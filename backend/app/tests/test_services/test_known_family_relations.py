import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.vault import VaultCreateWithUserID
from app.services.dweller_service import dweller_service
from app.tests.factory.vaults import create_fake_vault


async def _create(db_session: AsyncSession, vault: Vault, template_id: str) -> Dweller:
    return await dweller_service.create_dweller_from_template(db_session, vault.id, template_id)


@pytest.mark.parametrize("hank_first", [True, False])
async def test_lucy_links_to_hank_regardless_of_creation_order(
    async_session: AsyncSession, vault: Vault, hank_first: bool
) -> None:
    if hank_first:
        hank = await _create(async_session, vault, "hank")
        lucy = await _create(async_session, vault, "lucy-maclean")
    else:
        lucy = await _create(async_session, vault, "lucy-maclean")
        hank = await _create(async_session, vault, "hank")
    await async_session.refresh(lucy)

    assert lucy.parent_1_id == hank.id
    assert f"/vault/{vault.id}/dwellers/{hank.id}" in (lucy.bio or "")
    if hank_first:
        assert any("dweller-link" in entry["text"] for entry in lucy.bio_entries)


async def test_sarah_links_to_elder_lyons_with_bio_alias(async_session: AsyncSession, vault: Vault) -> None:
    elder = await _create(async_session, vault, "elder-lyons")
    sarah = await _create(async_session, vault, "sarah-lyons")
    await async_session.refresh(sarah)

    assert sarah.parent_1_id == elder.id
    assert f"/vault/{vault.id}/dwellers/{elder.id}" in (sarah.bio or "")
    assert "Elder Owyn Lyons" in (sarah.bio or "")


async def test_different_vaults_are_not_linked(async_session: AsyncSession, vault: Vault) -> None:
    hank = await _create(async_session, vault, "hank")
    other_vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=vault.user_id),
    )
    lucy = await _create(async_session, other_vault, "lucy-maclean")
    await async_session.refresh(lucy)

    assert hank.vault_id != lucy.vault_id
    assert lucy.parent_1_id is None
