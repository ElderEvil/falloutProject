from datetime import datetime
from uuid import uuid4

from pydantic import UUID4
from sqlmodel import Field, SQLModel


class TimeStampMixin(SQLModel):
    """Store timestamps as naive UTC (no tzinfo).

    The database connection is pinned to UTC, so naive datetimes are treated as UTC.
    """

    created_at: datetime | None = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow},
    )


class BaseUUIDModel(SQLModel):
    id: UUID4 = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )


class SoftDeleteMixin(SQLModel):
    is_deleted: bool = Field(default=False, index=True)
    deleted_at: datetime | None = Field(default=None)

    def soft_delete(self):
        """Marks the object as deleted."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()

    def restore(self):
        """Restores the object if it was soft-deleted."""
        self.is_deleted = False
        self.deleted_at = None


class SPECIALModel(SQLModel):
    strength: int = Field(default=1, ge=1, le=10, alias="S")
    perception: int = Field(default=1, ge=1, le=10, alias="P")
    endurance: int = Field(default=1, ge=1, le=10, alias="E")
    charisma: int = Field(default=1, ge=1, le=10, alias="C")
    intelligence: int = Field(default=1, ge=1, le=10, alias="I")
    agility: int = Field(default=1, ge=1, le=10, alias="A")
    luck: int = Field(default=1, ge=1, le=10, alias="L")

    model_config = {"populate_by_name": True}

    @classmethod
    def format_special_stats(cls, dweller: "SPECIALModel") -> str:
        """Format SPECIAL stats as a comma-separated string for AI prompts."""
        parts: list[str] = []
        for letter in ("S", "P", "E", "C", "I", "A", "L"):
            match letter:
                case "S":
                    parts.append(f"strength: {dweller.strength}")
                case "P":
                    parts.append(f"perception: {dweller.perception}")
                case "E":
                    parts.append(f"endurance: {dweller.endurance}")
                case "C":
                    parts.append(f"charisma: {dweller.charisma}")
                case "I":
                    parts.append(f"intelligence: {dweller.intelligence}")
                case "A":
                    parts.append(f"agility: {dweller.agility}")
                case "L":
                    parts.append(f"luck: {dweller.luck}")
        return ", ".join(parts)

    @staticmethod
    def get_stat(dweller: "SPECIALModel", stat: str) -> int:
        """Get a SPECIAL stat value by enum member or string name. Handles None → 1."""
        val = stat.value if hasattr(stat, "value") else stat
        match val:
            case "S" | "strength":
                result = dweller.strength
            case "P" | "perception":
                result = dweller.perception
            case "E" | "endurance":
                result = dweller.endurance
            case "C" | "charisma":
                result = dweller.charisma
            case "I" | "intelligence":
                result = dweller.intelligence
            case "A" | "agility":
                result = dweller.agility
            case "L" | "luck":
                result = dweller.luck
            case _:
                raise ValueError(f"Unknown SPECIAL stat: {val}")
        return 1 if result is None else result

    @staticmethod
    def set_stat(dweller: "SPECIALModel", stat: str, value: int) -> None:
        """Set a SPECIAL stat value by enum member or string name."""
        val = stat.value if hasattr(stat, "value") else stat
        match val:
            case "S" | "strength":
                dweller.strength = value
            case "P" | "perception":
                dweller.perception = value
            case "E" | "endurance":
                dweller.endurance = value
            case "C" | "charisma":
                dweller.charisma = value
            case "I" | "intelligence":
                dweller.intelligence = value
            case "A" | "agility":
                dweller.agility = value
            case "L" | "luck":
                dweller.luck = value
            case _:
                raise ValueError(f"Unknown SPECIAL stat: {val}")
