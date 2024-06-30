import json

from pydantic import UUID4
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.crud.room import room as room_crud
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.schemas.dweller import (
    DwellerCreate,
    DwellerCreateCommonOverride,
    DwellerReadFull,
    DwellerReadWithRoomID,
    DwellerUpdate,
)
from app.services.minio import get_minio_client
from app.services.open_ai import generate_completion, generate_completion_json, generate_image
from app.tests.factory.dwellers import create_random_common_dweller
from app.utils.exceptions import ContentNoChangeException
from app.utils.validation import validate_room_transfer, validate_vault_transfer

BOOSTED_STAT_VALUE = 5


class CRUDDweller(CRUDBase[Dweller, DwellerCreate, DwellerUpdate]):
    @staticmethod
    async def create_random(
        db_session: AsyncSession, vault_id: UUID4, obj_in: DwellerCreateCommonOverride | None = None
    ) -> Dweller:
        """Create a random common dweller."""
        dweller_data = create_random_common_dweller()
        if obj_in:
            new_dweller_data = obj_in.dict(exclude_unset=True)
            if stat := new_dweller_data.get("special_boost"):
                dweller_data[stat.value.lower()] = BOOSTED_STAT_VALUE
                new_dweller_data.pop("special_boost")
            dweller_data.update(new_dweller_data)

        db_obj = Dweller(**dweller_data, vault_id=vault_id)
        db_session.add(db_obj)
        await db_session.commit()
        await db_session.refresh(db_obj)
        return db_obj

    @staticmethod
    def calculate_experience_required(dweller_obj: Dweller) -> int:
        """Calculate the experience required for the next level."""
        return int(100 * 1.5**dweller_obj.level)

    @staticmethod
    def is_alive(dweller_obj: Dweller) -> bool:
        return dweller_obj.health > 0

    async def add_experience(self, db_session: AsyncSession, dweller_obj: Dweller, amount: int):
        """Add experience to dweller and level up if necessary."""
        dweller_obj.experience += amount
        experience_required = self.calculate_experience_required(dweller_obj)
        if dweller_obj.experience >= experience_required:
            dweller_obj.level += 1
            dweller_obj.experience -= experience_required
        return await self.update(
            db_session, dweller_obj.id, DwellerUpdate(level=dweller_obj.level, experience=dweller_obj.experience)
        )

    async def get_dweller_by_name(self, db_session: AsyncSession, name: str) -> Dweller | None:
        """Get dweller by name."""
        query = select(self.model).where(self.model.first_name == name)
        response = await db_session.execute(query)
        return response.scalars().first()

    async def move_to_room(
        self, db_session: AsyncSession, dweller_id: UUID4, room_id: UUID4
    ) -> DwellerReadWithRoomID | None:
        """Move dweller to a different room."""
        dweller_obj = await self.get(db_session, dweller_id)
        validate_room_transfer(dweller_obj.room_id, room_id)

        room_obj = await room_crud.get(db_session, room_id)
        validate_vault_transfer(dweller_obj.vault_id, room_obj.vault_id)

        if not dweller_obj.room_id and not await vault_crud.is_enough_population_space(
            db_session=db_session, vault_id=dweller_obj.vault_id, space_required=1
        ):
            raise ContentNoChangeException(detail="Not enough space in the vault to move dweller")
        dweller_obj = await self.update(db_session, dweller_id, DwellerUpdate(room_id=room_id))

        return DwellerReadWithRoomID.from_orm(dweller_obj)

    async def reanimate(self, db_session: AsyncSession, dweller_obj: Dweller) -> Dweller | None:
        """Revive a dead dweller."""
        if self.is_alive(dweller_obj):
            raise ContentNoChangeException(detail="Dweller is already alive")
        await self.update(db_session, dweller_obj.id, DwellerUpdate(health=dweller_obj.max_health))
        return dweller_obj

    async def get_full_info(self, db_session: AsyncSession, dweller_id: UUID4) -> DwellerReadFull:
        """Get full information about a dweller."""
        query = (
            select(self.model)
            .options(
                selectinload(self.model.vault),
                selectinload(self.model.room),
                selectinload(self.model.weapon),
                selectinload(self.model.outfit),
            )
            .where(self.model.id == dweller_id)
        )
        response = await db_session.execute(query)
        dweller_obj = response.scalar_one_or_none()

        return DwellerReadFull.from_orm(dweller_obj)

    async def generate_backstory(
        self, db_session: AsyncSession, dweller_id: UUID4, origin: str = "Vault"
    ) -> DwellerReadFull:
        """Generate a backstory for a dweller."""
        dweller_obj = await self.get_full_info(db_session, dweller_id)
        if dweller_obj.bio:
            raise ContentNoChangeException(detail="Dweller already has a bio")
        system_prompt = (
            "Generate a Fallout game series style biography for a dweller"
            "Include details about their background, skills, and personality traits as they relate to living in "
            f"{origin} and surviving in the post-apocalyptic world."
            "The bio should be a minimum of 100 words and a maximum of 1000 symbols."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Tell me about yourself, {dweller_obj.first_name}."},
            {"role": "assistant", "content": "Sure! Here's a brief bio about me:"},
        ]
        backstory = await generate_completion(messages)

        await self.update(db_session, dweller_id, DwellerUpdate(bio=backstory))

        return dweller_obj

    async def generate_visual_attributes(self, db_session: AsyncSession, dweller_id: UUID4) -> DwellerReadFull:
        """Generate visual attributes for a dweller."""
        dweller_obj = await self.get_full_info(db_session, dweller_id)
        if dweller_obj.visual_attributes:
            raise ContentNoChangeException(detail="Dweller already has visual attributes")

        visual_options = """
        hair_color: blonde, brunette, redhead, black, gray
        eye_color: blue, green, brown, hazel, gray
        skin_tone: fair, medium, olive, tan, dark
        build: slim, athletic, muscular, stocky, average
        height: tall, average, short
        distinguishing_features: scar, tattoo, mole, freckles, birthmark
        hair_style: short, long, curly, straight, wavy, bald
        (Only for male)facial_hair: clean - shaven, mustache, beard, goatee, stubble
        clothing_style: casual, military, formal, rugged, eclectic
        """

        prompt = (
            f"Create visual attributes for {dweller_obj.first_name} {dweller_obj.last_name}."
            f"That's his/her backstory: {dweller_obj.bio}"
            "Include details about their appearance, clothing, and any other distinguishing features."
            "Use dweller backstory in case it can help to generate visual attributes."
            "Use JSON format to describe the visual attributes."
            'Example: {"hair_color": "brown", "eye_color": "blue", "height": "average"}'
            f"Given options: {visual_options}"
        )
        visual_attributes = await generate_completion_json(prompt)
        print(visual_attributes)
        attributes = json.loads(visual_attributes)

        await self.update(db_session, dweller_id, DwellerUpdate(visual_attributes=attributes))

        return dweller_obj

    async def generate_photo(self, db_session: AsyncSession, dweller_id: UUID4) -> DwellerReadFull:
        """Generate a photo for a dweller."""
        dweller_obj = await self.get_full_info(db_session, dweller_id)
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
        image_bytes = await generate_image(prompt, return_bytes=True)
        minio_client = get_minio_client()
        image_url = minio_client.upload_file(image_bytes, f"{dweller_id}.png", "dweller-images")

        await self.update(db_session, dweller_id, DwellerUpdate(image_url=image_url))

        return dweller_obj

    async def extend_bio(self, db_session: AsyncSession, dweller_id: UUID4) -> DwellerReadFull:
        dweller_obj = await self.get_full_info(db_session, dweller_id)
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

        extended_bio = await generate_completion(messages)

        full_bio = f"{dweller_obj.bio}\n\n{extended_bio}"

        await self.update(db_session, dweller_id, DwellerUpdate(bio=full_bio))

        return dweller_obj


dweller = CRUDDweller(Dweller)
