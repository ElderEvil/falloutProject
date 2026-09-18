from app.models.outfit import Outfit
from app.models.weapon import Weapon

from . import storage
from .ai_settings import ai_settings
from .crafting_order import crafting_order
from .dweller import dweller
from .exploration import exploration
from .game_state import game_state_crud
from .hazard_team import hazard_team_crud
from .incident import incident_crud
from .incident_participant import incident_participant_crud
from .item_base import CRUDItem
from .junk import junk
from .llm_interaction import llm_interaction
from .objective import objective_crud
from .pregnancy import pregnancy
from .quest import quest_crud
from .room import room
from .user import user
from .vault import vault
from .world_location import world_location

# Create CRUD instances directly using CRUDItem
weapon = CRUDItem(Weapon)
outfit = CRUDItem(Outfit)
