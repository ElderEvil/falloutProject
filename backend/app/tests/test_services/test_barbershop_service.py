"""Barbershop gate, fee, and appearance-change tests."""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import AgeGroupEnum, RoomTypeEnum, SPECIALEnum
from app.models.dweller import Dweller
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.barbershop import BarbershopChangeRequest
from app.schemas.room import RoomCreate
from app.services.barbershop_service import barbershop_service
from app.utils.exceptions import (
    BarbershopRequiredException,
    ContentNoChangeException,
    InsufficientResourcesException,
    ValidationException,
)


async def _make_barbershop(db_session: AsyncSession, vault: Vault) -> Room:
    return await crud.room.create(
        db_session,
        obj_in=RoomCreate(
            name="Barbershop",
            category=RoomTypeEnum.MISC,
            ability=SPECIALEnum.CHARISMA,
            population_required=50,
            base_cost=10000,
            incremental_cost=None,
            t2_upgrade_cost=50000,
            t3_upgrade_cost=None,
            size_min=6,
            size_max=6,
            size=6,
            tier=1,
            vault_id=vault.id,
        ),
    )


async def _staff(db_session: AsyncSession, room: Room, dweller: Dweller) -> None:
    dweller.room_id = room.id
    db_session.add(dweller)
    await db_session.commit()
    await db_session.refresh(dweller)


async def _set_human(
    db_session: AsyncSession,
    dweller: Dweller,
    *,
    skin_tone: str = "Pale",
    hair_color: str = "blonde",
    image_url: str | None = None,
    thumbnail_url: str | None = None,
) -> None:
    dweller.visual_attributes = {
        "race": "human",
        "faction": "vault_dweller",
        "skin_tone": skin_tone,
        "hair_color": hair_color,
    }
    if image_url is not None:
        dweller.image_url = image_url
        dweller.thumbnail_url = thumbnail_url
    db_session.add(dweller)
    await db_session.commit()
    await db_session.refresh(dweller)


async def _change(session: AsyncSession, room: Room, dweller: Dweller, skin_tone: str, hair_color: str):
    return await barbershop_service.change_appearance(
        session,
        room=room,
        dweller_id=dweller.id,
        request=BarbershopChangeRequest(skin_tone=skin_tone, hair_color=hair_color),
    )


async def _fund(session: AsyncSession, vault: Vault, caps: int) -> Vault:
    vault.bottle_caps = caps
    session.add(vault)
    await session.commit()
    return vault


