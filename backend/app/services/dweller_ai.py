import asyncio
import logging
from math import ceil
from typing import Any

from fastapi import HTTPException
from pydantic import UUID4
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior
from sqlmodel.ext.asyncio.session import AsyncSession

from app.agents.deps import BackstoryDeps, ExtendBioDeps, VisualAttributesDeps
from app.agents.dweller_agents import backstory_agent, bio_extension_agent, visual_attributes_agent
from app.core.config import settings
from app.crud.dweller import dweller as dweller_crud
from app.crud.llm_interaction import llm_interaction as llm_interaction_crud
from app.models import User
from app.models.base import SPECIALModel
from app.schemas.dweller import DwellerReadFull, DwellerUpdate, DwellerVisualAttributes
from app.schemas.llm_interaction import LLMInteractionCreate
from app.services.ai_service import get_ai_service
from app.services.map_service import map_service
from app.services.prompt_service import get_instructions, get_provider_model_snapshot
from app.services.quota_service import quota_service
from app.services.storage import get_storage_client
from app.utils.exceptions import ContentNoChangeException, QuotaExceededException

logger = logging.getLogger(__name__)

BIO_MAX_LENGTH = 900
BIO_DB_MAX_LENGTH = 1_024  # matches Dweller.bio Field(max_length=1024)

# Visual-attribute fields that may only reflect items the dweller owns/equips.
EQUIPMENT_RESTRICTED_FIELDS = ("accessory", "object_held")


def restrict_equipment_fields(visual_attributes: dict[str, Any], equipped_items: list[str]) -> None:
    """Remove accessory/object_held fields that do not match equipped items."""
    if equipped_items:
        owned = set(equipped_items)
        for field in EQUIPMENT_RESTRICTED_FIELDS:
            if field in visual_attributes and visual_attributes[field] not in owned:
                visual_attributes.pop(field)
    else:
        for field in EQUIPMENT_RESTRICTED_FIELDS:
            visual_attributes.pop(field, None)


