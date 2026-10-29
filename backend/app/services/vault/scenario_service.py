"""Catalog of opt-in scenario starts for newly created vaults."""

from dataclasses import dataclass

from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import GenderEnum
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreateCommonOverride
from app.services.dweller_service import dweller_service
from app.services.exploration.expedition_scenario_service import expedition_scenario_service


@dataclass(frozen=True)
class VaultScenario:
    """One opt-in start: either a scout expedition or a population experiment."""

    number: int
    key: str
    title: str
    description: str
    requires_boosted: bool = False
    expedition: bool = False
    dweller_level: int = 5
    special: int = 5
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
        expedition=True,
        dweller_level=5,
        special=4,
    ),
    VaultScenario(
        number=68,
        key="vault_68_test",
        title="Vault 68 — The Ratio",
        description=(
            "99 men and 1 woman: a Vault-Tec gender-ratio experiment. Requires Boosted Start; "
            "no expedition scout. Starter objectives skipped."
        ),
        requires_boosted=True,
        male_dwellers=99,
        female_dwellers=1,
    ),
    VaultScenario(
        number=69,
        key="vault_69_test",
        title="Vault 69 — 99 Women, 1 Man",
        description=(
            "99 women and 1 man: a Vault-Tec gender-ratio experiment. Requires Boosted Start; "
            "no expedition scout. Starter objectives skipped."
        ),
        requires_boosted=True,
        male_dwellers=1,
        female_dwellers=99,
    ),
)


class VaultScenarioService:
    def list(self) -> list[VaultScenario]:
        return list(VAULT_SCENARIOS)

    def get(self, key: str) -> VaultScenario | None:
        return next((scenario for scenario in VAULT_SCENARIOS if scenario.key == key), None)

    async def seed(self, db_session: AsyncSession, vault: Vault, scenario: VaultScenario) -> None:
        if scenario.expedition:
            await expedition_scenario_service.setup(
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
            await self._seed_population(db_session, vault, scenario.male_dwellers, scenario.female_dwellers)
            await db_session.commit()
            await db_session.refresh(vault)

    @staticmethod
    async def _seed_population(
        db_session: AsyncSession,
        vault: Vault,
        male_dwellers: int,
        female_dwellers: int,
    ) -> None:
        """Fill a scenario vault to its authored gender split and expand its population cap."""
        target_total = male_dwellers + female_dwellers
        await db_session.refresh(vault)
        current = list(await crud.dweller.get_multi_by_vault(db_session, vault.id, limit=target_total + 1))
        majority = GenderEnum.MALE if male_dwellers >= female_dwellers else GenderEnum.FEMALE
        for dweller in current:
            if dweller.gender == majority:
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
                    vault.id,
                    DwellerCreateCommonOverride(gender=gender),
                )
        await db_session.refresh(vault)
        vault.population_max = max(vault.population_max or 0, target_total)
        db_session.add(vault)


vault_scenario_service = VaultScenarioService()
