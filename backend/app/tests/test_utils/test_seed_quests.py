import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.enums import RequirementType
from app.models.quest import Quest
from app.models.quest_requirement import QuestRequirement
from app.models.quest_reward import QuestReward
from app.schemas.quest import QuestJSON, QuestRewardJSON
from app.seeding.load_quests import load_all_quest_chain_files, load_quest_chain_from_json
from app.seeding.seed_quests import seed_quests_from_json
from app.utils.static_data import game_data_store

_LEVEL_GATE_RE = re.compile(r"level\s+(\d+)", re.IGNORECASE)
_PREDECESSOR_RE = re.compile(r"complete\s+['\"](.+?)['\"]\s+quest", re.IGNORECASE)


def _dir(tmp_path: Path, name: str = "quests") -> Path:
    path = tmp_path / name
    path.mkdir()
    return path


def _write(directory: Path, name: str, data) -> None:
    (directory / name).write_text(json.dumps(data), encoding="utf-8")


def _quest(name: str = "Test Quest", **overrides) -> dict:
    base = {
        "quest_name": name,
        "long_description": "A test quest.",
        "short_description": "Test",
        "requirements": "Level 1",
        "rewards": "10 caps",
        "quest_objective": "Do it",
    }
    return base | overrides


def _item_reward(item_name: str, **item_data) -> dict:
    payload = {"reward_type": "ITEM", "reward_data": {"item_name": item_name, "quantity": 1}}
    return payload | ({"item_data": item_data} if item_data else {})


CHAIN = {
    "chain_name": "Test chain",
    "quests": [
        _quest("Chain Starter", long_description="The first quest in a test chain.", short_description="Start"),
        _quest(
            "Chain Follow-up",
            long_description="The second quest in a test chain.",
            short_description="Continue",
            rewards="20 caps",
            quest_requirements=[
                {"requirement_type": "QUEST_COMPLETED", "requirement_data": {"quest_name": "Chain Starter"}}
            ],
        ),
    ],
}


def _seed_one(tmp_path: Path, quest: dict, name: str = "quests") -> Path:
    directory = _dir(tmp_path, name)
    _write(directory, "quests.json", {"quests": [quest]})
    return directory


async def _seed(session: AsyncSession, directory: Path) -> int:
    return await seed_quests_from_json(session, quest_dir=directory)


async def _quest_row(session: AsyncSession, title: str) -> Quest:
    return (await session.execute(select(Quest).where(Quest.title == title))).scalar_one()


async def _rewards(session: AsyncSession, quest: Quest) -> list[QuestReward]:
    return list((await session.execute(select(QuestReward).where(QuestReward.quest_id == quest.id))).scalars().all())


async def _requirements(session: AsyncSession, quest: Quest) -> list[QuestRequirement]:
    rows = await session.execute(select(QuestRequirement).where(QuestRequirement.quest_id == quest.id))
    return list(rows.scalars().all())


@pytest.mark.parametrize("file_format", ["single", "list", "chain"])
def test_quest_loader_preserves_supported_formats_and_filename_defaults(tmp_path, file_format):
    quest = {
        "Quest name": "Supply Run",
        "Short description": "Gather supplies",
        "Requirements": ["Level 1"],
        "Quest objective": "Return safely",
        "duration_minutes": 30,
    }
    data = {"quests": [quest]} if file_format == "chain" else ([quest] if file_format == "list" else quest)
    path = tmp_path / "supply_runs.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    chain = load_quest_chain_from_json(str(path))
    assert chain.title == "Supply Runs"
    assert chain.chain_id is None
    assert chain.chain_description is None
    assert len(chain.quests) == 1
    if file_format == "chain":
        _write(
            tmp_path,
            "supplies.json",
            {
                "chain_name": "The Supply Line",
                "chain_id": "supply-line",
                "chain_description": "A two-part expedition",
                "quests": [{"quest_name": "First"}, {"quest_name": "Second"}],
            },
        )
        meta = load_quest_chain_from_json(str(tmp_path / "supplies.json"))
        assert (meta.title, meta.chain_id, meta.chain_description) == (
            "The Supply Line",
            "supply-line",
            "A two-part expedition",
        )
        assert [quest.quest_name for quest in meta.quests] == ["First", "Second"]
    loaded = chain.quests[0]
    assert loaded.quest_name == "Supply Run"
    assert loaded.short_description == "Gather supplies"
    assert loaded.requirements == ["Level 1"]
    assert loaded.quest_objective == "Return safely"
    assert loaded.duration_minutes == 30


