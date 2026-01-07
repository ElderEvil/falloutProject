"""Service for handling audio conversations between users and dwellers."""

import logging
from uuid import uuid4

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.chat_message import chat_message as chat_message_crud
from app.crud.dweller import dweller as dweller_crud
from app.crud.llm_interaction import llm_interaction as llm_interaction_crud
from app.models import User
from app.models.base import SPECIALModel
from app.models.chat_message import ChatMessageCreate
from app.schemas.llm_interaction import LLMInteractionCreate
from app.services.minio import get_minio_client
from app.services.open_ai import get_ai_service

logger = logging.getLogger(__name__)


class ConversationService:
    """Handles audio conversation logic: STT, LLM response, TTS."""

    def __init__(self):
        self.ai_service = get_ai_service()
        self.minio_service = get_minio_client()

    async def process_audio_message(
        self,
        db_session: AsyncSession,
        user: User,
        dweller_id: UUID4,
        audio_bytes: bytes,
        audio_filename: str = "audio.webm",
    ) -> dict:
        """
        Process an audio message from user to dweller.

        Steps:
        1. Transcribe audio (STT)
        2. Generate text response from dweller (LLM)
        3. Generate audio response (TTS)
        4. Save everything to database and MinIO

        Returns:
            dict with user_message, dweller_response, and dweller_audio_url
        """
        # Get dweller info
        dweller = await dweller_crud.get_full_info(db_session, dweller_id)
        if not dweller:
            msg = f"Dweller {dweller_id} not found"
            raise ValueError(msg)

        # Step 1: Transcribe user audio
        logger.info("Transcribing audio message from user %s to dweller %s", user.id, dweller_id)
        transcribed_text = await self.ai_service.transcribe_audio(audio_bytes, filename=audio_filename)
        logger.debug("Transcription result: %s", transcribed_text)

        # Upload user audio to MinIO (optional, for history)
        user_audio_url = None
        if self.minio_service.enabled:
            user_audio_filename = f"chat/{user.id}/{dweller_id}/user_{uuid4()}.{audio_filename.split('.')[-1]}"
            user_audio_url = self.minio_service.upload_file(
                file_data=audio_bytes,
                file_name=user_audio_filename,
                file_type="audio/webm",
                bucket_name="chat-audio",
            )

        # Calculate audio duration (rough estimate: 1 byte ~ 1/8000 seconds for typical audio)
        # This is a placeholder - ideally use a library like pydub to get accurate duration
        audio_duration = len(audio_bytes) / 16000.0  # Rough estimate for WebM/Opus

        # Step 2: Generate dweller response using LLM
        special_stats = ", ".join(f"{stat}: {getattr(dweller, stat)}" for stat in SPECIALModel.__annotations__)
        vault_stats = (
            f" Average happiness: {dweller.vault.happiness}/100"
            f" Power: {dweller.vault.power}/{dweller.vault.power_max}"
            f" Food: {dweller.vault.food}/{dweller.vault.food_max}"
            f" Water: {dweller.vault.water}/{dweller.vault.water_max}"
        )

        dweller_prompt = f"""
        You are a Vault-Tec Dweller named {dweller.first_name} {dweller.last_name} in a post-apocalyptic world.
        You are {dweller.gender.value} {"Adult" if dweller.is_adult else "Child"} of level {dweller.level}.
        You are considered a {dweller.rarity.value} rarity dweller.
        You are in a vault {dweller.vault.number} with a group of other dwellers.
        You are in the {dweller.room.name if dweller.room else "a"} room of the vault.
        Your outfit is {dweller.outfit.name if dweller.outfit else "Vault Suit"}.
        Your weapon is {dweller.weapon.name if dweller.weapon else "Fist"}.
        You have {dweller.stimpack} Stimpacks and {dweller.radaway} Radaways.
        Your health is {dweller.health}/{dweller.max_health}.
        Your happiness level is {dweller.happiness}/100. Don't mention this, just act accordingly.
        Your SPECIAL stats are: {special_stats}. Don't mention them until asked, use this information for acting.
        In case user asks about vault - here is the information: {vault_stats}. Say it in a natural way.
        Try to be in character and be in line with the Fallout universe.
        Keep responses concise (under 150 words) since this will be converted to audio.
        """

        # Use the AI service with configured provider
        logger.info("Generating dweller response using configured AI provider")
        dweller_response_text = await self.ai_service.chat_completion(
            [
                {"role": "system", "content": dweller_prompt.strip()},
                {"role": "user", "content": transcribed_text},
            ]
        )

        # Step 3: Generate audio response (TTS)
        logger.info("Generating TTS audio for dweller response")
        dweller_audio_bytes = await self.ai_service.generate_audio(
            text=dweller_response_text,
            voice="alloy",  # Can be customized based on dweller gender
            model="tts-1",
        )

        # Upload dweller audio to MinIO
        dweller_audio_url = None
        if self.minio_service.enabled:
            dweller_audio_filename = f"chat/{user.id}/{dweller_id}/dweller_{uuid4()}.mp3"
            dweller_audio_url = self.minio_service.upload_file(
                file_data=dweller_audio_bytes,
                file_name=dweller_audio_filename,
                file_type="audio/mpeg",
                bucket_name="chat-audio",
            )

        # Step 4: Save to database
        # Save LLM interaction statistics
        llm_int_create = LLMInteractionCreate(
            parameters=transcribed_text,
            response=dweller_response_text,
            usage="audio_chat",
            user_id=user.id,
        )
        llm_interaction = await llm_interaction_crud.create(db_session, obj_in=llm_int_create)

        # Save user message
        await chat_message_crud.create_message(
            db_session,
            obj_in=ChatMessageCreate(
                vault_id=dweller.vault.id,
                from_user_id=user.id,
                to_dweller_id=dweller.id,
                message_text=transcribed_text,
                audio_url=user_audio_url,
                transcription=transcribed_text,
                audio_duration=audio_duration,
            ),
        )

        # Save dweller response
        await chat_message_crud.create_message(
            db_session,
            obj_in=ChatMessageCreate(
                vault_id=dweller.vault.id,
                from_dweller_id=dweller.id,
                to_user_id=user.id,
                message_text=dweller_response_text,
                audio_url=dweller_audio_url,
                llm_interaction_id=llm_interaction.id,
            ),
        )

        return {
            "transcription": transcribed_text,
            "user_audio_url": user_audio_url,
            "dweller_response": dweller_response_text,
            "dweller_audio_url": dweller_audio_url,
            "dweller_audio_bytes": dweller_audio_bytes,  # For immediate playback
        }


# Singleton instance
conversation_service = ConversationService()
