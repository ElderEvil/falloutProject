"""Reward item and dweller grants.

Item rewards materialize catalog-backed weapons/outfits/junk/pets through
``app.utils.item_factory`` — the only sanctioned constructors for those models —
and mint dwellers from named templates or procedural stats. ``grant_item``
routes dweller and medication rewards before touching storage, so treatment
stock and population capacity are handled on the same paths as the original
``RewardService``. Public entry points are called through the facade in
``app.services.reward_service``.
"""

import logging
import random
from typing import Any

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import RarityEnum
from app.core.event_bus import GameEvent, event_bus
from app.crud.storage import get_available_space
from app.crud.storage import storage as storage_crud
from app.models.dweller import Dweller
from app.models.quest_reward import RewardType
from app.models.storage import Storage
from app.services.rewards.resources import _medication_kind, grant_radaway, grant_stimpak
from app.services.user_service import user_service
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException
from app.utils.item_factory import build_item, build_outfit, build_weapon
from app.utils.reward_delivery import persist_reward_change, reward_delivery_is_deferred
from app.utils.storage_policy import is_nuka_cola_consumable

logger = logging.getLogger(__name__)


def _parse_quantity(data: dict[str, Any]) -> int:
    raw = data.get("quantity", data.get("amount", 1))
    try:
        qty = int(raw)
    except (TypeError, ValueError):
        qty = 1
    return max(1, qty)


async def _ensure_storage(db_session: AsyncSession, vault_id: UUID4, quantity: int):
    storage_obj = await storage_crud.get_by_vault(db_session, vault_id)
    if not storage_obj:
        raise ResourceNotFoundException(Storage, vault_id, identifier_type="vault_id")
    available = await get_available_space(db_session, storage_obj.id)
    if available < quantity:
        raise ResourceConflictException(f"Storage full for vault {vault_id}: need {quantity}, available {available}")
    return storage_obj


async def _pick_legendary_template_id(db_session: AsyncSession, vault_id: UUID4) -> str | None:
    """Pick an unused legendary template id; None when the vault exhausted them."""
    from app.crud.dweller import dweller as dweller_crud
    from app.utils.static_data import game_data_store

    active_names = await dweller_crud.lock_vault_for_template(db_session, vault_id)
    template = game_data_store.pick_template(RarityEnum.LEGENDARY.value, exclude_names=active_names or None)
    return template.template_id if template is not None else None


def _fallback_legendary_identity() -> dict[str, Any]:
    """Canonical name/rarity for the exhausted-pool fallback.

    Omits template_id on purpose: grant_dweller then rolls procedural stats
    while keeping a canonical legendary name and rarity.
    """
    from app.utils.static_data import game_data_store

    template = game_data_store.pick_template(RarityEnum.LEGENDARY.value)
    if template is None:
        return {}
    return {
        "first_name": template.first_name,
        "last_name": template.last_name,
        "rarity": template.rarity,
    }


async def _grant_as_dweller(
    db_session: AsyncSession, vault_id: UUID4, item_name: str, rarity: str, quantity: int
) -> dict[str, Any]:
    first_name, _, last_name = item_name.strip().partition(" ")
    dweller_template = {
        "rarity": rarity,
        "level": 1,
        "first_name": first_name or "Legendary",
        "last_name": last_name or None,
    }
    legendary = item_name.strip().lower() == "legendary dweller"
    dweller_ids: list[str] = []
    last_name: str | None = None
    for _ in range(quantity):
        if legendary and (template_id := await _pick_legendary_template_id(db_session, vault_id)):
            result = await grant_dweller(db_session, vault_id, {"template_id": template_id})
        else:
            payload = dweller_template
            if legendary:
                payload = {**dweller_template, **_fallback_legendary_identity()}
            result = await grant_dweller(db_session, vault_id, payload)
        dweller_ids.append(result["dweller_id"])
        last_name = result["name"]
    logger.info(f"Granted {quantity} dweller(s) '{item_name}' ({rarity}) to vault {vault_id}")
    return {
        "reward_type": RewardType.ITEM,
        "item_type": "dweller",
        "name": last_name or item_name,
        "amount": quantity,
        "dweller_ids": dweller_ids,
        "dweller_id": dweller_ids[0] if dweller_ids else None,
    }