@pytest.mark.parametrize("file_format", ["single", "list", "chain"])
def test_quest_loader_rejects_invalid_nested_quest_data(tmp_path, file_format):
    quest = {"quest_name": "Invalid", "duration_minutes": 1}
    data = {"quests": [quest]} if file_format == "chain" else ([quest] if file_format == "list" else quest)
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValidationError, match="duration_minutes"):
        load_quest_chain_from_json(str(path))


@pytest.mark.parametrize(
    ("field", "alias"),
    [
        ("quest_name", "Quest name"),
        ("long_description", "Long description"),
        ("short_description", "Short description"),
        ("requirements", "Requirements"),
        ("rewards", "Rewards"),
        ("quest_objective", "Quest objective"),
    ],
)
def test_quest_json_accepts_both_aliases_and_prefers_snake_case(field, alias):
    spaced = QuestJSON.model_validate({alias: "spaced"})
    snake = QuestJSON.model_validate({field: "snake", alias: "spaced"})
    assert getattr(spaced, field) == "spaced"
    assert getattr(snake, field) == "snake"
    assert snake.model_dump(by_alias=True)[alias] == "snake"


LEGACY_TITLES = [
    ({}, "Legacy title"),
    ({"Quest name": "Spaced"}, "Spaced"),
    ({"quest_name": "Snake", "Quest name": "Spaced"}, "Snake"),
    ({"quest_name": "", "Quest name": "Spaced"}, "Legacy title"),
    ({"quest_name": None}, "Legacy title"),
    ({"Quest name": ""}, "Legacy title"),
]


def test_quest_json_preserves_legacy_title_fallback():
    for names, expected in LEGACY_TITLES:
        assert QuestJSON.model_validate({"title": "Legacy title", **names}).quest_name == expected


def test_quest_display_requirements_never_advertise_unenforced_gates() -> None:
    violations: list[str] = []
    for chain in load_all_quest_chain_files():
        for quest in chain.quests:
            display_lines = quest.requirements if isinstance(quest.requirements, list) else [quest.requirements]
            enforced_levels = {
                req.requirement_data.get("level")
                for req in quest.quest_requirements
                if req.requirement_type.upper() == "LEVEL" and req.is_mandatory
            }
            enforced_predecessors = {
                req.requirement_data.get("quest_name")
                for req in quest.quest_requirements
                if req.requirement_type.upper() == "QUEST_COMPLETED" and req.is_mandatory
            }
            for line in display_lines:
                for match in _LEVEL_GATE_RE.finditer(line):
                    level = int(match.group(1))
                    if level not in enforced_levels:
                        violations.append(
                            f"{quest.quest_name}: advertises 'Level {level}' without an enforced LEVEL gate"
                        )
                for match in _PREDECESSOR_RE.finditer(line):
                    predecessor = match.group(1).strip()
                    if predecessor not in enforced_predecessors:
                        violations.append(f"{quest.quest_name}: advertises '{predecessor}' without an enforced gate")
    assert not violations, "Quest display text advertises gates that are not enforced:\n" + "\n".join(violations)


def test_quest_item_reward_validation() -> None:
    reward = QuestRewardJSON.model_validate(
        {"reward_type": "ITEM", "reward_data": {"item_name": "Nuka-Cola Quantum", "amount": "2"}}
    )
    assert reward.reward_data["quantity"] == 2
    for quantity in ("two", 2.5):
        with pytest.raises(ValidationError, match="quantity"):
            QuestRewardJSON.model_validate(
                {"reward_type": "ITEM", "reward_data": {"item_name": "Nuka-Cola Quantum", "quantity": quantity}}
            )
    with pytest.raises(ValidationError, match="item_type"):
        QuestRewardJSON.model_validate(_item_reward("Mystery Item", item_type="armor", name="Mystery Item"))
    authored = QuestRewardJSON.model_validate(
        _item_reward("Assault rifle", name="Assault rifle", item_type="weapon", image_url="/custom/art.png")
    )
    assert authored.item_data is not None
    assert authored.item_data.image_url == "/custom/art.png"
    for name in ("Nuka-Cola Quantum", "Lunchbox", "Legendary Dweller"):
        photo_less = QuestRewardJSON.model_validate(_item_reward(name))
        assert photo_less.item_data is not None
        assert photo_less.item_data.image_url is None


