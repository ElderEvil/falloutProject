"""Run-to-room selection for expedition sites."""

from app.models.exploration import ExpeditionRun
from app.schemas.expedition import SiteDefinition, SiteRoom
from app.utils.exceptions import ValidationException


def rooms_for_run(site: SiteDefinition, run: ExpeditionRun) -> list[SiteRoom]:
    """Saved runs keep their original cursor; new spatial visits use one encounter."""
    if run.flags.get("single_scene"):
        if site.encounter is None:
            raise ValidationException(f"Missing encounter content for {site.id}")
        return [site.encounter]
    return site.rooms
