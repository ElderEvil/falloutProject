from sqlmodel import Field, SQLModel

from Game.Vault.utilities.Person import Person


class DwellerInventory(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    stimpak: int = Field(default=0, ge=0, le=25)
    radaway: int = Field(default=0, ge=0, le=25)
    inventory: dict = Field(default_factory=dict)


class DwellerDataBase(Person, SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    level: int = Field(default=1, ge=1, le=50)
    experience: int = 0
    max_health: int = 0
    health: int = 0
    happiness: int = Field(default=50, ge=10, le=100)
    is_adult: bool = True