class DwellerAIService:
    def __init__(self):
        self.storage_service = get_storage_client()
        self.ai_service = get_ai_service()

    async def _register_map_places_best_effort(
        self,
        db_session: AsyncSession,
        dweller_obj: DwellerReadFull,
        *,
        origin_place: str,
        visited_places: list[str],
        explicit_origin: str | None = None,
    ) -> None:
        """Register bio-extracted places on the world map — best-effort, never raises."""
        try:
            await map_service.register_bio_places(
                db_session,
                dweller_obj,
                origin_place=origin_place,
                visited_places=visited_places,
                explicit_origin=explicit_origin,
            )
        except Exception:
            logger.exception("Failed to register map places for dweller %s", dweller_obj.id)

    def _extract_usage(self, result: Any, *, agent_name: str) -> tuple[int | None, int | None, int | None]:
        """Extract token usage from an agent result, tolerating provider failures."""
        try:
            usage = result.usage()
        except Exception:
            logger.exception("Failed to extract usage info from %s agent result", agent_name)
            return None, None, None
        else:
            return usage.input_tokens, usage.output_tokens, usage.total_tokens

    @staticmethod
    def _provider_error_detail(error: ModelHTTPError) -> str:
        """Return a safe provider message suitable for a player-facing API response."""
        if isinstance(error.body, dict):
            message = error.body.get("message")
            if isinstance(message, str) and message:
                return message
        return f"AI provider request failed (HTTP {error.status_code})"

    async def generate_backstory(
        self,
        user: User,
        db_session: AsyncSession,
        *,
        dweller_id: UUID4 | None = None,
        dweller_info: DwellerReadFull | None = None,
        origin: str | None = None,
    ) -> DwellerReadFull:
        """Generate a backstory for a dweller using PydanticAI agent."""
        quota_result = await quota_service.check_quota(user.id, db_session)
        if not quota_result.allowed:
            raise QuotaExceededException(
                detail=f"Monthly token quota exceeded. Used: {quota_result.used}/{quota_result.limit} tokens."
            )

        dweller_obj = dweller_info or await dweller_crud.get_full_info(db_session, dweller_id)

        location = origin or "Wasteland"
        special_stats = SPECIALModel.format_special_stats(dweller_obj)

        # Create dependencies for the agent
        deps = BackstoryDeps(
            first_name=dweller_obj.first_name,
            gender=dweller_obj.gender,
            special_stats=special_stats,
            location=location,
        )

        instructions, prompt_id, instructions_hash = await get_instructions(db_session, "backstory")
        provider, model = await get_provider_model_snapshot(db_session)

        # Run the backstory agent
        result = await backstory_agent.run(
            f"Tell me about yourself, {dweller_obj.first_name}.", deps=deps, instructions=instructions
        )
        backstory = result.output.bio

        # Keep generated biographies within the prompt's rendering-friendly upper bound.
        if len(backstory) > BIO_MAX_LENGTH:
            backstory = backstory[: BIO_MAX_LENGTH - 3] + "..."
            msg = f"Backstory exceeded max length, truncated to {BIO_MAX_LENGTH} characters"
            logger.warning(msg)

        await dweller_crud.update(db_session, dweller_obj.id, DwellerUpdate(bio=backstory))

        # Register bio-extracted places on the world map (best-effort; after bio commit)
        await self._register_map_places_best_effort(
            db_session,
            dweller_obj,
            origin_place=result.output.origin_place,
            visited_places=result.output.visited_places,
            explicit_origin=origin,
        )

        prompt_tokens, completion_tokens, total_tokens = self._extract_usage(result, agent_name="backstory")

        llm_int_create = LLMInteractionCreate(
            parameters=origin,
            response=backstory,
            usage="generate_backstory",
            user_id=user.id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            provider=provider,
            model=model,
            prompt_id=prompt_id,
            instructions_hash=instructions_hash,
            instructions_snapshot=instructions,
        )
        await llm_interaction_crud.create(
            db_session,
            obj_in=llm_int_create,
        )

        return dweller_obj

    async def extend_bio(self, db_session: AsyncSession, dweller_id: UUID4, user: User) -> DwellerReadFull:
        """Extend existing dweller bio using PydanticAI agent."""
        # Check quota before making LLM call
        quota_result = await quota_service.check_quota(user.id, db_session)
        if not quota_result.allowed:
            raise QuotaExceededException(
                detail=f"Monthly token quota exceeded. Used: {quota_result.used}/{quota_result.limit} tokens."
            )

        dweller_obj = await dweller_crud.get_full_info(db_session, dweller_id)
        if not dweller_obj.bio:
            raise ContentNoChangeException(detail="Dweller doesn't have a bio to extend")

        # Create dependencies for the agent
        deps = ExtendBioDeps(current_bio=dweller_obj.bio)

        instructions, prompt_id, instructions_hash = await get_instructions(db_session, "extend_bio")
        provider, model = await get_provider_model_snapshot(db_session)

        # Run the bio extension agent
        result = await bio_extension_agent.run(
            "Please extend this biography with more details.", deps=deps, instructions=instructions
        )
        extended_bio = result.output.extended_bio

        full_bio = f"{dweller_obj.bio}\n\n{extended_bio}"

        # Length guard (D15): ensure the combined bio fits within the model's max_length=1024
        if len(full_bio) > BIO_DB_MAX_LENGTH:
            full_bio = full_bio[: BIO_DB_MAX_LENGTH - 3] + "..."
            msg = f"Extended bio exceeded max length, truncated to {BIO_DB_MAX_LENGTH} characters"
            logger.warning(msg)

        await dweller_crud.update(db_session, dweller_id, DwellerUpdate(bio=full_bio))

        # Register bio-extracted places on the world map (best-effort; after bio commit)
        await self._register_map_places_best_effort(
            db_session,
            dweller_obj,
            origin_place="",
            visited_places=result.output.visited_places,
        )

        prompt_tokens, completion_tokens, total_tokens = self._extract_usage(result, agent_name="bio extension")

        llm_int_create = LLMInteractionCreate(
            parameters=dweller_obj.bio,
            response=extended_bio,
            usage="extend_bio",
            user_id=user.id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            provider=provider,
            model=model,
            prompt_id=prompt_id,
            instructions_hash=instructions_hash,
            instructions_snapshot=instructions,
        )
        await llm_interaction_crud.create(
            db_session,
            obj_in=llm_int_create,
        )

        return await dweller_crud.get_full_info(db_session, dweller_id)

    async def generate_visual_attributes(
        self,
        user: User,
        db_session: AsyncSession,
        *,
        dweller_id: UUID4 | None = None,
        dweller_info: DwellerReadFull | None = None,
    ) -> DwellerReadFull:
        """Generate visual attributes for a dweller using PydanticAI agent."""
        # Check quota before making LLM call
        quota_result = await quota_service.check_quota(user.id, db_session)
        if not quota_result.allowed:
            raise QuotaExceededException(
                detail=f"Monthly token quota exceeded. Used: {quota_result.used}/{quota_result.limit} tokens."
            )

        dweller_obj = dweller_info or await dweller_crud.get_full_info(db_session, dweller_id)

        existing_attrs = dweller_obj.visual_attributes or {}

        dweller_race = existing_attrs.get("race") if isinstance(existing_attrs, dict) else None
        dweller_faction = existing_attrs.get("faction") if isinstance(existing_attrs, dict) else None

        equipped_items = [item.name for item in (dweller_obj.weapon, dweller_obj.outfit) if item is not None]

        deps = VisualAttributesDeps(
            first_name=dweller_obj.first_name,
            last_name=dweller_obj.last_name or "",
            gender=dweller_obj.gender,
            bio=dweller_obj.bio,
            race=dweller_race,
            faction=dweller_faction,
            equipped_items=equipped_items,
        )

        instructions, prompt_id, instructions_hash = await get_instructions(db_session, "visual_attributes")
        provider, model = await get_provider_model_snapshot(db_session)

        try:
            result = await visual_attributes_agent.run(
                f"Create visual attributes for {dweller_obj.first_name} {dweller_obj.last_name}.",
                deps=deps,
                instructions=instructions,
            )
        except ModelHTTPError as error:
            logger.exception("Appearance generation provider request failed for dweller %s", dweller_obj.id)
            raise HTTPException(status_code=502, detail=self._provider_error_detail(error)) from error
        except UnexpectedModelBehavior as error:
            logger.exception("Appearance generation returned invalid structured output for dweller %s", dweller_obj.id)
            raise HTTPException(
                status_code=502,
                detail="The AI provider returned an invalid appearance response. Please try again.",
            ) from error

        visual_attributes = result.output.model_dump(exclude_none=True)

        restrict_equipment_fields(visual_attributes, equipped_items)

        if isinstance(existing_attrs, dict):
            for key in ("race", "faction", "age", "state_of_being", "voice_line_text", "voice_line_url"):
                if key in existing_attrs and key not in visual_attributes:
                    visual_attributes[key] = existing_attrs[key]

        await dweller_crud.update(db_session, dweller_obj.id, DwellerUpdate(visual_attributes=visual_attributes))

        prompt_tokens, completion_tokens, total_tokens = self._extract_usage(result, agent_name="visual attributes")

        llm_int_create = LLMInteractionCreate(
            parameters=dweller_obj.bio,
            response=str(visual_attributes),
            usage="generate_visual_attributes",
            user_id=user.id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            provider=provider,
            model=model,
            prompt_id=prompt_id,
            instructions_hash=instructions_hash,
            instructions_snapshot=instructions,
        )
        await llm_interaction_crud.create(
            db_session,
            obj_in=llm_int_create,
        )

        return await dweller_crud.get_full_info(db_session, dweller_obj.id)

    async def generate_photo(
        self,
        user: User,
        db_session: AsyncSession,
        *,
        dweller_id: UUID4 | None = None,
        dweller_info: DwellerReadFull | None = None,
        force: bool = False,
    ) -> DwellerReadFull:
        """Generate a photo for a dweller."""
        dweller_obj = dweller_info or await dweller_crud.get_full_info(db_session, dweller_id)
        if dweller_obj.image_url and not force:
            raise ContentNoChangeException(detail="Dweller already has a photo")

        if self.storage_service is None:
            raise HTTPException(
                status_code=503,
                detail="Image upload service is not available. Cannot generate photo.",
            )

        prompt = (
            "Create a photo of a Fallout shelter game vault dweller."
            "Mood: post-apocalyptic, retro-futuristic, sci-fi"
            "Style: realistic, cartoon"
            "Color scheme: pastel, blue and yellow room color scheme"
            f"Dweller info: {dweller_obj.rarity} {dweller_obj.gender}"
            f"Dweller visual attributes: {dweller_obj.visual_attributes}"
        )
        try:
            image_bytes = await self.ai_service.generate_image(prompt=prompt, return_bytes=True)
            image_url = await asyncio.to_thread(
                self.storage_service.upload_file,
                file_data=image_bytes,
                file_name=f"{dweller_obj.id}.png",
                bucket_name="dweller-images",
            )
            thumbnail_url = await asyncio.to_thread(
                self.storage_service.upload_thumbnail,
                file_data=image_bytes,
                file_name=f"{dweller_obj.id}_thumbnail.png",
                bucket_name="dweller-thumbnails",
            )
        except Exception as error:
            logger.exception("Portrait generation failed for dweller %s", dweller_obj.id)
            raise HTTPException(status_code=502, detail="Portrait generation failed. Please try again.") from error

        await dweller_crud.update(
            db_session, dweller_obj.id, DwellerUpdate(image_url=image_url, thumbnail_url=thumbnail_url)
        )

        llm_int_create = LLMInteractionCreate(
            parameters=str(dweller_obj.visual_attributes),
            response=image_url,
            usage="generate_photo",
            user_id=user.id,
            provider="openai",
            model=settings.AI_IMAGE_MODEL,
        )
        await llm_interaction_crud.create(
            db_session,
            obj_in=llm_int_create,
        )

        return dweller_obj

    async def generate_audio(
        self,
        text: str,
        user: User,
        db_session: AsyncSession,
        *,
        dweller_id: UUID4 | None = None,
        dweller_info: DwellerReadFull | None = None,
        voice_type: str = "echo",
    ) -> DwellerReadFull:
        """Generates a voice line for a dweller, uploads it to storage, and updates dweller info."""
        # Estimate TTS tokens using character count approximation (~4 chars per token)
        # TTS doesn't return token counts from API, so we estimate based on input text
        estimated_tokens = ceil(len(text) / 4)

        dweller_obj = dweller_info or await dweller_crud.get_full_info(db_session, dweller_id)
        if dweller_obj.visual_attributes and dweller_obj.visual_attributes.get("voice_line_url"):
            raise ContentNoChangeException(detail="Dweller already has an audio line. Overwrite not implemented yet.")

        if not self.storage_service.enabled:
            logger.warning("Storage service is disabled, cannot generate audio for dweller %s", dweller_obj.id)
            raise HTTPException(
                status_code=503,
                detail="Audio upload service is not available. Cannot generate audio.",
            )

        # Check quota before making TTS API call
        quota_result = await quota_service.check_quota(user.id, db_session)
        if not quota_result.allowed or quota_result.remaining < estimated_tokens:
            raise QuotaExceededException(
                detail=f"Monthly token quota exceeded. Used: {quota_result.used}/{quota_result.limit} tokens. "
                f"Estimated TTS cost: {estimated_tokens} tokens."
            )

        try:
            audio_bytes = await self.ai_service.generate_audio(text=text, voice=voice_type, model="tts-1")
            if not len(audio_bytes):
                logger.warning("Empty input")
        except (ValueError, RuntimeError) as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate audio via OpenAI: {e}") from e

        audio_url = await asyncio.to_thread(
            self.storage_service.upload_file,
            file_data=audio_bytes,
            file_name=f"{dweller_obj.id}_voice.mp3",
            file_type="audio/mpeg",
            bucket_name="dweller-audio",
        )

        updated_visual_attributes = dweller_obj.visual_attributes or {}
        updated_visual_attributes["voice_line_text"] = text
        updated_visual_attributes["voice_line_url"] = audio_url

        await dweller_crud.update(
            db_session,
            dweller_obj.id,
            DwellerUpdate(visual_attributes=updated_visual_attributes),
        )

        llm_int_create = LLMInteractionCreate(
            parameters=f"text_input: {text}, voice_type: {voice_type}",
            response=audio_url,
            usage="generate_audio",
            user_id=user.id,
            prompt_tokens=None,
            completion_tokens=estimated_tokens,
            total_tokens=estimated_tokens,
            provider="openai",
            model="tts-1",
        )
        await llm_interaction_crud.create(
            db_session,
            obj_in=llm_int_create,
        )

        return await dweller_crud.get_full_info(db_session, dweller_obj.id)

    async def generate_dweller_avatar(
        self,
        dweller_id: UUID4,
        dweller_first_name: str,
        dweller_last_name: str,
        visual_attributes_input: DwellerVisualAttributes,
        db_session: AsyncSession,
        user: User,
    ) -> DwellerReadFull:
        """Save avatar choices, generate a photo, and optionally add a voice line."""
        update_data = DwellerUpdate(
            first_name=dweller_first_name,
            last_name=dweller_last_name,
            visual_attributes=visual_attributes_input,
        )
        updated_dweller = await dweller_crud.update(db_session, dweller_id, update_data)

        dweller_obj = await self.generate_photo(db_session=db_session, dweller_info=updated_dweller, user=user)
        if visual_attributes_input.voice_line_text:
            return await self.generate_audio(
                db_session=db_session,
                dweller_info=dweller_obj,
                user=user,
                text=visual_attributes_input.voice_line_text,
            )
        return dweller_obj

    def _has_substantial_visual_attributes(self, visual_attributes: dict | None) -> bool:
        """Check if visual_attributes has meaningful content beyond identity defaults."""
        if not visual_attributes:
            return False
        if not isinstance(visual_attributes, dict):
            return True
        non_identity_keys = [
            k for k, v in visual_attributes.items() if k not in ("race", "faction", "age", "state_of_being") and v
        ]
        return bool(non_identity_keys)

    async def dweller_generate_pipeline(
        self,
        db_session: AsyncSession,
        dweller_id: UUID4,
        user: User,
        origin: str | None = None,
    ) -> DwellerReadFull:
        """Generate Dweller's bio, visual attributes, and photo."""
        dweller_obj = await dweller_crud.get_full_info(db_session, dweller_id)
        if dweller_obj.bio and dweller_obj.visual_attributes and dweller_obj.image_url:
            raise ContentNoChangeException(detail="Dweller already has a bio, visual attributes, and photo")

        if not dweller_obj.bio:
            dweller_obj = await self.generate_backstory(
                db_session=db_session, dweller_info=dweller_obj, origin=origin, user=user
            )
        if not self._has_substantial_visual_attributes(dweller_obj.visual_attributes):
            dweller_obj = await self.generate_visual_attributes(
                db_session=db_session, dweller_info=dweller_obj, user=user
            )
        if not dweller_obj.image_url:
            dweller_obj = await self.generate_photo(db_session=db_session, dweller_info=dweller_obj, user=user)

        return dweller_obj


dweller_ai = DwellerAIService()
