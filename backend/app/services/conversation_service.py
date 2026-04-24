"""Service for handling audio conversations between users and dwellers."""

import logging
import random
from dataclasses import dataclass
from uuid import uuid4

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.agents.dweller_chat_agent import (
    DwellerChatDeps,
    DwellerChatOutput,
    compute_happiness_delta,
    derive_reason_code,
    dweller_chat_agent,
    parse_action_suggestion,
)
from app.crud.chat_message import chat_message as chat_message_crud
from app.crud.dweller import dweller as dweller_crud
from app.crud.llm_interaction import llm_interaction as llm_interaction_crud
from app.models import User
from app.models.base import SPECIALModel
from app.models.chat_message import ChatMessageCreate
from app.schemas.chat import ActionSuggestion, NoAction
from app.schemas.common import GenderEnum
from app.schemas.happiness import HappinessImpact, HappinessReasonCode
from app.schemas.llm_interaction import LLMInteractionCreate
from app.services.chat_happiness_service import apply_chat_happiness
from app.services.open_ai import get_ai_service
from app.services.quota_service import quota_service
from app.services.storage import get_storage_client
from app.utils.exceptions import DwellerNotFoundError, QuotaExceededException

logger = logging.getLogger(__name__)

VOICE_MAP = {
    GenderEnum.MALE: ["echo", "fable", "onyx"],
    GenderEnum.FEMALE: ["nova", "shimmer", "alloy"],
}


@dataclass
class MessagePayload:
    """Data holder for message processing results."""

    transcribed_text: str
    user_audio_url: str | None
    audio_duration: float | None
    dweller_response_text: str
    dweller_audio_url: str | None
    happiness_impact: HappinessImpact | None = None
    action_suggestion: ActionSuggestion | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass
class ChatGenerationResult:
    text: str
    happiness_impact: HappinessImpact | None
    action_suggestion: ActionSuggestion | None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


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

    @staticmethod
    def _build_dweller_prompt(dweller, *, for_audio: bool = False) -> str:
        special_stats = ", ".join(f"{stat}: {getattr(dweller, stat)}" for stat in SPECIALModel.__annotations__)
        vault_stats = (
            f" Average happiness: {dweller.vault.happiness}/100"
            f" Power: {dweller.vault.power}/{dweller.vault.power_max}"
            f" Food: {dweller.vault.food}/{dweller.vault.food_max}"
            f" Water: {dweller.vault.water}/{dweller.vault.water_max}"
        )
        audio_instruction = (
            "\nKeep responses concise (under 150 words) since this will be converted to audio." if for_audio else ""
        )
        return f"""
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
        Try to be in character and be in line with the Fallout universe.{audio_instruction}
        """

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
            user_audio_url = self.storage_service.upload_file(
                file_data=audio_bytes,
                file_name=user_audio_filename,
                file_type="audio/webm",
                bucket_name="chat-audio",
            )

        return transcribed_text, user_audio_url, None

    async def _generate_response_with_agent(
        self, db_session: AsyncSession, dweller, transcribed_text: str
    ) -> ChatGenerationResult:
        deps = DwellerChatDeps(db_session=db_session, dweller=dweller, vault_id=dweller.vault.id)

        try:
            logger.info("Generating dweller response using PydanticAI agent")
            result = await dweller_chat_agent.run(transcribed_text, deps=deps)
        except Exception:
            logger.exception("Dweller chat agent failed, using fallback for voice chat")
            dweller_prompt = self._build_dweller_prompt(dweller, for_audio=True)
            result = await self.ai_service.chat_completion_with_usage(
                [
                    {"role": "system", "content": dweller_prompt.strip()},
                    {"role": "user", "content": transcribed_text},
                ]
            )
            happiness = HappinessImpact(
                delta=0,
                reason_code=HappinessReasonCode.CHAT_NEUTRAL,
                reason_text="Voice chat processed without sentiment analysis",
                happiness_after=dweller.happiness,
            )
            return ChatGenerationResult(
                text=result.text,
                happiness_impact=happiness,
                action_suggestion=NoAction(reason="Unable to analyze conversation for suggestions"),
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                total_tokens=result.total_tokens,
            )

        output: DwellerChatOutput = result.output
        try:
            usage = result.usage()
            prompt_tokens = usage.input_tokens
            completion_tokens = usage.output_tokens
            total_tokens = usage.total_tokens
        except Exception:  # noqa: BLE001
            logger.warning("Failed to extract usage info from voice chat agent result")
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None
        delta = compute_happiness_delta(output.sentiment_score)
        new_dweller_happiness, _ = await apply_chat_happiness(db_session=db_session, dweller_id=dweller.id, delta=delta)
        reason_code_str = derive_reason_code(output.sentiment_score)
        happiness_impact = HappinessImpact(
            delta=delta,
            reason_code=HappinessReasonCode(reason_code_str),
            reason_text=output.reason_text,
            happiness_after=new_dweller_happiness,
        )
        action_suggestion = await parse_action_suggestion(output, db_session, dweller)
        return ChatGenerationResult(
            text=output.response_text,
            happiness_impact=happiness_impact,
            action_suggestion=action_suggestion,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    async def _generate_tts_audio(
        self, text: str, gender: GenderEnum | None, user_id: UUID4, dweller_id: UUID4
    ) -> tuple[bytes, str | None]:
        voice = self._select_voice_for_gender(gender)
        logger.info("Generating TTS audio (gender=%s, voice=%s)", gender, voice)
        audio_bytes = await self.ai_service.generate_audio(text=text, voice=voice, model="tts-1")
        audio_url = None
        if self.storage_service is not None:
            audio_filename = f"chat/{user_id}/{dweller_id}/dweller_{uuid4()}.mp3"
            audio_url = self.storage_service.upload_file(
                file_data=audio_bytes, file_name=audio_filename, file_type="audio/mpeg", bucket_name="chat-audio"
            )
        return audio_bytes, audio_url

    async def _save_messages_to_db(
        self,
        db_session: AsyncSession,
        user: User,
        dweller,
        payload: "MessagePayload",
    ) -> UUID4:
        llm_int_create = LLMInteractionCreate(
            parameters=payload.transcribed_text,
            response=payload.dweller_response_text,
            usage="audio_chat",
            user_id=user.id,
            prompt_tokens=payload.prompt_tokens,
            completion_tokens=payload.completion_tokens,
            total_tokens=payload.total_tokens,
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
    ) -> dict:
        dweller = await dweller_crud.get_full_info(db_session, dweller_id)
        if not dweller:
            msg = f"Dweller {dweller_id} not found"
            raise DwellerNotFoundError(msg)

        logger.info("Transcribing audio message from user %s to dweller %s", user.id, dweller_id)
        transcribed_text, user_audio_url, audio_duration = await self._transcribe_audio(
            audio_bytes, user.id, dweller_id, audio_filename
        )

        # Check quota before running LLM (after transcription, before AI response)
        quota_result = await quota_service.check_quota(user.id, db_session)

        # Build headers for quota info
        quota_headers = {
            "X-Quota-Remaining": str(quota_result.remaining),
        }
        if quota_result.warning:
            quota_headers["X-Quota-Warning"] = "true"

        # If quota exceeded, raise exception with headers
        if not quota_result.allowed:
            detail = f"Monthly token quota exceeded. You have used {quota_result.used} of {quota_result.limit} tokens."
            raise QuotaExceededException(detail=detail, headers=quota_headers)

        response = await self._generate_response_with_agent(db_session, dweller, transcribed_text)
        dweller_audio_bytes, dweller_audio_url = await self._generate_tts_audio(
            response.text, dweller.gender, user.id, dweller_id
        )
        payload = MessagePayload(
            transcribed_text=transcribed_text,
            user_audio_url=user_audio_url,
            audio_duration=audio_duration,
            dweller_response_text=response.text,
            dweller_audio_url=dweller_audio_url,
            happiness_impact=response.happiness_impact,
            action_suggestion=response.action_suggestion,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            total_tokens=response.total_tokens,
        )
        dweller_message_id = await self._save_messages_to_db(db_session, user, dweller, payload)

        return {
            "transcription": transcribed_text,
            "user_audio_url": user_audio_url,
            "dweller_response": response.text,
            "dweller_audio_url": dweller_audio_url,
            "dweller_audio_bytes": dweller_audio_bytes,
            "dweller_message_id": dweller_message_id,
            "happiness_impact": response.happiness_impact,
            "action_suggestion": response.action_suggestion,
        }


# Singleton instance
conversation_service = ConversationService()