def _build_weapon(name: str, rarity: str, data: dict[str, Any], storage_id: UUID4):
    """Prefer the catalog weapon so stats and metadata are canonical."""
    from app.services import catalog_service as data_loader
    from app.utils.item_factory import build_catalog_item

    catalog_weapon = build_catalog_item(
        "weapon", name, rarity, storage_id, weapons_data=data_loader.load_weapons(), outfits_data=[]
    )
    if catalog_weapon is not None:
        return catalog_weapon
    logger.warning(f"Reward weapon '{name}' is not in the catalog; building a default row")
    return build_weapon(data | {"name": name}, rarity, storage_id)


def _build_outfit(name: str, rarity: str, data: dict[str, Any], storage_id: UUID4):
    """Prefer the catalog outfit so SPECIAL bonuses and metadata are kept."""
    from app.services import catalog_service as data_loader
    from app.utils.item_factory import build_catalog_item

    catalog_outfit = build_catalog_item(
        "outfit", name, rarity, storage_id, weapons_data=[], outfits_data=data_loader.load_outfits()
    )
    if catalog_outfit is not None:
        return catalog_outfit
    logger.warning(f"Reward outfit '{name}' is not in the catalog; building a default row")
    return build_outfit(data | {"name": name}, rarity, storage_id)


def _build_junk(name: str, rarity: str, data: dict[str, Any], storage_id: UUID4):
    from app.core.enums import JunkTypeEnum
    from app.utils.item_factory import build_junk
    from app.utils.junk_assets import get_junk_image_url

    return build_junk(
        name,
        rarity,
        storage_id,
        value=data.get("value"),
        description=data.get("description", name),
        junk_type=data.get("junk_type", JunkTypeEnum.VALUABLES),
        image_url=data.get("image_url") or get_junk_image_url(name),
    )


def _build_pet(name: str, rarity: str, data: dict[str, Any], storage_id: UUID4):
    """Build a Pet; bonuses resolve by name at read time, so only identity/art are persisted."""
    from app.utils.item_factory import build_pet

    return build_pet(data | {"name": name}, rarity, storage_id)


async def grant_item(
    db_session: AsyncSession, vault_id: UUID4, item_data: dict[str, Any], *, emit_event: bool = True
) -> dict[str, Any]:
    from app.schemas.quest import infer_item_type

    quantity = _parse_quantity(item_data)
    item_name = item_data.get("item_name", item_data.get("name", "Unknown Item"))
    item_rarity = item_data.get("rarity", "common")
    item_type = infer_item_type(str(item_name), item_data)

    if item_type == "dweller":
        return await _grant_as_dweller(db_session, vault_id, str(item_name), str(item_rarity), quantity)

    # Medication rides the dweller-stock path so it stays usable for treatment;
    # generic Item rows would be inert (treatment spends carried stock).
    if _medication_kind(str(item_name)) == "stimpak":
        return await grant_stimpak(db_session, vault_id, quantity, emit_event=emit_event)
    if _medication_kind(str(item_name)) == "radaway":
        return await grant_radaway(db_session, vault_id, quantity, emit_event=emit_event)

    if item_type not in {"weapon", "outfit", "junk", "consumable", "lunchbox", "pet"}:
        raise ValueError(f"Unsupported item_type: {item_type}")
    # Space-free by design (app.utils.storage_policy): bottles live in storage
    # but occupy no slot, so a full vault must not reject them.
    space_required = 0 if is_nuka_cola_consumable(item_type, item_name) else quantity
    storage_obj = await _ensure_storage(db_session, vault_id, space_required)
    created_ids: list[str] = []
    for _ in range(quantity):
        match item_type:
            case "weapon":
                item = _build_weapon(str(item_name), str(item_rarity), item_data, storage_obj.id)
            case "outfit":
                item = _build_outfit(str(item_name), str(item_rarity), item_data, storage_obj.id)
            case "junk":
                item = _build_junk(str(item_name), str(item_rarity), item_data, storage_obj.id)
            case "pet":
                item = _build_pet(str(item_name), str(item_rarity), item_data, storage_obj.id)
            case _:
                item = build_item(
                    str(item_name),
                    item_type,
                    str(item_rarity),
                    storage_obj.id,
                    value=item_data.get("value"),
                    image_url=item_data.get("image_url"),
                )
        db_session.add(item)
        await db_session.flush()
        await db_session.refresh(item)
        created_ids.append(str(item.id))

    await persist_reward_change(db_session)

    if emit_event and not reward_delivery_is_deferred(db_session):
        await event_bus.emit(GameEvent.ITEM_COLLECTED, vault_id, {"item_type": item_type, "amount": quantity})
    logger.info(f"Granted {quantity}x {item_type} '{item_name}' ({item_rarity}) to vault {vault_id}")
    return {
        "reward_type": RewardType.ITEM,
        "item_type": item_type,
        "name": item_name,
        "amount": quantity,
        "item_id": created_ids[0] if len(created_ids) == 1 else None,
        "item_ids": created_ids,
    }