@pytest.mark.parametrize(
    ("name", "item_type", "image_url"),
    [
        ("Assault rifle", "weapon", "/static/weapon_images/Assault Rifle FOS.png"),
        ("Hazmat suit", "outfit", "/static/apparel_images/FOS Rad Suit.png"),
        ("CX404", "pet", "/static/pet_images/FOS CX404.png"),
        ("Teddy bear", "junk", "/static/junk_images/FOS Teddy bear.png"),
    ],
)
def test_quest_item_reward_fills_catalog_art_at_parse(name: str, item_type: str, image_url: str) -> None:
    reward = QuestRewardJSON.model_validate(_item_reward(name))
    assert reward.item_data is not None
    assert reward.item_data.item_type == item_type
    assert reward.item_data.image_url == image_url


REWARD_PAYLOAD_CASES = [
    (
        "Mutable Reward Quest",
        lambda quests: quests[0]["quest_rewards"][0].update(reward_data={"amount": 250}),
        [("caps", {"amount": 250})],
    ),
    (
        "Expanding Reward Quest",
        lambda quests: quests[0]["quest_rewards"].append({"reward_type": "STIMPAK", "reward_data": {"quantity": 2}}),
        [("caps", {"amount": 100}), ("stimpak", {"quantity": 2})],
    ),
]


@pytest.mark.asyncio
async def test_seed_quests_rewrites_reward_rows(async_session: AsyncSession, tmp_path: Path) -> None:
    backfill_dir = _seed_one(
        tmp_path,
        _quest("Backfill Art Quest", rewards="Assault rifle", quest_rewards=[_item_reward("Assault rifle")]),
        "backfill",
    )
    await _seed(async_session, backfill_dir)
    backfill = await _quest_row(async_session, "Backfill Art Quest")
    reward = (await _rewards(async_session, backfill))[0]
    # Simulate a row seeded before the enrichment existed.
    reward.item_data = {"name": "Assault rifle", "item_type": "weapon", "rarity": "common"}
    await async_session.commit()
    assert await _seed(async_session, backfill_dir) == 0
    assert ((await _rewards(async_session, backfill))[0].item_data or {})["image_url"] == (
        "/static/weapon_images/Assault Rifle FOS.png"
    )

    item_data = {"item_type": "outfit", "name": "Vault Suit", "rarity": "rare"}
    item = {"reward_type": "ITEM", "reward_data": {"item_name": "Vault Suit", "quantity": 1}, "item_data": item_data}
    update_dir = _seed_one(
        tmp_path, _quest("Existing Reward Quest", rewards="Vault Suit", quest_rewards=[item]), "update"
    )
    existing = Quest(
        title="Existing Reward Quest",
        short_description="Test",
        long_description="A test quest.",
        requirements="Level 1",
        rewards="Vault Suit",
    )
    async_session.add(existing)
    await async_session.flush()
    async_session.add(
        QuestReward(quest_id=existing.id, reward_type="item", reward_data={"item_name": "Vault Suit", "quantity": 1})
    )
    await async_session.commit()
    assert await _seed(async_session, update_dir) == 0
    assert (await _rewards(async_session, existing))[0].item_data == item_data

    for title, mutate, expected in REWARD_PAYLOAD_CASES:
        quests = [
            _quest(title, rewards="100 caps", quest_rewards=[{"reward_type": "CAPS", "reward_data": {"amount": 100}}])
        ]
        payload_dir = _seed_one(tmp_path, quests[0], title)
        await _seed(async_session, payload_dir)
        mutate(quests)
        _write(payload_dir, "quests.json", {"quests": quests})
        assert await _seed(async_session, payload_dir) == 0
        quest = await _quest_row(async_session, title)
        assert (
            sorted((reward.reward_type.value, reward.reward_data) for reward in await _rewards(async_session, quest))
            == expected
        )
    duplicate_dir = _dir(tmp_path, "duplicates")
    for chain_id in ("first", "second"):
        _write(
            duplicate_dir,
            f"{chain_id}.json",
            {"chain_id": chain_id, "quests": [{**_quest("Duplicate Quest"), "chain_order": 1}]},
        )
    with pytest.raises(ValueError, match="Duplicate quest_name 'Duplicate Quest'"):
        await _seed(async_session, duplicate_dir)


def test_dweller_quest_rewards_reference_canonical_templates() -> None:
    for chain in game_data_store.quests:
        for quest in chain.quests:
            for reward in quest.quest_rewards:
                if reward.reward_type.upper() == "DWELLER":
                    template_id = reward.reward_data.get("template_id")
                    assert template_id, f"{quest.quest_name} is missing a dweller template_id"
                    assert game_data_store.get_dweller(template_id), f"Unknown template {template_id}"


