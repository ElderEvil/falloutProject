from . import storage
from .dweller import dweller
from .exploration import exploration
from .game_state import game_state_crud
from .incident import incident_crud
from .item_base import CRUDItem
from .llm_interaction import llm_interaction
from .objective import objective_crud
from .pregnancy import pregnancy
from .quest import quest_crud
from .room import room
from .user import user
from .vault import vault
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.weapon import Weapon

# Create CRUD instances directly using CRUDItem
weapon = CRUDItem(Weapon)
outfit = CRUDItem(Outfit)
junk = CRUDItem(Junk)
