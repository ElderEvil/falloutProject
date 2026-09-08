"""Service for handling audio conversations between users and dwellers."""

import asyncio
import logging
import random
from uuid import uuid4

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import GenderEnum
from app.crud.chat_message import chat_message as chat_message_crud
from app.crud.llm_interaction import llm_interaction as llm_interaction_crud
from app.models import User
from app.models.chat_message import ChatMessageCreate
from app.schemas.chat import VoiceChatResult
from app.schemas.llm_interaction import LLMInteractionCreate
from app.services.access_service import get_accessible_dweller
from app.services.ai_service import get_ai_service
from app.services.chat.agent_runner import run_chat_agent
from app.services.chat.models import AgentChatResult, VoiceMessagePayload
from app.services.chat.notifications import send_chat_notification, unlock_places_after_conversation
from app.services.prompt_service import get_instructions, get_provider_model_snapshot
from app.services.quota_service import quota_service
from app.services.storage import get_storage_client
from app.utils.exceptions import ValidationException

logger = logging.getLogger(__name__)


VOICE_MAP = {
    GenderEnum.MALE: ["echo", "fable", "onyx"],
    GenderEnum.FEMALE: ["nova", "shimmer", "alloy"],
}


class ConversationService:
    """Handles audio conversation logic: STT, LLM response, TTS."""

    def __init__(self):
        self.ai_service = get_ai_service()
        self.storage_service = get_storage_client()

    @staticmethod
    def _select_voice_for_gender(gender: GenderEnum | None) -> str:
        if gender is not None and gender in VOICE_MAP:
            return random.choice(VOICE_MAP[gender])
        return "alloy"

    async def _transcribe_audio(
        self, audio_bytes: bytes, user_id: UUID4, dweller_id: UUID4, audio_filename: str
    ) -> tuple[str, str | None, float | None]:
        transcribed_text = await self.ai_service.transcribe_audio(audio_bytes, filename=audio_filename)
        logger.debug("Transcription result: %s", transcribed_text)

        user_audio_url = None
        if self.storage_service is not None:
            user_audio_filename = (
                f"chat/{user_id}/{dweller_id}/user_{uuid4()}.{audio_filename.rsplit('.', maxsplit=1)[-1]}"
            )
            user_audio_url = await asyncio.to_thread(
                self.storage_service.upload_file,
                file_data=audio_bytes,
                file_name=user_audio_filename,
                file_type="audio/webm",
                bucket_name="chat-audio",
            )

        return transcribed_text, user_audio_url, None

    async def _generate_response_with_agent(
        self, db_session: AsyncSession, dweller, transcribed_text: str, instructions: str
    ) -> AgentChatResult:
        return await run_chat_agent(db_session, dweller, transcribed_text, instructions, for_audio=True)

    async def _generate_tts_audio(
        self, text: str, gender: GenderEnum | None, user_id: UUID4, dweller_id: UUID4
    ) -> tuple[bytes, str | None]:
        voice = self._select_voice_for_gender(gender)
        logger.info("Generating TTS audio (gender=%s, voice=%s)", gender, voice)
        audio_bytes = await self.ai_service.generate_audio(text=text, voice=voice, model="tts-1")
        audio_url = None
        if self.storage_service is not None:
            audio_filename = f"chat/{user_id}/{dweller_id}/dweller_{uuid4()}.mp3"
            audio_url = await asyncio.to_thread(
                self.storage_service.upload_file,
                file_data=audio_bytes,
                file_name=audio_filename,
                file_type="audio/mpeg",
                bucket_name="chat-audio",
            )
        return audio_bytes, audio_url

    async def _save_messages_to_db(
        self,
        db_session: AsyncSession,
        user: User,
        dweller,
        payload: VoiceMessagePayload,
    ) -> UUID4:
        llm_int_create = LLMInteractionCreate(
            parameters=payload.transcribed_text,
            response=payload.dweller_response_text,
            usage="audio_chat",
            user_id=user.id,
            prompt_tokens=payload.prompt_tokens,
            completion_tokens=payload.completion_tokens,
            total_tokens=payload.total_tokens,
            provider=payload.provider,
            model=payload.model,
            prompt_id=payload.prompt_id,
            instructions_hash=payload.instructions_hash,
            instructions_snapshot=payload.instructions_snapshot,
        )
        llm_interaction = await llm_interaction_crud.create(db_session, obj_in=llm_int_create)
        await chat_message_crud.create_message(
            db_session,
            obj_in=ChatMessageCreate(
                vault_id=dweller.vault.id,
                from_user_id=user.id,
                to_dweller_id=dweller.id,
                message_text=payload.transcribed_text,
                audio_url=payload.user_audio_url,
                transcription=payload.transcribed_text,
                audio_duration=payload.audio_duration,
            ),
        )
        chat_create_data = ChatMessageCreate(
            vault_id=dweller.vault.id,
            from_dweller_id=dweller.id,
            to_user_id=user.id,
            message_text=payload.dweller_response_text,
            audio_url=payload.dweller_audio_url,
            llm_interaction_id=llm_interaction.id,
        )
        if payload.happiness_impact:
            chat_create_data.happiness_delta = payload.happiness_impact.delta
            chat_create_data.happiness_reason = payload.happiness_impact.reason_text
        dweller_message = await chat_message_crud.create_message(db_session, obj_in=chat_create_data)
        return dweller_message.id

    async def process_audio_message(
        self,
        db_session: AsyncSession,
        user: User,
        dweller_id: UUID4,
        audio_bytes: bytes,
        audio_filename: str = "audio.webm",
    ) -> VoiceChatResult:
        if not audio_bytes:
            raise ValidationException(detail="Empty audio file")
        async with db_session.begin_nested():
            dweller = await get_accessible_dweller(dweller_id, user, db_session)

            logger.info("Transcribing audio message from user %s to dweller %s", user.id, dweller_id)
            transcribed_text, user_audio_url, audio_duration = await self._transcribe_audio(
                audio_bytes, user.id, dweller_id, audio_filename
            )

            # Check quota before running LLM (after transcription, before AI response)
            quota_result = await quota_service.check_quota(user.id, db_session)

            quota_result.ensure_allowed()

            instructions, prompt_id, instructions_hash = await get_instructions(db_session, "chat")
            provider, model = await get_provider_model_snapshot(db_session)
            response = await self._generate_response_with_agent(db_session, dweller, transcribed_text, instructions)
            dweller_audio_bytes, dweller_audio_url = await self._generate_tts_audio(
                response.response_text, dweller.gender, user.id, dweller_id
            )
            payload = VoiceMessagePayload(
                transcribed_text=transcribed_text,
                user_audio_url=user_audio_url,
                audio_duration=audio_duration,
                dweller_response_text=response.response_text,
                dweller_audio_url=dweller_audio_url,
                happiness_impact=response.happiness_impact,
                action_suggestion=response.action_suggestion,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_tokens=response.total_tokens,
                provider=provider,
                model=model,
                prompt_id=prompt_id,
                instructions_hash=instructions_hash,
                instructions_snapshot=instructions,
            )
            dweller_message_id = await self._save_messages_to_db(db_session, user, dweller, payload)
            unlocked_places = await unlock_places_after_conversation(db_session, dweller)
            result = VoiceChatResult(
                transcription=transcribed_text,
                user_audio_url=user_audio_url,
                dweller_response=response.response_text,
                dweller_audio_url=dweller_audio_url,
                dweller_audio_bytes=dweller_audio_bytes,
                dweller_message_id=dweller_message_id,
                happiness_impact=response.happiness_impact,
                action_suggestion=response.action_suggestion,
                unlocked_places=unlocked_places,
            )
        await db_session.commit()
        await send_chat_notification(
            user_id=user.id,
            dweller_id=dweller_id,
            dweller_message_id=result.dweller_message_id,
            happiness_impact=result.happiness_impact,
            action_suggestion=result.action_suggestion,
        )
        return result


# Singleton instance
conversation_service = ConversationService()