@pytest.mark.asyncio
async def test_seed_quests_handles_input_edge_cases(async_session: AsyncSession, tmp_path: Path) -> None:
    malformed = _quest(
        "Malformed Predecessor",
        quest_requirements=[{"requirement_type": "QUEST_COMPLETED", "requirement_data": {"quest_id": "not-a-uuid"}}],
    )
    assert await _seed(async_session, _seed_one(tmp_path, malformed)) == 1
    assert await _requirements(async_session, await _quest_row(async_session, "Malformed Predecessor")) == []

    list_quest = _quest(
        "Multi Requirement Quest", requirements=["Level 10 dwellers", "Lucy's vault suit", "The Ghoul's coat"]
    )
    assert await _seed(async_session, _seed_one(tmp_path, list_quest, "list")) == 1
    joined = (await _quest_row(async_session, "Multi Requirement Quest")).requirements
    assert "Level 10 dwellers" in joined
    assert "Lucy's vault suit" in joined
    assert "The Ghoul's coat" in joined
    assert ", " in joined

    errors_dir = _seed_one(tmp_path, _quest("Valid Quest"), "errors")
    (errors_dir / "invalid.json").write_text("{ invalid json }", encoding="utf-8")
    assert await _seed(async_session, errors_dir) >= 1
    assert (await async_session.execute(select(Quest).where(Quest.title == "Valid Quest"))).scalar_one_or_none()
    assert await seed_quests_from_json(async_session, quest_dir=tmp_path / "nonexistent") == 0


@pytest.mark.asyncio
async def test_seed_quests_rollback_on_error(async_session: AsyncSession, tmp_path: Path) -> None:
    quest_dir = _seed_one(tmp_path, _quest())
    with patch.object(async_session, "commit", side_effect=Exception("Database error")):
        assert await _seed(async_session, quest_dir) == 0
    assert len((await async_session.execute(select(Quest))).scalars().all()) == 0


@pytest.mark.asyncio
async def test_seed_quests_reconciles_existing_state(async_session: AsyncSession, tmp_path: Path) -> None:
    gates = [
        {"requirement_type": "LEVEL", "requirement_data": {"level": 5}, "is_mandatory": True},
        {"requirement_type": "ITEM", "requirement_data": {"item_name": "Stimpak"}, "is_mandatory": True},
    ]
    quest_dir = _seed_one(tmp_path, _quest("Reconciled Gates Quest", requirements="Level 5", quest_requirements=gates))
    assert await _seed(async_session, quest_dir) == 1
    quest = await _quest_row(async_session, "Reconciled Gates Quest")
    for requirement in await _requirements(async_session, quest):
        await async_session.delete(requirement)
    async_session.add(
        QuestRequirement(
            quest_id=quest.id, requirement_type=RequirementType.LEVEL, requirement_data={"level": 99}, is_mandatory=True
        )
    )
    await async_session.commit()
    assert await _seed(async_session, quest_dir) == 0
    assert sorted(
        (r.requirement_type.value, r.requirement_data) for r in await _requirements(async_session, quest)
    ) == [
        ("item", {"item_name": "Stimpak"}),
        ("level", {"level": 5}),
    ]
    before_ids = {requirement.id for requirement in await _requirements(async_session, quest)}
    assert await _seed(async_session, quest_dir) == 0
    assert {requirement.id for requirement in await _requirements(async_session, quest)} == before_ids

    chain_dir = _dir(tmp_path, "chains")
    _write(chain_dir, "chain.json", CHAIN)
    assert await _seed(async_session, chain_dir) == 2
    quests = {q.title: q for q in (await async_session.execute(select(Quest))).scalars().all()}
    follow_up, starter = quests["Chain Follow-up"], quests["Chain Starter"]
    assert follow_up.previous_quest_id == starter.id
    # Drop the gate and clear the predecessor link in the DB.
    for requirement in await _requirements(async_session, follow_up):
        await async_session.delete(requirement)
    follow_up.previous_quest_id = None
    await async_session.commit()
    assert await _seed(async_session, chain_dir) == 0
    follow_up = await _quest_row(async_session, "Chain Follow-up")
    requirements = await _requirements(async_session, follow_up)
    assert len(requirements) == 1
    assert requirements[0].requirement_type == RequirementType.QUEST_COMPLETED
    assert requirements[0].requirement_data == {"quest_id": str(starter.id)}
    assert follow_up.previous_quest_id == starter.id