async def grant_dweller(db_session: AsyncSession, vault_id: UUID4, dweller_template: dict[str, Any]) -> dict[str, Any]:
    from app.core.enums import RarityEnum
    from app.crud.vault import vault as vault_crud
    from app.schemas.dweller import STATS_RANGE_BY_RARITY
    from app.utils.static_data import game_data_store

    vault, population = await vault_crud.lock_population_for_update(db_session, vault_id)
    if vault_crud.population_limit_reached(vault.population_max, population):
        raise ResourceConflictException(f"Vault population capacity reached ({population}/{vault.population_max})")

    if template_id := dweller_template.get("template_id"):
        template = game_data_store.get_dweller(template_id)
        if template is None:
            msg = f"Unknown dweller reward template: {template_id}"
            raise ValueError(msg)
        from app.services.dweller_service import dweller_service

        try:
            new_dweller = await dweller_service.create_dweller_from_template(
                db_session,
                vault_id,
                template_id,
                overrides=dweller_template,
            )
        except ResourceConflictException:
            fallback = await dweller_service.create_random_dweller(
                db_session, vault_id=vault_id, rarity=RarityEnum.COMMON, register_bio_places=True
            )
            logger.info(
                f"Template {template_id} already active in vault {vault_id}, granted fallback common {fallback.id}"
            )
            return {
                "reward_type": RewardType.DWELLER,
                "dweller_id": str(fallback.id),
                "name": f"{fallback.first_name} {fallback.last_name or ''}".strip(),
            }
        logger.info(f"Granted dweller '{new_dweller.first_name}' ({new_dweller.rarity}) to vault {vault_id}")
        return {
            "reward_type": RewardType.DWELLER,
            "dweller_id": str(new_dweller.id),
            "name": f"{new_dweller.first_name} {new_dweller.last_name or ''}".strip(),
        }

    first_name = dweller_template.get("first_name", dweller_template.get("name", "Unknown"))
    last_name = dweller_template.get("last_name")
    rarity = dweller_template.get("rarity", "common")
    level = dweller_template.get("level", 1)
    gender = dweller_template.get("gender", "male")

    rarity_enum = RarityEnum(rarity)

    stat_range = STATS_RANGE_BY_RARITY.get(rarity_enum, (1, 3))
    default_stat = random.randint(stat_range[0], stat_range[1])

    new_dweller = Dweller(
        first_name=first_name,
        last_name=last_name,
        gender=gender,
        rarity=rarity_enum,
        level=level,
        experience=dweller_template.get("experience", 0),
        max_health=dweller_template.get("max_health", 50),
        health=dweller_template.get("health", 50),
        happiness=dweller_template.get("happiness", 50),
        strength=dweller_template.get("strength", default_stat),
        perception=dweller_template.get("perception", default_stat),
        endurance=dweller_template.get("endurance", default_stat),
        charisma=dweller_template.get("charisma", default_stat),
        intelligence=dweller_template.get("intelligence", default_stat),
        agility=dweller_template.get("agility", default_stat),
        luck=dweller_template.get("luck", default_stat),
        bio=dweller_template.get("bio"),
        visual_attributes=dweller_template.get("visual_attributes"),
        vault_id=vault_id,
    )
    await persist_reward_change(db_session, new_dweller, refresh=True)
    await user_service.record_vault_statistic(
        db_session, vault_id, "total_dwellers_created", commit=not reward_delivery_is_deferred(db_session)
    )

    logger.info(f"Granted dweller '{first_name}' ({rarity}) to vault {vault_id}")
    return {
        "reward_type": RewardType.DWELLER,
        "dweller_id": str(new_dweller.id),
        "name": f"{first_name} {last_name or ''}".strip(),
    }
