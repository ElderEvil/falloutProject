"""Pet CRUD operations."""

from app.crud.item_base import CRUDItem
from app.models.pet import Pet

pet = CRUDItem(Pet)
