from typing import Any

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import AgeGroupEnum, GenderEnum, RarityEnum
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.tests.factory.dwellers import create_fake_dweller
from app.utils.dweller_assets import resolve_dweller_image_urls

pytestmark = pytest.mark.asyncio(scope="module")

HUMAN = {"race": "human", "skin_tone": "Pale", "hair_color": "Blonde"}
EBONY = {"race": "human", "skin_tone": "Ebony", "hair_color": "black"}


async def _create_dweller(async_session: AsyncSession, vault: Vault, **overrides: Any) -> Dweller:
    payload = create_fake_dweller() | {"rarity": RarityEnum.COMMON, "gender": GenderEnum.MALE, **overrides}
    return await crud.dweller.create(async_session, DwellerCreate(**payload, vault_id=vault.id))


async def _put_visuals(client, headers, dweller, visuals):
    return await client.put(f"/dwellers/{dweller.id}", headers=headers, json={"visual_attributes": visuals})


async def _age_change(async_session, dweller, age_group):
    dweller.age_group = age_group
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)


async def test_direct_model_insert_applies_defaults(async_session, vault):
    dweller = Dweller(
        first_name="Direct",
        last_name="Insert",
        gender=GenderEnum.FEMALE,
        rarity=RarityEnum.COMMON,
        vault_id=vault.id,
        visual_attributes={"race": "synth", "state_of_being": "gen_2"},
    )
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)
    assert (dweller.image_url, dweller.thumbnail_url) == resolve_dweller_image_urls(dweller)


