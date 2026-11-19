"""Catalog of opt-in scenario starts for newly created vaults."""

from dataclasses import dataclass

from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import GenderEnum
from app.models.vault import Vault
from app.utils.exceptions import ValidationException


@dataclass(frozen=True)
class VaultScenario:
    """One opt-in start: a scout expedition or a population experiment."""

    number: int
    key: str
    title: str
    description: str
    requires_boosted: bool = False
    default_boosted: bool = False
    default_on: bool = False
    expedition: bool = False
    multi: bool = False
    dwellers: int | None = None
    discover: bool = True
    outbound_hours: int = 8
    dweller_level: int = 5
    special: int = 5
    duration_hours: int = 8
    all_sites: bool = True
    single_scene_only: bool = True
    choice_only: bool = True
    site_id: str | None = None
    majority_gender: GenderEnum | None = None
    ration_divisor: int = 1
    food_water_multiplier: float = 1.0
    variety: bool = False


SHORT_RATIONS_SCENARIO = "vault_67_short_rations"


VAULT_SCENARIOS = (
    VaultScenario(
        number=1,
        key="vault_1_test",
        title="Vault 1 — Wasteland Test",
        description=(
            "One named scout per expedition site, each already "
            "scouting with its site reported in the bell, at mixed levels with varied weapons and pets. "
            "Standard starts with expanded facilities. Starter objectives skipped."
        ),
        default_boosted=True,
        expedition=True,
        multi=True,
        dweller_level=5,
        variety=True,
    ),
    VaultScenario(
        number=67,
        key=SHORT_RATIONS_SCENARIO,
        title="Vault 67 — Short Rations",
        description=(
            "An original experiment. Open with half the usual food and water. "
            "The vault produces 25% less food and water, including room rushes."
        ),
        ration_divisor=2,
        food_water_multiplier=0.75,
    ),
    VaultScenario(
        number=68,
        key="vault_68_test",
        title="Vault 68 — The Ratio",
        description=(
            "Inspired by the Fallout Bible. Start with eight male residents and one female resident. "
            "The nine starter recruits follow the same ratio. Radio recruitment uses 8-to-1 odds."
        ),
        majority_gender=GenderEnum.MALE,
    ),
    VaultScenario(
        number=69,
        key="vault_69_test",
        title="Vault 69 — The Inverse Ratio",
        description=(
            "Inspired by the Fallout Bible. Start with eight female residents and one male resident. "
            "The nine starter recruits follow the same ratio. Radio recruitment uses 8-to-1 odds."
        ),
        majority_gender=GenderEnum.FEMALE,
    ),
)


class VaultScenarioService:
    def list_options(self) -> list[VaultScenario]:
        return list(VAULT_SCENARIOS)

    def get(self, key: str | None) -> VaultScenario | None:
        return next((scenario for scenario in VAULT_SCENARIOS if scenario.key == key), None) if key else None

    def resolve(self, key: str | None, number: int) -> VaultScenario | None:
        if key is None:
            return None
        scenario = self.get(key)
        if scenario is None:
            raise ValidationException(f"Unknown vault scenario: {key}")
        if scenario.number != number:
            raise ValidationException(f"Vault {scenario.number} is required for this scenario")
        return scenario

    async def seed(self, db_session: AsyncSession, vault: Vault, scenario: VaultScenario) -> None:
        from app.services.exploration.expedition_scenario_service import expedition_scenario_service

        if scenario.expedition:
            if scenario.multi:
                await expedition_scenario_service.setup_multi(
                    db_session,
                    vault_id=vault.id,
                    dwellers=scenario.dwellers,
                    dweller_level=scenario.dweller_level,
                    duration_hours=scenario.duration_hours,
                    discover=scenario.discover,
                    outbound_hours=scenario.outbound_hours,
                    variety=scenario.variety,
                )
                await self._raise_population_capacity(db_session, vault)
                await db_session.commit()
            else:
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

    @staticmethod
    async def _raise_population_capacity(db_session: AsyncSession, vault: Vault) -> None:
        """Stage a population cap that keeps every seeded dweller; the caller commits."""
        await db_session.refresh(vault)
        dwellers = await crud.dweller.get_multi_by_vault(db_session, vault.id, limit=1_000)
        if (vault.population_max or 0) >= len(dwellers):
            return
        vault.population_max = len(dwellers)
        db_session.add(vault)


vault_scenario_service = VaultScenarioService()