@pytest.fixture
async def shop(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> Room:
    room = await _make_barbershop(async_session, vault)
    await _staff(async_session, room, dweller)
    return room


@pytest.fixture
async def human(async_session: AsyncSession, shop: Room, dweller: Dweller) -> Dweller:
    await _set_human(async_session, dweller)
    return dweller


@pytest.fixture
async def funded(async_session: AsyncSession, vault: Vault) -> Vault:
    return await _fund(async_session, vault, 500)


async def test_status_reports_built_unstaffed_barbershop(async_session: AsyncSession, vault: Vault) -> None:
    await _make_barbershop(async_session, vault)
    status = await barbershop_service.get_status(async_session, vault.id)
    assert status.built is True
    assert status.staffed is False
    assert status.fee == 350
    assert status.skin_fee == 200
    assert status.hair_fee == 150
    assert status.skin_tones == ["Pale", "Tan", "Brown", "Ebony"]
    assert status.hair_colors == ["blonde", "brunette", "black", "brown", "red", "gray"]


async def test_require_available_rejects_missing_barbershop(async_session: AsyncSession, vault: Vault) -> None:
    with pytest.raises(BarbershopRequiredException, match="Build a Barbershop"):
        await barbershop_service.require_available(async_session, vault.id)


async def test_require_available_rejects_unstaffed_barbershop(async_session: AsyncSession, vault: Vault) -> None:
    await _make_barbershop(async_session, vault)
    with pytest.raises(BarbershopRequiredException, match="Assign at least one dweller"):
        await barbershop_service.require_available(async_session, vault.id)


async def test_change_appearance_deducts_fee_and_swaps_default_portrait(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, shop: Room, human: Dweller, funded: Vault
) -> None:
    before_image = dweller.image_url
    response = await _change(async_session, shop, dweller, "Tan", "black")
    assert response.portrait_updated is True
    assert response.fee == 350
    assert response.remaining_caps == 150
    assert response.dweller.visual_attributes["skin_tone"] == "Tan"
    assert response.dweller.visual_attributes["hair_color"] == "black"
    assert response.dweller.image_url != before_image
    assert "SkinTan_HairBlack" in response.dweller.image_url
    await async_session.refresh(vault)
    assert vault.bottle_caps == 150


async def test_change_appearance_charges_only_for_the_changed_attribute(
    async_session: AsyncSession, dweller: Dweller, shop: Room, human: Dweller, funded: Vault
) -> None:
    skin_response = await _change(async_session, shop, dweller, "Tan", "blonde")
    assert skin_response.fee == 200
    assert skin_response.remaining_caps == 300
    await async_session.refresh(dweller)
    hair_response = await _change(async_session, shop, dweller, "Tan", "black")
    assert hair_response.fee == 150
    assert hair_response.remaining_caps == 150


async def test_change_appearance_preserves_custom_art(
    async_session: AsyncSession, dweller: Dweller, shop: Room, funded: Vault
) -> None:
    custom_image = "https://cdn.example.com/custom-portrait.png"
    custom_thumbnail = "https://cdn.example.com/custom-thumb.png"
    await _set_human(async_session, dweller, image_url=custom_image, thumbnail_url=custom_thumbnail)
    response = await _change(async_session, shop, dweller, "Ebony", "red")
    assert response.portrait_updated is False
    assert response.dweller.image_url == custom_image
    assert response.dweller.thumbnail_url == custom_thumbnail
    assert response.dweller.visual_attributes["skin_tone"] == "Ebony"
    assert response.dweller.visual_attributes["hair_color"] == "red"


async def test_change_appearance_rejects_insufficient_caps(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, shop: Room, human: Dweller
) -> None:
    await _fund(async_session, vault, 50)
    with pytest.raises(InsufficientResourcesException):
        await _change(async_session, shop, dweller, "Tan", "black")
    await async_session.refresh(dweller)
    await async_session.refresh(vault)
    assert dweller.visual_attributes["skin_tone"] == "Pale"
    assert vault.bottle_caps == 50


async def test_change_appearance_rejects_non_human(async_session: AsyncSession, dweller: Dweller, shop: Room) -> None:
    dweller.visual_attributes = {"race": "ghoul", "state_of_being": "sane", "skin_tone": "Pale", "hair_color": "gray"}
    async_session.add(dweller)
    await async_session.commit()
    with pytest.raises(ValidationException, match="Only human"):
        await _change(async_session, shop, dweller, "Tan", "black")


async def test_change_appearance_allows_gen_3_synth(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, shop: Room
) -> None:
    dweller.visual_attributes = {
        "race": "synth",
        "state_of_being": "gen_3",
        "skin_tone": "Pale",
        "hair_color": "blonde",
    }
    await _fund(async_session, vault, 500)
    async_session.add(dweller)
    await async_session.commit()
    response = await _change(async_session, shop, dweller, "Tan", "black")
    assert response.dweller.visual_attributes["skin_tone"] == "Tan"
    assert response.dweller.visual_attributes["hair_color"] == "black"


async def test_change_appearance_rejects_child(
    async_session: AsyncSession, dweller: Dweller, shop: Room, human: Dweller
) -> None:
    dweller.age_group = AgeGroupEnum.CHILD
    async_session.add(dweller)
    await async_session.commit()
    with pytest.raises(ValidationException, match="adult or elder"):
        await _change(async_session, shop, dweller, "Tan", "black")


async def test_change_appearance_rejects_unknown_preset(
    async_session: AsyncSession, dweller: Dweller, shop: Room, human: Dweller
) -> None:
    with pytest.raises(ValidationException, match="valid skin tone"):
        await _change(async_session, shop, dweller, "Light", "black")


async def test_change_appearance_rejects_no_change(
    async_session: AsyncSession, dweller: Dweller, shop: Room, human: Dweller
) -> None:
    with pytest.raises(ContentNoChangeException):
        await _change(async_session, shop, dweller, "Pale", "blonde")


async def test_change_appearance_requires_the_room_to_be_staffed(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    room = await _make_barbershop(async_session, vault)
    await _set_human(async_session, dweller)
    with pytest.raises(BarbershopRequiredException, match="this Barbershop"):
        await _change(async_session, room, dweller, "Tan", "black")
