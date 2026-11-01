"""Starter objective dweller rewards must resolve to curated resident profiles."""

from app.core.enums import RewardType
from app.schemas.objective import ObjectiveCreate
from app.services.rewards.settlement import _parse_objective_reward
from app.utils.static_data import DATA_DIR, StaticGameData


def test_every_starter_dweller_reward_has_a_named_profile() -> None:
    objectives = StaticGameData.load_data(DATA_DIR / "objectives/starter.json", ObjectiveCreate)
    dweller_rewards = [objective.reward for objective in objectives if objective.reward.startswith("dweller:")]

    assert dweller_rewards
    for reward in dweller_rewards:
        reward_type, profile = _parse_objective_reward(reward)
        assert reward_type is RewardType.DWELLER
        assert profile["first_name"]
        assert profile["last_name"]
        assert profile["bio"]
        assert profile["visual_attributes"]
