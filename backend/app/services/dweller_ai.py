import json

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.dweller import dweller as dweller_crud
from app.crud.vault import vault as vault_crud
from app.models.base import SPECIALModel
from app.schemas.common import GenderEnum
from app.schemas.dweller import DwellerReadFull, DwellerUpdate
from app.services.minio import get_minio_client
from app.services.open_ai import get_openai_service
from app.utils.exceptions import ContentNoChangeException


class DwellerAIService:
    def __init__(self):
        self.minio_service = get_minio_client()
        self.open_ai_service = get_openai_service()

    async def generate_backstory(
        self, db_session: AsyncSession, dweller_id: UUID4, origin: str = "Wasteland"
    ) -> DwellerReadFull:
        """Generate a backstory for a dweller."""
        dweller_obj = await dweller_crud.get_full_info(db_session, dweller_id)
        if dweller_obj.bio:
            raise ContentNoChangeException(detail="Dweller already has a bio")

        if origin.lower().startswith("vault"):
            dweller_vault = await vault_crud.get(db_session, dweller_obj.vault_id)
            if origin == dweller_vault.name:
                origin = "this vault from childhood"

        special_stats = ", ".join(f"{stat}: {getattr(dweller_obj, stat)}" for stat in SPECIALModel.__annotations__)
        gender_pronoun = "his" if dweller_obj.gender == GenderEnum.MALE else "her"
        system_prompt = (
            "Generate a Fallout game series style biography for a dweller"
            f"Include details about {gender_pronoun} background, skills, and personality traits as they relate to"
            f" living in {origin} and surviving in the post-apocalyptic world. "
            f"Use the dweller's SPECIAL attributes to help create a unique backstory. {special_stats}"
            "The bio should be a minimum of 50 words and a maximum of 1000 symbols."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Tell me about yourself, {dweller_obj.first_name}."},
            {"role": "assistant", "content": "Sure! Here's a brief bio about me:"},
        ]
        backstory = await self.open_ai_service.generate_completion(messages)

        await dweller_crud.update(db_session, dweller_id, DwellerUpdate(bio=backstory))

        return dweller_obj

    async def extend_bio(self, db_session: AsyncSession, dweller_id: UUID4) -> DwellerReadFull:
        dweller_obj = await dweller_crud.get_full_info(db_session, dweller_id)
        if not dweller_obj.bio:
            raise ContentNoChangeException(detail="Dweller doesn't have a bio to extend")

        extension_prompt = (
            "You are a helpful assistant. You must assist the user in generating a response to the following prompt."
            "You are helping a dweller to extend their bio with more details."
        )

        messages = [
            {"role": "system", "content": extension_prompt},
            {
                "role": "user",
                "content": f"Here's the current bio: {dweller_obj.bio}\nPlease extend it with more details.",
            },
        ]
        extended_bio = await self.open_ai_service.generate_completion(messages)

        full_bio = f"{dweller_obj.bio}\n\n{extended_bio}"

        await dweller_crud.update(db_session, dweller_id, DwellerUpdate(bio=full_bio))

        return dweller_obj

    async def generate_visual_attributes(self, db_session: AsyncSession, dweller_id: UUID4) -> DwellerReadFull:
        """Generate visual attributes for a dweller."""
        dweller_obj = await dweller_crud.get_full_info(db_session, dweller_id)
        if dweller_obj.visual_attributes:
            raise ContentNoChangeException(detail="Dweller already has visual attributes")

        visual_options = """
        age: teenager, adult, elder
        height: tall, average, short
        eye_color: blue, green, brown, hazel, gray
        appearance: attractive, cute, average, unattractive, ghoul
        skin_tone: fair, medium, olive, tan, dark
        build: slim, athletic, muscular, stocky, average, overweight
        hair_style: short, long, curly, straight, wavy, bald
        hair_color: blonde, brunette, redhead, black, gray, colored
        distinguishing_features: scar, tattoo, mole, freckles, birthmark, piercing
        clothing_style: casual, military, formal, rugged, eclectic
        (Only for male) facial_hair: clean - shaven, mustache, beard, goatee, stubble
        (Only for female) makeup: natural, glamorous, goth, no makeup
        """
        prompt = (
            f"Create visual attributes for {dweller_obj.first_name} {dweller_obj.last_name}."
            f"That's his/her backstory: {dweller_obj.bio}"
            "Include details about their appearance, clothing, and any other distinguishing features."
            "Use dweller backstory in case it can help to generate visual attributes."
            "Use JSON format to describe the visual attributes."
            'Examples: {"hair_color": "brown", "eye_color": "blue", "height": "average"},'
            '{"hair_color": "blonde", "eye_color": "green", "height": "short", "distinguishing_features": ["glasses", "freckles"]}'  # noqa:E501
            '{"hair_color": "grey", "eye_color": "brown", "height": "tall", "distinguishing_features": ["tattoo", "prosthetic arm"], "clothing_style": "military"}'  # noqa:E501
            f"Given options: {visual_options}"
        )
        visual_attributes_json = await self.open_ai_service.generate_completion_json(prompt)
        visual_attributes = json.loads(visual_attributes_json)

        await dweller_crud.update(db_session, dweller_id, DwellerUpdate(visual_attributes=visual_attributes))

        return dweller_obj

    async def generate_photo(self, db_session: AsyncSession, dweller_id: UUID4) -> DwellerReadFull:
        """Generate a photo for a dweller."""
        dweller_obj = await dweller_crud.get_full_info(db_session, dweller_id)
        if dweller_obj.image_url:
            raise ContentNoChangeException(detail="Dweller already has a photo")
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
            file_data=image_bytes, file_name=f"{dweller_id}.png", bucket_name="dweller-images"
        )
        thumbnail_url = self.minio_service.upload_thumbnail(
            file_data=image_bytes, file_name=f"{dweller_id}_thumbnail.png", bucket_name="dweller-thumbnails"
        )

        await dweller_crud.update(
            db_session, dweller_id, DwellerUpdate(image_url=image_url, thumbnail_url=thumbnail_url)
        )

        return dweller_obj

    async def dweller_generate_pipeline(
        self,
        db_session: AsyncSession,
        dweller_id: UUID4,
        origin: str | None = None,
    ) -> DwellerReadFull:
        """Generate Dweller's bio, visual attributes, and photo."""
        dweller_obj = await dweller_crud.get_full_info(db_session, dweller_id)
        if dweller_obj.bio and dweller_obj.visual_attributes and dweller_obj.image_url:
            raise ContentNoChangeException(detail="Dweller already has a bio, visual attributes, and photo")

        if not dweller_obj.bio:
            dweller_obj = await self.generate_backstory(db_session, dweller_id, origin)
        if not dweller_obj.visual_attributes:
            dweller_obj = await self.generate_visual_attributes(db_session, dweller_id)
        if not dweller_obj.image_url:
            dweller_obj = await self.generate_photo(db_session, dweller_id)

        return dweller_obj


dweller_ai = DwellerAIService()