def test_quest_gear_rewards_are_catalog_backed() -> None:
    from app.schemas.quest import infer_item_type
    from app.services import catalog_service as data_loader
    from app.services.rewards.items import _resolve_junk
    from app.utils.static_data import DATA_DIR

    catalog = {
        "weapon": {str(w["name"]).lower() for w in data_loader.load_weapons()},
        "outfit": {str(o["name"]).lower() for o in data_loader.load_outfits()},
        "junk": {str(j["name"]).lower() for j in data_loader.load_junk_items()},
    }

    def walk(node: object) -> None:
        if isinstance(node, dict):
            reward_data = node.get("reward_data") or {}
            item_data = node.get("item_data") if isinstance(node.get("item_data"), dict) else None
            name = reward_data.get("item_name") or (item_data or {}).get("name")
            if name:
                item_type = infer_item_type(str(name), item_data)
                if item_type in catalog and item_type != "junk":
                    assert str(name).lower() in catalog[item_type], f"{name!r} is not a catalog {item_type}"
                if item_type == "junk":
                    # Settle as settlement.py will: normalized payload merged with item_data;
                    # every quest junk reward must resolve to a priced row, never a valueless orphan.
                    parsed = QuestRewardJSON.model_validate(node)
                    merged = parsed.reward_data | (parsed.item_data_json or {})
                    resolved = _resolve_junk(
                        str(merged.get("item_name") or merged.get("name") or name),
                        str(merged.get("rarity", "common")),
                        dict(merged),
                    )[2]
                    assert resolved.get("value") is not None, f"{name!r} settles as a valueless junk row"
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for path in (DATA_DIR / "quests").rglob("*.json"):
        walk(json.loads(path.read_text()))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("chain_id", "quest_count", "final_template"),
    [
        ("almost_human", 4, "harkness"),
        ("climbing_the_ranks", 4, "sarah-lyons"),
        ("a_settler_needs_your_help", 5, "preston-garvey"),
    ],
)
async def test_wasteland_chains_seed_unlock_and_grant_rewards(
    async_session: AsyncSession, vault, dweller, chain_id: str, quest_count: int, final_template: str
) -> None:
    from sqlalchemy.orm import selectinload

    from app import crud
    from app.core.enums import AgeGroupEnum
    from app.models.vault_quest import VaultQuestCompletionLink
    from app.services.progression.quests.availability import quest_availability
    from app.services.reward_service import reward_service
    from app.utils.item_factory import build_weapon

    assert await seed_quests_from_json(async_session) > 0
    quests = list(
        (
            await async_session.execute(
                select(Quest)
                .where(Quest.chain_id == chain_id)
                .options(selectinload(Quest.quest_requirements), selectinload(Quest.quest_rewards))
                .order_by(Quest.chain_order)
            )
        ).scalars()
    )
    assert len(quests) == quest_count
    assert [quest.chain_order for quest in quests] == list(range(1, quest_count + 1))
    requirement_count = len((await async_session.execute(select(QuestRequirement))).scalars().all())
    reward_count = len((await async_session.execute(select(QuestReward))).scalars().all())
    assert await seed_quests_from_json(async_session) == 0
    assert len((await async_session.execute(select(QuestRequirement))).scalars().all()) == requirement_count
    assert len((await async_session.execute(select(QuestReward))).scalars().all()) == reward_count

    dweller.age_group = AgeGroupEnum.ADULT
    dweller.level = 50
    async_session.add(dweller)
    catalog_weapon = next(weapon for weapon in game_data_store.weapons if weapon.name == "Plasma rifle")
    weapon = build_weapon(catalog_weapon.model_dump(), catalog_weapon.rarity)
    weapon.dweller_id = dweller.id
    async_session.add(weapon)
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=vault.id)
    storage.max_space = 100
    async_session.add(storage)
    await async_session.commit()

    for index, quest in enumerate(quests):
        assert quest.previous_quest_id == (quests[index - 1].id if index else None)
        if index + 1 < len(quests):
            blocked = await quest_availability(async_session, vault.id, quests[index + 1], has_office=True)
            assert not blocked.available
        available = await quest_availability(async_session, vault.id, quest, has_office=True)
        assert available.available, available.lock_reason
        assert all(reward.reward_chance == 1.0 for reward in quest.quest_rewards)
        grants = await reward_service.process_quest_rewards(async_session, vault.id, quest)
        assert len(grants) == len(quest.quest_rewards)
        assert all(grant["amount"] > 0 for grant in grants if "amount" in grant)
        async_session.add(VaultQuestCompletionLink(vault_id=vault.id, quest_id=quest.id, is_completed=True))
        await async_session.commit()

    template = game_data_store.get_dweller(final_template)
    recruited = await crud.dweller.get_multi_by_vault(async_session, vault_id=vault.id)
    assert any(
        person.first_name == template.first_name and person.last_name == template.last_name for person in recruited
    )
