"""Catalog of opt-in scenario starts for newly created vaults."""

from dataclasses import dataclass

from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import GenderEnum
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreateCommonOverride
from app.services.dweller_service import dweller_service
from app.services.exploration.expedition_scenario_service import (
    ExpeditionScenarioResult,
    expedition_scenario_service,
)


@dataclass(frozen=True)
class VaultScenario:
    number: int
    key: str
    title: str
    description: str
    dweller_level: int
    special: int
    duration_hours: int = 8
    all_sites: bool = True
    single_scene_only: bool = True
    choice_only: bool = True
    site_id: str | None = None
    male_dwellers: int | None = None
    female_dwellers: int | None = None


VAULT_SCENARIOS = (
    VaultScenario(
        number=1,
        key="vault_1_test",
        title="Vault 1 — Scout Test",
        description=(
            "Adds a level 5 / SPECIAL 4 Scout and a single-scene stat-check expedition. "
            "Extra living capacity; starter objectives skipped. Starts at the site picker."
        ),
        dweller_level=5,
        special=4,
    ),
    VaultScenario(
        number=68,
        key="vault_68_test",
        title="Vault 68 — The Ratio",
        description=(
            "99 men and 1 woman. Adds a level 10 / SPECIAL 7 Scout and the Vault 68 social "
            "encounter. Extra living capacity; starter objectives skipped. Starts at the site picker."
        ),
        dweller_level=10,
        special=7,
        site_id="vault_68",
        male_dwellers=99,
        female_dwellers=1,
    ),
    VaultScenario(
        number=69,
        key="vault_69_test",
        title="Vault 69 — The Inverse",
        description=(
            "The inverse of Vault 68: 99 women and 1 man. Adds a level 3 / SPECIAL 3 Scout "
            "and the Vault 69 social encounter. Extra living capacity; starter objectives skipped. "
            "Starts at the site picker."
        ),
        dweller_level=3,
        special=3,
        site_id="vault_69",
        male_dwellers=1,
        female_dwellers=99,
    ),
)


class ScenarioVaultService:
    def list(self) -> list[VaultScenario]:
        return list(VAULT_SCENARIOS)

    def get(self, key: str) -> VaultScenario | None:
        return next((scenario for scenario in VAULT_SCENARIOS if scenario.key == key), None)

    async def seed(self, db_session: AsyncSession, vault: Vault, scenario: VaultScenario) -> ExpeditionScenarioResult:
        result = await expedition_scenario_service.setup(
            db_session,
            vault_id=vault.id,
            dweller_level=scenario.dweller_level,
            duration_hours=scenario.duration_hours,
            special=scenario.special,
            all_sites=scenario.all_sites,
            single_scene_only=scenario.single_scene_only,
            scenario_site_id=scenario.site_id,
            choice_only=scenario.choice_only,
        )
        if scenario.male_dwellers is not None and scenario.female_dwellers is not None:
            await self._seed_population(db_session, result, scenario.male_dwellers, scenario.female_dwellers)
            await db_session.commit()
            await db_session.refresh(result.vault)
        return result

    @staticmethod
    async def _seed_population(
        db_session: AsyncSession,
        result: ExpeditionScenarioResult,
        male_dwellers: int,
        female_dwellers: int,
    ) -> None:
        """Fill a scenario vault to its authored gender split and expand its population cap."""
        target_total = male_dwellers + female_dwellers
        await db_session.refresh(result.vault)
        current = list(await crud.dweller.get_multi_by_vault(db_session, result.vault.id, limit=target_total + 1))
        majority = GenderEnum.MALE if male_dwellers >= female_dwellers else GenderEnum.FEMALE
        for dweller in current:
            if dweller.id == result.dweller.id or dweller.gender == majority:
                continue
            await crud.dweller.update(db_session, dweller.id, {"gender": majority})
            dweller.gender = majority
        male_count = sum(dweller.gender == GenderEnum.MALE for dweller in current)
        female_count = len(current) - male_count
        for gender, missing in (
            (GenderEnum.MALE, male_dwellers - male_count),
            (GenderEnum.FEMALE, female_dwellers - female_count),
        ):
            for _ in range(max(0, missing)):
                await dweller_service.create_random_dweller(
                    db_session,
                    result.vault.id,
                    DwellerCreateCommonOverride(gender=gender),
                )
        await db_session.refresh(result.vault)
        result.vault.population_max = max(result.vault.population_max or 0, target_total)
        db_session.add(result.vault)


scenario_vault_service = ScenarioVaultService()
