"""Site intel: derived check profiles couriers use to pick the right dweller."""

from app.schemas.expedition import (
    EnemySpec,
    NodeBranch,
    NodeOption,
    SiteDefinition,
    SiteNode,
    SiteRoom,
)
from app.services import catalog_service as data_loader
from app.services.exploration.site_intel import intel_phrase, site_intel


def make_site(*nodes: SiteNode, encounter: bool = False) -> SiteDefinition:
    def room(index: int, node: SiteNode) -> SiteRoom:
        return SiteRoom(id=f"room{index}", name=f"Room {index}", flavor="...", node=node)

    if encounter:
        return SiteDefinition(
            id="test_site",
            name="Test Site",
            flavor="...",
            coord_x=10,
            coord_y=10,
            min_dweller_level=1,
            encounter=room(1, nodes[0]),
            reward_vault={"caps_min": 0, "caps_max": 0},
        )
    return SiteDefinition(
        id="test_site",
        name="Test Site",
        flavor="...",
        coord_x=10,
        coord_y=10,
        min_dweller_level=1,
        rooms=[room(i + 1, node) for i, node in enumerate(nodes)],
        reward_vault={"caps_min": 0, "caps_max": 0},
    )


def option(option_id: str, stat: str, difficulty: int, *, bloodless: bool) -> NodeOption:
    combat = [EnemySpec(name="Raider", power=1, health=1)] if not bloodless else None
    return NodeOption(
        id=option_id,
        label=f"Option {option_id}",
        stat=stat,
        difficulty=difficulty,
        success=NodeBranch(),
        failure=NodeBranch(combat_enemies=combat),
    )


def test_choice_options_advertise_checks():
    site = make_site(
        SiteNode(kind="choice", prompt="...", options=[option("a", "charisma", 3, bloodless=True)])
    )
    intel = site_intel(site, spatial=True)
    assert [(check.stat, check.difficulty) for check in intel.checks] == [("charisma", 3)]
    assert intel.checks[0].bloodless is True
    assert intel.negotiable is True


def test_combat_failure_marks_option_and_blocks_negotiable():
    site = make_site(
        SiteNode(kind="choice", prompt="...", options=[option("a", "guns", 4, bloodless=False)])
    )
    intel = site_intel(site, spatial=True)
    assert intel.checks[0].bloodless is False
    assert intel.negotiable is False


def test_dedupes_checks_across_rooms():
    site = make_site(
        SiteNode(kind="choice", prompt="...", options=[option("a", "charisma", 3, bloodless=True)]),
        SiteNode(kind="choice", prompt="...", options=[option("b", "charisma", 3, bloodless=True)]),
    )
    intel = site_intel(site, spatial=False)
    assert len(intel.checks) == 1


def test_combat_room_blocks_negotiable_despite_bloodless_option():
    site = make_site(
        SiteNode(kind="choice", prompt="...", options=[option("a", "charisma", 3, bloodless=True)]),
        SiteNode(kind="combat", prompt="...", enemies=[EnemySpec(name="Ghoul", power=1, health=1)]),
    )
    intel = site_intel(site, spatial=False)
    assert intel.negotiable is False


def test_finale_terminal_is_advertised():
    site = make_site(
        SiteNode(kind="finale", prompt="...", stat="intelligence", difficulty=4)
    )
    intel = site_intel(site, spatial=True)
    assert [(check.stat, check.difficulty, check.label) for check in intel.checks] == [
        ("intelligence", 4, "Terminal")
    ]
    # Nothing to fight at all, so the pass is bloodless by definition.
    assert intel.negotiable is True


def test_spatial_uses_encounter_legacy_uses_rooms():
    encounter_only = make_site(
        SiteNode(kind="choice", prompt="...", options=[option("a", "luck", 2, bloodless=True)]),
        encounter=True,
    )
    assert [check.stat for check in site_intel(encounter_only, spatial=True).checks] == ["luck"]

    # Spatial without an encounter falls back to the legacy rooms content.
    legacy = make_site(
        SiteNode(kind="choice", prompt="...", options=[option("a", "perception", 5, bloodless=True)]),
    )
    legacy.encounter = None
    assert [check.stat for check in site_intel(legacy, spatial=True).checks] == ["perception"]


def test_intel_phrase_variants():
    site = make_site(
        SiteNode(kind="choice", prompt="...", options=[option("a", "charisma", 3, bloodless=True)])
    )
    assert "CHARISMA 3" in intel_phrase(site_intel(site, spatial=True))
    assert "without a shot" in intel_phrase(site_intel(site, spatial=True))
    assert intel_phrase(site_intel(make_site(
        SiteNode(kind="combat", prompt="...", enemies=[EnemySpec(name="Raider", power=1, health=1)])
    ), spatial=True)) is None


def test_catalog_sites_all_advertise_sane_intel():
    """Content-quality net: every playable catalog site projects a sane profile."""
    for site in data_loader.load_expedition_sites():
        intel = site_intel(site, spatial=True)
        for check in intel.checks:
            assert 1 <= check.difficulty <= 5
            assert check.stat
            assert check.label
            assert isinstance(check.bloodless, bool)
