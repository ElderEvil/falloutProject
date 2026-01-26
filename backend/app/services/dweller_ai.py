import logging

from fastapi import HTTPException
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.agents.deps import BackstoryDeps, ExtendBioDeps, VisualAttributesDeps
from app.agents.dweller_agents import backstory_agent, bio_extension_agent, visual_attributes_agent
from app.crud.dweller import dweller as dweller_crud
from app.crud.llm_interaction import llm_interaction as llm_interaction_crud
from app.models import User
from app.models.base import SPECIALModel
from app.schemas.common import GenderEnum
from app.schemas.dweller import DwellerReadFull, DwellerUpdate, DwellerVisualAttributesInput
from app.schemas.llm_interaction import LLMInteractionCreate
from app.services.minio import get_minio_client
from app.services.open_ai import get_ai_service
from app.utils.exceptions import ContentNoChangeException

logger = logging.getLogger(__name__)

GENDER_PRONOUNS_MAP = {
    GenderEnum.MALE: "his",
    GenderEnum.FEMALE: "her",
    None: "",
}

BIO_MAX_LENGTH = 1_000


class DwellerAIService:
    def __init__(self):
        self.minio_service = get_minio_client()
        self.open_ai_service = get_ai_service()

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
        dweller_obj = dweller_info or await dweller_crud.get_full_info(db_session, dweller_id)
        if dweller_obj.bio:
            raise ContentNoChangeException(detail="Dweller already has a bio")

        location = origin or "Wasteland"
        special_stats = ", ".join(f"{stat}: {getattr(dweller_obj, stat)}" for stat in SPECIALModel.__annotations__)

        # Create dependencies for the agent
        deps = BackstoryDeps(
            first_name=dweller_obj.first_name,
            gender=dweller_obj.gender,
            special_stats=special_stats,
            location=location,
        )

        # Run the backstory agent
        result = await backstory_agent.run(f"Tell me about yourself, {dweller_obj.first_name}.", deps=deps)
        backstory = result.output.bio

        # Safety check: truncate if exceeds max length (shouldn't happen with proper prompts)
        if len(backstory) > BIO_MAX_LENGTH:
            backstory = backstory[: BIO_MAX_LENGTH - 3] + "..."
            msg = f"Backstory exceeded max length, truncated to {BIO_MAX_LENGTH} characters"
            logger.warning(msg)

        await dweller_crud.update(db_session, dweller_obj.id, DwellerUpdate(bio=backstory))

        llm_int_create = LLMInteractionCreate(
            parameters=origin,
            response=backstory,
            usage="generate_backstory",
            user_id=user.id,
        )
        await llm_interaction_crud.create(
            db_session,
            obj_in=llm_int_create,
        )

        return dweller_obj

    async def extend_bio(self, db_session: AsyncSession, dweller_id: UUID4, user: User) -> DwellerReadFull:
        """Extend existing dweller bio using PydanticAI agent."""
        dweller_obj = await dweller_crud.get_full_info(db_session, dweller_id)
        if not dweller_obj.bio:
            raise ContentNoChangeException(detail="Dweller doesn't have a bio to extend")

        # Create dependencies for the agent
        deps = ExtendBioDeps(current_bio=dweller_obj.bio)

        # Run the bio extension agent
        result = await bio_extension_agent.run("Please extend this biography with more details.", deps=deps)
        extended_bio = result.output.extended_bio

        full_bio = f"{dweller_obj.bio}\n\n{extended_bio}"

        await dweller_crud.update(db_session, dweller_id, DwellerUpdate(bio=full_bio))

        llm_int_create = LLMInteractionCreate(
            parameters=dweller_obj.bio,
            response=extended_bio,
            usage="extend_bio",
            user_id=user.id,
        )
        await llm_interaction_crud.create(
            db_session,
            obj_in=llm_int_create,
        )

        return dweller_obj

    async def generate_visual_attributes(
        self,
        user: User,
        db_session: AsyncSession,
        *,
        dweller_id: UUID4 | None = None,
        dweller_info: DwellerReadFull | None = None,
    ) -> DwellerReadFull:
        """Generate visual attributes for a dweller using PydanticAI agent."""
        dweller_obj = dweller_info or await dweller_crud.get_full_info(db_session, dweller_id)
        if dweller_obj.visual_attributes:
            raise ContentNoChangeException(detail="Dweller already has visual attributes")

        # Create dependencies for the agent
        deps = VisualAttributesDeps(
            first_name=dweller_obj.first_name,
            last_name=dweller_obj.last_name or "",
            gender=dweller_obj.gender,
            bio=dweller_obj.bio,
        )

        # Run the visual attributes agent
        result = await visual_attributes_agent.run(
            f"Create visual attributes for {dweller_obj.first_name} {dweller_obj.last_name}.", deps=deps
        )

        # Convert Pydantic model to dict, excluding None values
        visual_attributes = result.output.model_dump(exclude_none=True)

        await dweller_crud.update(db_session, dweller_obj.id, DwellerUpdate(visual_attributes=visual_attributes))

        llm_int_create = LLMInteractionCreate(
            parameters=dweller_obj.bio,
            response=str(visual_attributes),
            usage="generate_visual_attributes",
            user_id=user.id,
        )
        await llm_interaction_crud.create(
            db_session,
            obj_in=llm_int_create,
        )

        return dweller_obj

    async def generate_photo(
        self,
        user: User,
        db_session: AsyncSession,
        *,
        dweller_id: UUID4 | None = None,
        dweller_info: DwellerReadFull | None = None,
    ) -> DwellerReadFull:
        """Generate a photo for a dweller."""
        dweller_obj = dweller_info or await dweller_crud.get_full_info(db_session, dweller_id)
        if dweller_obj.image_url:
            raise ContentNoChangeException(detail="Dweller already has a photo")

        if not self.minio_service.enabled:
            logger.warning("MinIO is disabled, cannot generate photo for dweller %s", dweller_obj.id)
            raise HTTPException(
                status_code=503,
                detail="Image upload service (MinIO) is not available. Cannot generate photo.",
            )

        prompt = (
            "Create a photo of a Fallout shelter game vault dweller."
            "Mood: post-apocalyptic, retro-futuristic, sci-fi"
            "Style: realistic, cartoon"
            "Color scheme: pastel, blue and yellow room color scheme"
            f"Dweller info: {dweller_obj.rarity} {dweller_obj.gender}"
            f"Dweller visual attributes: {dweller_obj.visual_attributes}"
        )
        image_bytes = await self.open_ai_service.generate_image(prompt=prompt, return_bytes=True)
        image_url = self.minio_service.upload_file(
            file_data=image_bytes, file_name=f"{dweller_obj.id}.png", bucket_name="dweller-images"
        )
        thumbnail_url = self.minio_service.upload_thumbnail(
            file_data=image_bytes, file_name=f"{dweller_obj.id}_thumbnail.png", bucket_name="dweller-thumbnails"
        )

        await dweller_crud.update(
            db_session, dweller_obj.id, DwellerUpdate(image_url=image_url, thumbnail_url=thumbnail_url)
        )

        llm_int_create = LLMInteractionCreate(
            parameters=str(dweller_obj.visual_attributes),
            response=image_url,
            usage="generate_photo",
            user_id=user.id,
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
        """
        Generates a voice line for a dweller, uploads it to MinIO, and updates dweller info.
        """
        dweller_obj = dweller_info or await dweller_crud.get_full_info(db_session, dweller_id)
        if dweller_obj.visual_attributes and dweller_obj.visual_attributes.get("voice_line_url"):
            raise ContentNoChangeException(detail="Dweller already has an audio line. Overwrite not implemented yet.")

        if not self.minio_service.enabled:
            logger.warning("MinIO is disabled, cannot generate audio for dweller %s", dweller_obj.id)
            raise HTTPException(
                status_code=503,
                detail="Audio upload service (MinIO) is not available. Cannot generate audio.",
            )

        try:
            audio_bytes = await self.open_ai_service.generate_audio(text=text, voice=voice_type, model="tts-1")
            if not len(audio_bytes):
                logger.warning("Empty input")
        except (ValueError, RuntimeError) as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate audio via OpenAI: {e}") from e

        audio_url = self.minio_service.upload_file(
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
            parameters=f"text_input: {text}, voice_type: {voice_type}",  # Store input parameters
            response=audio_url,
            usage="generate_audio",
            user_id=user.id,
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
        visual_attributes_input: DwellerVisualAttributesInput,
        db_session: AsyncSession,
        user: User,
    ) -> DwellerReadFull:
        # 1. Update Dweller with provided visual attributes
        # This is where we save the user's choices.
        update_data = DwellerUpdate(
            first_name=dweller_first_name,
            last_name=dweller_last_name,
            visual_attributes=visual_attributes_input,
        )
        updated_dweller = await dweller_crud.update(db_session, dweller_id, update_data)

        # 2. Refine the prompt
        # The prompt should be built based on the *updated* dweller's attributes.
        # This could be more sophisticated using the visual_attributes_input.
        # You would need to add a method to your DwellerAIService for this.
        # For simplicity, let's assume `generate_photo` handles prompt building internally
        # or takes a prompt from this endpoint if you implement a prompt building service here.

        # Example: Building prompt from current dweller object
        # You'll need to pass 'character' (from Streamlit) to build_prompt here,
        # or integrate prompt building into DwellerAIService.
        # For now, let's assume dweller_ai_service.generate_photo pulls what it needs from dweller_obj
        # after it's updated.

        # 3. Generate Photo (using your existing DwellerAIService)
        dweller_obj = await dweller_ai.generate_photo(db_session=db_session, dweller_info=updated_dweller, user=user)
        # 4. Generate Audio
        return await dweller_ai.generate_audio(
            db_session=db_session,
            dweller_info=dweller_obj,
            user=user,
            text=visual_attributes_input.voice_line_text,
        )

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
        if not dweller_obj.visual_attributes:
            dweller_obj = await self.generate_visual_attributes(
                db_session=db_session, dweller_info=dweller_obj, user=user
            )
        if not dweller_obj.image_url:
            dweller_obj = await self.generate_photo(db_session=db_session, dweller_info=dweller_obj, user=user)

        return dweller_obj


dweller_ai = DwellerAIService()