async def test_detail_fills_default_portrait(async_client, async_session, superuser_token_headers, vault):
    dweller = await _create_dweller(async_session, vault, visual_attributes={"race": "ghoul", "state_of_being": "wild"})
    expected_image, expected_thumbnail = resolve_dweller_image_urls(dweller)
    response = await async_client.get(f"/dwellers/{dweller.id}", headers=superuser_token_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["image_url"] == expected_image
    assert body["thumbnail_url"] == expected_thumbnail
    assert body["is_default_portrait"] is True


async def test_list_fills_default_thumbnail(async_client, async_session, superuser_token_headers, vault):
    dweller = await _create_dweller(
        async_session,
        vault,
        gender=GenderEnum.FEMALE,
        visual_attributes={"race": "super_mutant", "state_of_being": "behemoth"},
    )
    response = await async_client.get(f"/dwellers/vault/{vault.id}/", headers=superuser_token_headers)
    assert response.status_code == 200
    _, expected_thumbnail = resolve_dweller_image_urls(dweller)
    item = next(row for row in response.json() if row["id"] == str(dweller.id))
    assert item["thumbnail_url"] == expected_thumbnail
    assert item["is_default_portrait"] is True


async def test_existing_portrait_is_preserved(async_client, async_session, superuser_token_headers, vault):
    dweller = await _create_dweller(async_session, vault, image_url="/static/custom.png", thumbnail_url=None)
    response = await async_client.get(f"/dwellers/{dweller.id}", headers=superuser_token_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["image_url"] == "/static/custom.png"
    assert body["thumbnail_url"] == "/static/custom.png"
    assert body["is_default_portrait"] is False


@pytest.mark.parametrize(
    ("age_group", "visuals", "stem"),
    [
        (AgeGroupEnum.CHILD, HUMAN, "child/FOS_Dw_Default_Human_Child_Male_SkinPale_HairBlonde.webp"),
        (AgeGroupEnum.ELDER, EBONY, "elder/FOS_Dw_Default_Human_Elder_Male_SkinEbony_HairGray.webp"),
    ],
)
async def test_insert_uses_age_variant(async_session, vault, age_group, visuals, stem):
    dweller = await _create_dweller(async_session, vault, age_group=age_group, visual_attributes=visuals)
    assert dweller.image_url == f"/static/dweller_images/variants/{stem}"
    assert dweller.thumbnail_url == f"/static/dweller_thumbnails/variants/{stem}"


@pytest.mark.parametrize(
    ("start_age", "new_age", "visuals", "stem"),
    [
        (AgeGroupEnum.CHILD, AgeGroupEnum.ADULT, HUMAN, "adult/FOS_Dw_Default_Human_Male_SkinPale_HairBlonde.webp"),
        (
            AgeGroupEnum.ADULT,
            AgeGroupEnum.ELDER,
            EBONY,
            "elder/FOS_Dw_Default_Human_Elder_Male_SkinEbony_HairGray.webp",
        ),
    ],
)
async def test_age_update_swaps_default_portrait(async_session, vault, start_age, new_age, visuals, stem):
    dweller = await _create_dweller(async_session, vault, age_group=start_age, visual_attributes=visuals)
    await _age_change(async_session, dweller, new_age)
    assert dweller.image_url == f"/static/dweller_images/variants/{stem}"


async def test_age_update_preserves_custom_portrait(async_session, vault):
    dweller = await _create_dweller(
        async_session,
        vault,
        age_group=AgeGroupEnum.CHILD,
        image_url="/static/custom.png",
        thumbnail_url="/static/custom-thumb.png",
        visual_attributes=HUMAN,
    )
    await _age_change(async_session, dweller, AgeGroupEnum.ADULT)
    assert dweller.image_url == "/static/custom.png"
    assert dweller.thumbnail_url == "/static/custom-thumb.png"


async def test_insert_uses_human_variant_for_preset_colors(async_session, vault):
    dweller = await _create_dweller(
        async_session,
        vault,
        gender=GenderEnum.FEMALE,
        age_group=AgeGroupEnum.ADULT,
        visual_attributes={"race": "human", "skin_tone": "Ebony", "hair_color": "red"},
    )
    stem = "adult/FOS_Dw_Default_Human_Female_SkinEbony_HairRed.webp"
    assert dweller.image_url == f"/static/dweller_images/variants/{stem}"
    assert dweller.thumbnail_url == f"/static/dweller_thumbnails/variants/{stem}"


async def test_color_update_swaps_human_variant(
    async_client, async_session, superuser_token_headers, vault, staffed_barbershop
):
    dweller = await _create_dweller(
        async_session, vault, age_group=AgeGroupEnum.ADULT, visual_attributes={"race": "human"}
    )
    response = await _put_visuals(
        async_client, superuser_token_headers, dweller, {"race": "human", "skin_tone": "Tan", "hair_color": "black"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["image_url"] == "/static/dweller_images/variants/adult/FOS_Dw_Default_Human_Male_SkinTan_HairBlack.webp"
    assert body["is_default_portrait"] is True


async def test_unsupported_color_update_falls_back_to_base(
    async_client, async_session, superuser_token_headers, vault, staffed_barbershop
):
    dweller = await _create_dweller(async_session, vault, age_group=AgeGroupEnum.ADULT, visual_attributes=HUMAN)
    response = await _put_visuals(
        async_client, superuser_token_headers, dweller, {"race": "human", "skin_tone": "Light", "hair_color": "white"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["image_url"] == "/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp"


async def test_color_update_preserves_custom_portrait(
    async_client, async_session, superuser_token_headers, vault, staffed_barbershop
):
    dweller = await _create_dweller(
        async_session,
        vault,
        image_url="/static/custom.png",
        thumbnail_url="/static/custom-thumb.png",
        visual_attributes={"race": "human"},
    )
    response = await _put_visuals(
        async_client, superuser_token_headers, dweller, {"race": "human", "skin_tone": "Ebony", "hair_color": "gray"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["image_url"] == "/static/custom.png"
    assert body["thumbnail_url"] == "/static/custom-thumb.png"


async def test_identity_update_refreshes_default_portrait(
    async_client, async_session, superuser_token_headers, vault, staffed_barbershop
):
    dweller = await _create_dweller(async_session, vault, visual_attributes={"race": "human"})
    response = await _put_visuals(
        async_client, superuser_token_headers, dweller, {"race": "ghoul", "state_of_being": "wild"}
    )
    assert response.status_code == 200
    await async_session.refresh(dweller)
    expected_image, expected_thumbnail = resolve_dweller_image_urls(dweller)
    body = response.json()
    assert body["image_url"] == expected_image
    assert body["thumbnail_url"] == expected_thumbnail
    assert body["is_default_portrait"] is True


async def test_identity_update_preserves_custom_portrait(
    async_client, async_session, superuser_token_headers, vault, staffed_barbershop
):
    dweller = await _create_dweller(
        async_session,
        vault,
        image_url="/static/custom.png",
        thumbnail_url="/static/custom-thumb.png",
        visual_attributes={"race": "human"},
    )
    response = await _put_visuals(
        async_client, superuser_token_headers, dweller, {"race": "ghoul", "state_of_being": "wild"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["image_url"] == "/static/custom.png"
    assert body["thumbnail_url"] == "/static/custom-thumb.png"
    assert body["is_default_portrait"] is False


async def test_gen1_synth_uses_one_genderless_default(async_client, async_session, superuser_token_headers, vault):
    male = await _create_dweller(
        async_session, vault, gender=GenderEnum.MALE, visual_attributes={"race": "synth", "state_of_being": "gen_1"}
    )
    female = await _create_dweller(
        async_session, vault, gender=GenderEnum.FEMALE, visual_attributes={"race": "synth", "state_of_being": "gen_1"}
    )
    for dweller in (male, female):
        expected_image, expected_thumbnail = resolve_dweller_image_urls(dweller)
        response = await async_client.get(f"/dwellers/{dweller.id}", headers=superuser_token_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["image_url"] == expected_image
        assert body["thumbnail_url"] == expected_thumbnail
        assert "Male" not in body["image_url"]
        assert "Female" not in body["image_url"]
        assert body["is_default_portrait"] is True
