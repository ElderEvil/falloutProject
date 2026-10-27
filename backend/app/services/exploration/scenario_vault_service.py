"""Catalog of opt-in scenario starts for newly created vaults."""

from dataclasses import dataclass

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.vault import Vault
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


VAULT_SCENARIOS = (
    VaultScenario(
        number=1,
        key="vault_1_test",
        title="Vault 1 — Scout Test",
        description=(
            "Adds a level 5 / SPECIAL 4 Scout and a single-scene all-sites expedition. Starts at the site picker."
        ),
        dweller_level=5,
        special=4,
    ),
)


class ScenarioVaultService:
    def list(self) -> list[VaultScenario]:
        return list(VAULT_SCENARIOS)

    def get(self, key: str) -> VaultScenario | None:
        return next((scenario for scenario in VAULT_SCENARIOS if scenario.key == key), None)

    async def seed(self, db_session: AsyncSession, vault: Vault, scenario: VaultScenario) -> ExpeditionScenarioResult:
        return await expedition_scenario_service.setup(
            db_session,
            vault_id=vault.id,
            dweller_level=scenario.dweller_level,
            duration_hours=scenario.duration_hours,
            special=scenario.special,
            all_sites=scenario.all_sites,
            single_scene_only=scenario.single_scene_only,
        )


scenario_vault_service = ScenarioVaultService()
