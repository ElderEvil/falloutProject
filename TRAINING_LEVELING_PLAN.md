# Training, Leveling & Experience System - Implementation Plan

## Executive Summary

This document outlines the implementation of a comprehensive training, leveling, and experience system for the Fallout Shelter game. The work is divided into **4 releases** to ensure incremental delivery and testing.

---

## Design Principles

### SPECIAL Stat Progression
**SPECIAL stats can ONLY be increased through:**
1. **Training rooms** - Primary method, costs time
2. **Quest rewards** - Rare, special rewards
3. **Exploration events** - Random discoveries (e.g., finding a Bobblehead)
4. **Breeding** - Inherited from parents (already implemented)

**NO manual stat point distribution** - players cannot freely allocate points.

### Experience & Leveling
- **Leveling grants**: HP increases, prestige, unlock higher difficulty content
- **Experience sources**: Exploration, combat, working, training time
- **Level cap**: 50 (as per current model)

### Training System
- **Time-based**: Training takes real-time hours to complete
- **Stat-specific rooms**: Each SPECIAL stat has dedicated training room(s)
- **Scaling duration**: Higher current stat = longer training time
- **Multiple trainees**: Rooms have capacity for multiple dwellers

---

## Current State Analysis

### What Exists ✅
- Dweller model with `level` (1-50) and `experience` fields
- 7 training rooms in data (Weight, Athletics, Armory, Classroom, Fitness, Lounge, Game room)
- Room category `TRAINING` enum
- Dweller status `TRAINING` enum
- Experience awarded in exploration (distance × 10 + enemies × 50)

### What's Missing ❌
- Level-up logic (experience accumulates but level never increases)
- Training system (rooms exist but don't train)
- Experience requirement calculations
- Combat XP rewards
- Work XP rewards
- Training progress tracking
- SPECIAL stat cap enforcement (should be 10)

### Issues with Current Room System
- Rooms stored in JSON with redundant/duplicate data
- No separation between "room template" (design) and "room instance" (vault-specific)
- Building logic mixes template data with instance data
- All properties must be specified even if formulaic

---

# Release Plan

## Release v1.5: Core Leveling System ✅ COMPLETED
**Status**: Shipped (January 2, 2026)
**Actual Time**: 8 hours
**Goal**: Implement basic leveling mechanics and experience tracking

**Commits**:
- `4a8a3b0`: Core leveling system implementation
- `e3f76f1`: Exploration XP test updates
- `3c958ea`: Vault number validation fix

**Deliverables**:
- ✅ Leveling service with XP curve (100 * level^1.5)
- ✅ Multiple XP sources (exploration, combat, work)
- ✅ Game loop integration with dweller processing
- ✅ HP scaling (+5 per level, full heal on level-up)
- ✅ 11 comprehensive tests (90.70% coverage)
- ✅ Weight Room added to new vaults for testing

### Backend Tasks

#### 1.1 Leveling Service
**File**: `backend/app/services/leveling_service.py`

```python
class LevelingService:
    """Service for handling dweller leveling and experience."""

    @staticmethod
    def calculate_xp_required(level: int) -> int:
        """Calculate total XP required to reach a level.
        Formula: 100 * (level ^ 1.5)
        Level 1->2: 100 XP
        Level 2->3: 283 XP
        Level 10->11: 3,162 XP
        Level 50->MAX: ~353,553 XP
        """

    @staticmethod
    def calculate_xp_for_level_range(current_level: int, target_level: int) -> int:
        """Calculate XP needed between two levels."""

    async def check_level_up(
        self,
        db_session: AsyncSession,
        dweller: Dweller
    ) -> tuple[bool, int]:
        """
        Check if dweller should level up.
        Returns: (leveled_up: bool, levels_gained: int)
        """

    async def level_up_dweller(
        self,
        db_session: AsyncSession,
        dweller: Dweller,
        levels: int = 1
    ) -> Dweller:
        """
        Level up dweller:
        - Increase level
        - Increase max_health (5 HP per level)
        - Heal to new max if needed
        - Return updated dweller
        """
```

**Game Balance Constants**:
```python
# backend/app/config/game_balance.py
BASE_XP_REQUIREMENT = 100
XP_CURVE_EXPONENT = 1.5
HP_GAIN_PER_LEVEL = 5
MAX_LEVEL = 50
```

#### 1.2 Update Dweller Model
**File**: `backend/app/models/dweller.py`

Add properties:
```python
@property
def current_level_xp(self) -> int:
    """XP required for current level."""
    return leveling_service.calculate_xp_required(self.level)

@property
def next_level_xp(self) -> int:
    """XP required for next level."""
    return leveling_service.calculate_xp_required(self.level + 1)

@property
def xp_progress_percentage(self) -> float:
    """Progress to next level as percentage (0-100)."""
    if self.level >= MAX_LEVEL:
        return 100.0
    current = self.experience - self.current_level_xp
    required = self.next_level_xp - self.current_level_xp
    return (current / required) * 100 if required > 0 else 0.0
```

#### 1.3 Enhanced Experience Rewards

**Exploration** (`backend/app/services/wasteland_service.py`):
```python
# Current: (distance * 10) + (enemies * 50)
# Enhanced:
def calculate_exploration_xp(exploration: Exploration) -> int:
    base_xp = (exploration.total_distance * 10)
    combat_xp = (exploration.enemies_encountered * 50)
    event_xp = len(exploration.events) * 20

    # Survival bonus (returned with >70% health)
    survival_bonus = 0
    if dweller.health / dweller.max_health > 0.7:
        survival_bonus = int((base_xp + combat_xp) * 0.2)

    # Luck bonus (0-20% based on luck stat)
    luck_bonus = int((base_xp + combat_xp) * (exploration.dweller_luck / 50))

    return base_xp + combat_xp + event_xp + survival_bonus + luck_bonus
```

**Combat** (`backend/app/services/combat_service.py`):
```python
async def award_combat_xp(
    db_session: AsyncSession,
    incident: Incident,
    participating_dwellers: list[Dweller]
) -> None:
    """Award XP to dwellers who fought in incident."""
    base_xp = incident.difficulty * 30  # 30-300 XP range

    # Distribute among participants
    xp_per_dweller = base_xp // len(participating_dwellers)

    # Bonus for victory without taking damage
    if incident.status == "resolved" and all(d.health == d.max_health for d in dwellers):
        xp_per_dweller = int(xp_per_dweller * 1.5)

    for dweller in participating_dwellers:
        dweller.experience += xp_per_dweller
        await leveling_service.check_level_up(db_session, dweller)
```

**Working** (`backend/app/services/resource_manager.py` or `game_loop.py`):
```python
# Small XP gain per tick for dwellers working in production rooms
WORK_XP_PER_TICK = 2  # 2 XP per minute = 120 XP per hour
# Bonus for working at 100% efficiency (all SPECIAL requirements met)
WORK_XP_EFFICIENCY_BONUS = 1.5  # 50% more XP
```

#### 1.4 Game Loop Integration
**File**: `backend/app/services/game_loop.py`

```python
async def process_dweller_experience(
    db_session: AsyncSession,
    vault: Vault
) -> None:
    """Process experience gains and level-ups for all dwellers in vault."""

    for dweller in vault.dwellers:
        # Award work XP if working
        if dweller.status == DwellerStatusEnum.WORKING and dweller.room_id:
            room = await room_crud.get(db_session, dweller.room_id)
            if room.category == RoomTypeEnum.PRODUCTION:
                xp_gain = calculate_work_xp(dweller, room)
                dweller.experience += xp_gain

        # Check for level-ups
        leveled_up, levels = await leveling_service.check_level_up(db_session, dweller)
        if leveled_up:
            await leveling_service.level_up_dweller(db_session, dweller, levels)
            # TODO: Store notification for frontend
```

#### 1.5 Testing
**Files**:
- `backend/app/tests/test_services/test_leveling_service.py`
- `backend/app/tests/test_api/test_dweller_leveling.py`

**Test Coverage**:
- XP calculation curve (levels 1-50)
- Level-up detection logic
- Health increases on level-up
- Multiple level-ups at once
- Max level cap enforcement
- XP progress percentage calculation
- Experience from all sources (exploration, combat, work)

#### 1.6 Database Migration
**File**: `backend/app/alembic/versions/YYYY_MM_DD_HHMM-leveling_system.py`

```python
# No new fields needed - using existing level and experience fields
# Just ensure max_health can store up to 1000 (already in model)
# Add index on dweller.level for performance
op.create_index('ix_dweller_level', 'dweller', ['level'])
```

---

## Release v1.6: Training System (Core)
**Estimated Time**: 8-10 hours
**Goal**: Implement training rooms that increase SPECIAL stats over time

### Backend Tasks

#### 2.1 Training Model
**File**: `backend/app/models/training.py`

```python
from datetime import datetime
from enum import StrEnum
from pydantic import UUID4
from sqlmodel import Field, SQLModel
from app.models.base import BaseUUIDModel, TimeStampMixin
from app.schemas.common import SPECIALEnum

class TrainingStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class TrainingBase(SQLModel):
    dweller_id: UUID4 = Field(foreign_key="dweller.id", index=True)
    room_id: UUID4 = Field(foreign_key="room.id", index=True)
    vault_id: UUID4 = Field(foreign_key="vault.id", index=True)

    stat_being_trained: SPECIALEnum
    current_stat_value: int = Field(ge=1, le=10)  # Snapshot at start
    target_stat_value: int = Field(ge=2, le=10)   # Always current + 1

    progress: float = Field(default=0.0, ge=0.0, le=1.0)  # 0.0 to 1.0

    started_at: datetime
    estimated_completion_at: datetime
    completed_at: datetime | None = None

    status: TrainingStatus = Field(default=TrainingStatus.ACTIVE, index=True)

class Training(BaseUUIDModel, TrainingBase, TimeStampMixin, table=True):
    def is_active(self) -> bool:
        return self.status == TrainingStatus.ACTIVE

    def is_completed(self) -> bool:
        return self.status == TrainingStatus.COMPLETED

    def progress_percentage(self) -> float:
        return self.progress * 100

    def time_remaining_seconds(self) -> int:
        if not self.is_active():
            return 0
        now = datetime.utcnow()
        remaining = (self.estimated_completion_at - now).total_seconds()
        return max(0, int(remaining))
```

#### 2.2 Training Service
**File**: `backend/app/services/training_service.py`

```python
class TrainingService:
    """Service for managing dweller training in training rooms."""

    @staticmethod
    def calculate_training_duration(
        current_stat: int,
        room_tier: int = 1
    ) -> int:
        """
        Calculate training duration in seconds.

        Base: 2 hours (7200 seconds)
        Scaling: +30 minutes per current stat level
        Room tier reduces time: T2 = 75%, T3 = 60%

        Examples:
        - Stat 1→2: 2h (base)
        - Stat 5→6: 4.5h
        - Stat 9→10: 6.5h
        - Stat 9→10 (T3): 3.9h (6.5h * 0.6)
        """
        base_duration = 7200  # 2 hours
        per_level_increase = 1800  # 30 minutes

        duration = base_duration + (current_stat * per_level_increase)

        # Apply tier multiplier
        tier_multipliers = {1: 1.0, 2: 0.75, 3: 0.6}
        duration *= tier_multipliers.get(room_tier, 1.0)

        return int(duration)

    async def can_start_training(
        self,
        db_session: AsyncSession,
        dweller: Dweller,
        room: Room
    ) -> tuple[bool, str]:
        """
        Validate if dweller can start training.
        Returns: (can_train: bool, reason: str)
        """
        # Check if dweller is already training
        existing = await training_crud.get_active_by_dweller(db_session, dweller.id)
        if existing:
            return False, "Dweller is already training"

        # Check if room is training room
        if room.category != RoomTypeEnum.TRAINING:
            return False, "Room is not a training room"

        # Check room capacity
        trainee_count = await training_crud.count_active_in_room(db_session, room.id)
        if trainee_count >= room.capacity:
            return False, "Training room is at full capacity"

        # Check if stat is already maxed
        stat_value = getattr(dweller, room.ability.lower())
        if stat_value >= 10:
            return False, f"{room.ability} is already at maximum (10)"

        # Check if dweller is assigned to this room
        if dweller.room_id != room.id:
            return False, "Dweller must be assigned to training room first"

        return True, ""

    async def start_training(
        self,
        db_session: AsyncSession,
        dweller_id: UUID4,
        room_id: UUID4
    ) -> Training:
        """Start training for a dweller in a training room."""
        dweller = await dweller_crud.get(db_session, dweller_id)
        room = await room_crud.get(db_session, room_id)

        # Validate
        can_train, reason = await self.can_start_training(db_session, dweller, room)
        if not can_train:
            raise ValueError(reason)

        # Get current stat value
        stat_name = room.ability.lower()
        current_stat = getattr(dweller, stat_name)

        # Calculate duration
        duration_seconds = self.calculate_training_duration(current_stat, room.tier)
        estimated_completion = datetime.utcnow() + timedelta(seconds=duration_seconds)

        # Create training record
        training = Training(
            dweller_id=dweller.id,
            room_id=room.id,
            vault_id=dweller.vault_id,
            stat_being_trained=room.ability,
            current_stat_value=current_stat,
            target_stat_value=current_stat + 1,
            started_at=datetime.utcnow(),
            estimated_completion_at=estimated_completion,
            status=TrainingStatus.ACTIVE,
        )

        training = await training_crud.create(db_session, obj_in=training)

        # Update dweller status
        await dweller_crud.update(
            db_session,
            dweller.id,
            DwellerUpdate(status=DwellerStatusEnum.TRAINING)
        )

        return training

    async def update_training_progress(
        self,
        db_session: AsyncSession,
        training: Training
    ) -> Training:
        """Update training progress based on elapsed time."""
        if not training.is_active():
            return training

        now = datetime.utcnow()
        elapsed = (now - training.started_at).total_seconds()
        total_duration = (training.estimated_completion_at - training.started_at).total_seconds()

        training.progress = min(1.0, elapsed / total_duration)

        # Auto-complete if finished
        if training.progress >= 1.0:
            await self.complete_training(db_session, training)
        else:
            await training_crud.update(
                db_session,
                training.id,
                TrainingUpdate(progress=training.progress)
            )

        return training

    async def complete_training(
        self,
        db_session: AsyncSession,
        training: Training
    ) -> Dweller:
        """Complete training and award stat increase."""
        if not training.is_active():
            raise ValueError("Training is not active")

        # Get dweller
        dweller = await dweller_crud.get(db_session, training.dweller_id)

        # Increase SPECIAL stat
        stat_name = training.stat_being_trained.lower()
        current_value = getattr(dweller, stat_name)
        new_value = min(10, current_value + 1)  # Cap at 10

        setattr(dweller, stat_name, new_value)

        # Award small XP for training time
        training_duration_hours = (
            training.estimated_completion_at - training.started_at
        ).total_seconds() / 3600
        training_xp = int(training_duration_hours * 50)  # 50 XP per hour trained
        dweller.experience += training_xp

        # Update training record
        training.progress = 1.0
        training.status = TrainingStatus.COMPLETED
        training.completed_at = datetime.utcnow()

        await training_crud.update(
            db_session,
            training.id,
            TrainingUpdate(
                progress=1.0,
                status=TrainingStatus.COMPLETED,
                completed_at=training.completed_at
            )
        )

        # Update dweller status to IDLE (or back to WORKING if still assigned)
        new_status = DwellerStatusEnum.IDLE
        if dweller.room_id:
            room = await room_crud.get(db_session, dweller.room_id)
            if room.category == RoomTypeEnum.TRAINING:
                new_status = DwellerStatusEnum.IDLE  # Can start new training
            elif room.category == RoomTypeEnum.PRODUCTION:
                new_status = DwellerStatusEnum.WORKING

        await dweller_crud.update(
            db_session,
            dweller.id,
            DwellerUpdate(status=new_status)
        )

        # Check for level-up from training XP
        await leveling_service.check_level_up(db_session, dweller)

        await db_session.commit()
        await db_session.refresh(dweller)

        return dweller

    async def cancel_training(
        self,
        db_session: AsyncSession,
        training_id: UUID4
    ) -> Training:
        """Cancel active training (no progress saved)."""
        training = await training_crud.get(db_session, training_id)

        if not training.is_active():
            raise ValueError("Training is not active")

        training.status = TrainingStatus.CANCELLED
        await training_crud.update(
            db_session,
            training.id,
            TrainingUpdate(status=TrainingStatus.CANCELLED)
        )

        # Update dweller status
        dweller = await dweller_crud.get(db_session, training.dweller_id)
        await dweller_crud.update(
            db_session,
            dweller.id,
            DwellerUpdate(status=DwellerStatusEnum.IDLE)
        )

        return training

training_service = TrainingService()
```

#### 2.3 Training CRUD
**File**: `backend/app/crud/training.py`

```python
class CRUDTraining(CRUDBase[Training, TrainingCreate, TrainingUpdate]):
    async def get_active_by_dweller(
        self,
        db_session: AsyncSession,
        dweller_id: UUID4
    ) -> Training | None:
        """Get active training for a dweller."""
        result = await db_session.execute(
            select(Training)
            .where(Training.dweller_id == dweller_id)
            .where(Training.status == TrainingStatus.ACTIVE)
        )
        return result.scalar_one_or_none()

    async def get_active_by_vault(
        self,
        db_session: AsyncSession,
        vault_id: UUID4
    ) -> list[Training]:
        """Get all active training sessions in a vault."""
        result = await db_session.execute(
            select(Training)
            .where(Training.vault_id == vault_id)
            .where(Training.status == TrainingStatus.ACTIVE)
        )
        return result.scalars().all()

    async def count_active_in_room(
        self,
        db_session: AsyncSession,
        room_id: UUID4
    ) -> int:
        """Count active trainees in a room."""
        result = await db_session.execute(
            select(func.count(Training.id))
            .where(Training.room_id == room_id)
            .where(Training.status == TrainingStatus.ACTIVE)
        )
        return result.scalar()

training = CRUDTraining(Training)
```

#### 2.4 Training API Endpoints
**File**: `backend/app/api/v1/endpoints/training.py`

```python
router = APIRouter()

@router.post("/start", response_model=TrainingRead)
async def start_training(
    request: TrainingStartRequest,  # {dweller_id, room_id}
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Start training a dweller in a training room."""
    # Verify access to room (which verifies vault access)
    await verify_room_access(request.room_id, user, db_session)

    training = await training_service.start_training(
        db_session,
        request.dweller_id,
        request.room_id
    )
    return training

@router.get("/dweller/{dweller_id}", response_model=TrainingRead | None)
async def get_dweller_training(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Get current active training for a dweller."""
    await verify_dweller_access(dweller_id, user, db_session)

    training = await training_crud.get_active_by_dweller(db_session, dweller_id)
    return training

@router.get("/vault/{vault_id}", response_model=list[TrainingRead])
async def list_vault_training(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """List all active training sessions in a vault."""
    await get_user_vault_or_403(vault_id, user, db_session)

    trainings = await training_crud.get_active_by_vault(db_session, vault_id)
    return trainings

@router.get("/{training_id}", response_model=TrainingRead)
async def get_training(
    training_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Get training details with current progress."""
    training = await training_crud.get(db_session, training_id)
    await verify_vault_access_via_training(training, user, db_session)

    # Update progress before returning
    training = await training_service.update_training_progress(db_session, training)
    return training

@router.post("/{training_id}/cancel", response_model=TrainingRead)
async def cancel_training(
    training_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Cancel an active training session."""
    training = await training_crud.get(db_session, training_id)
    await verify_vault_access_via_training(training, user, db_session)

    training = await training_service.cancel_training(db_session, training_id)
    return training
```

#### 2.5 Game Loop Integration
**File**: `backend/app/services/game_loop.py`

```python
async def process_training(
    db_session: AsyncSession,
    vault: Vault
) -> None:
    """Process all active training sessions in vault."""
    trainings = await training_crud.get_active_by_vault(db_session, vault.id)

    for training in trainings:
        await training_service.update_training_progress(db_session, training)
        # update_training_progress auto-completes if ready
```

#### 2.6 Training Balance Config
**File**: `backend/app/config/game_balance.py`

```python
# ===== TRAINING SYSTEM =====
# Base training duration (2 hours)
TRAINING_BASE_DURATION_SECONDS = 7200

# Additional time per current stat level (30 minutes)
TRAINING_PER_LEVEL_INCREASE_SECONDS = 1800

# Tier multipliers for training speed
TRAINING_TIER_MULTIPLIER = {
    1: 1.0,    # T1: Normal speed
    2: 0.75,   # T2: 25% faster
    3: 0.6,    # T3: 40% faster
}

# XP awarded for time spent training (per hour)
TRAINING_XP_PER_HOUR = 50

# Maximum SPECIAL stat value
MAX_SPECIAL_STAT = 10
```

#### 2.7 Database Migration
**File**: `backend/app/alembic/versions/YYYY_MM_DD_HHMM-training_system.py`

```python
def upgrade():
    op.create_table(
        'training',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('dweller_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('room_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('vault_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('stat_being_trained', sa.String(), nullable=False),
        sa.Column('current_stat_value', sa.Integer(), nullable=False),
        sa.Column('target_stat_value', sa.Integer(), nullable=False),
        sa.Column('progress', sa.Float(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('estimated_completion_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['dweller_id'], ['dweller.id']),
        sa.ForeignKeyConstraint(['room_id'], ['room.id']),
        sa.ForeignKeyConstraint(['vault_id'], ['vault.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_training_dweller_id', 'training', ['dweller_id'])
    op.create_index('ix_training_room_id', 'training', ['room_id'])
    op.create_index('ix_training_vault_id', 'training', ['vault_id'])
    op.create_index('ix_training_status', 'training', ['status'])
```

#### 2.8 Testing
**Files**:
- `backend/app/tests/test_services/test_training_service.py`
- `backend/app/tests/test_api/test_training.py`
- `backend/app/tests/test_crud/test_training.py`

**Test Coverage**:
- Training duration calculation (different stats, different tiers)
- Start training validation (capacity, max stat, already training)
- Training progress updates
- Training completion and stat increase
- SPECIAL stat cap at 10
- Training XP rewards
- Cancel training
- Multiple dwellers training in same room
- Room capacity enforcement

---

## Release v1.7: Room System Improvements
**Estimated Time**: 6-8 hours
**Goal**: Separate room templates from instances, improve room creation flow

### Backend Tasks

#### 3.1 Room Template System
**File**: `backend/app/models/room_template.py`

```python
class RoomTemplate(BaseModel):
    """Static template data for room types (loaded from JSON)."""

    name: str
    category: RoomTypeEnum
    ability: SPECIALEnum | None

    # Requirements
    population_required: int | None = None

    # Costs
    base_cost: int
    incremental_cost: int | None = None
    t2_upgrade_cost: int | None = None
    t3_upgrade_cost: int | None = None

    # Formulas (optional, for dynamic calculation)
    capacity_formula: str | None = None
    output_formula: str | None = None

    # Size constraints
    size_min: int
    size_max: int

    # Default speedup multiplier
    speedup_multiplier: float = 1.0

    # Metadata
    description: str | None = None
    image_url: str | None = None

    @property
    def is_unique(self) -> bool:
        return self.incremental_cost is None

    @property
    def max_tier(self) -> int:
        if self.t3_upgrade_cost is not None:
            return 3
        if self.t2_upgrade_cost is not None:
            return 2
        return 1
```

#### 3.2 Room Template Loader
**File**: `backend/app/services/room_template_service.py`

```python
class RoomTemplateService:
    """Service for loading and managing room templates."""

    def __init__(self):
        self.templates: dict[str, RoomTemplate] = {}
        self._load_templates()

    def _load_templates(self) -> None:
        """Load room templates from JSON file."""
        template_file = Path(__file__).parent.parent / "data" / "vault" / "rooms.json"

        with open(template_file) as f:
            data = json.load(f)

        for item in data:
            template = RoomTemplate(**item)
            self.templates[template.name] = template

    def get_template(self, name: str) -> RoomTemplate:
        """Get room template by name."""
        template = self.templates.get(name)
        if not template:
            raise ValueError(f"Room template '{name}' not found")
        return template

    def get_all_templates(self) -> list[RoomTemplate]:
        """Get all room templates."""
        return list(self.templates.values())

    def get_available_templates(
        self,
        vault_population: int
    ) -> list[RoomTemplate]:
        """Get templates available for current vault population."""
        return [
            t for t in self.templates.values()
            if t.population_required is None or vault_population >= t.population_required
        ]

    def get_templates_by_category(
        self,
        category: RoomTypeEnum
    ) -> list[RoomTemplate]:
        """Get all templates of a specific category."""
        return [t for t in self.templates.values() if t.category == category]

room_template_service = RoomTemplateService()
```

#### 3.3 Update Room Model
**File**: `backend/app/models/room.py`

Add field to link to template:
```python
class Room(BaseUUIDModel, RoomBase, TimeStampMixin, table=True):
    # Add template name to identify source template
    template_name: str | None = Field(default=None, index=True)

    # ... rest of existing fields
```

#### 3.4 Refactor Room Building
**File**: `backend/app/crud/room.py`

Update `build()` method:
```python
async def build(self, *, db_session: AsyncSession, obj_in: RoomCreate) -> Room:
    """Build a room using template + instance data."""

    # Load template
    template = room_template_service.get_template(obj_in.name)

    # Validate vault population requirement
    vault = await vault_crud.get(db_session, id=obj_in.vault_id)
    if template.population_required:
        population = await vault_crud.get_population(
            db_session=db_session,
            vault_id=vault.id
        )
        if population < template.population_required:
            raise InsufficientResourcesException(
                resource_name="dwellers",
                resource_amount=template.population_required
            )

    # Check for coordinate conflicts
    existing_room = await self.get_room_by_coordinates(
        db_session=db_session,
        vault_id=vault.id,
        x_coord=obj_in.coordinate_x,
        y_coord=obj_in.coordinate_y
    )

    if existing_room:
        # Can merge if same template and tier
        if existing_room.template_name == template.name and existing_room.tier == obj_in.tier:
            return await self.expand_room(db_session, existing_room, obj_in.size)
        raise NoSpaceAvailableException(space_needed=obj_in.size)

    # Check if unique room already exists
    if template.is_unique:
        existing_unique = await db_session.execute(
            select(Room)
            .where(Room.vault_id == vault.id)
            .where(Room.template_name == template.name)
        )
        if existing_unique.scalars().first():
            raise UniqueRoomViolationException(room_name=template.name)

    # Calculate capacity and output from formulas
    capacity = None
    if template.capacity_formula:
        capacity = self.evaluate_capacity_formula(
            template.capacity_formula,
            obj_in.tier,
            obj_in.size
        )

    output = None
    if template.output_formula:
        output = self.evaluate_output_formula(
            template.output_formula,
            obj_in.tier,
            obj_in.size
        )

    # Calculate build cost
    price = template.base_cost
    if template.incremental_cost:
        # Count existing rooms with same template
        result = await db_session.execute(
            select(func.count(Room.id))
            .where(Room.vault_id == vault.id)
            .where(Room.template_name == template.name)
        )
        existing_count = result.scalar()
        price += existing_count * template.incremental_cost

    # Deduct caps
    await vault_crud.withdraw_caps(db_session=db_session, vault_obj=vault, amount=price)

    # Create room instance
    room_data = RoomCreate(
        name=template.name,
        template_name=template.name,  # Link to template
        category=template.category,
        ability=template.ability,
        population_required=template.population_required,
        base_cost=template.base_cost,
        incremental_cost=template.incremental_cost,
        t2_upgrade_cost=template.t2_upgrade_cost,
        t3_upgrade_cost=template.t3_upgrade_cost,
        capacity=capacity,
        output=output,
        size_min=template.size_min,
        size_max=template.size_max,
        size=obj_in.size,
        tier=obj_in.tier,
        coordinate_x=obj_in.coordinate_x,
        coordinate_y=obj_in.coordinate_y,
        vault_id=vault.id,
        speedup_multiplier=template.speedup_multiplier,
    )

    room = await self.create(db_session, obj_in=room_data)

    # Recalculate vault attributes if needed
    if self.requires_recalculation(room):
        await vault_crud.recalculate_vault_attributes(
            db_session=db_session,
            vault_obj=vault,
            room_obj=room,
            action=RoomActionEnum.BUILD
        )

    return room
```

#### 3.5 New API Endpoints
**File**: `backend/app/api/v1/endpoints/room.py`

```python
@router.get("/templates/", response_model=list[RoomTemplateRead])
async def get_room_templates(
    user: CurrentActiveUser,
    vault_id: UUID4 | None = None,
):
    """
    Get all room templates.
    If vault_id provided, filter by population requirement.
    """
    if vault_id:
        vault = await vault_crud.get(db_session, vault_id)
        population = await vault_crud.get_population(db_session, vault_id)
        templates = room_template_service.get_available_templates(population)
    else:
        templates = room_template_service.get_all_templates()

    return templates

@router.get("/templates/{name}", response_model=RoomTemplateRead)
async def get_room_template(
    name: str,
    user: CurrentActiveUser,
):
    """Get a specific room template by name."""
    return room_template_service.get_template(name)

@router.get("/templates/category/{category}", response_model=list[RoomTemplateRead])
async def get_templates_by_category(
    category: RoomTypeEnum,
    user: CurrentActiveUser,
):
    """Get all templates of a specific category."""
    return room_template_service.get_templates_by_category(category)
```

#### 3.6 Simplify Room Schemas
**File**: `backend/app/schemas/room.py`

```python
class RoomBuildRequest(BaseModel):
    """Simplified request for building a room."""
    template_name: str
    coordinate_x: int
    coordinate_y: int
    size: int  # Must be between template's size_min and size_max
    tier: int = 1  # Default to tier 1

# Backend will load template and fill in the rest
```

#### 3.7 Testing
**Files**:
- `backend/app/tests/test_services/test_room_template_service.py`
- `backend/app/tests/test_api/test_room_templates.py`
- Update existing room tests

**Test Coverage**:
- Template loading from JSON
- Template filtering by population
- Template filtering by category
- Room building with templates
- Cost calculation with incremental pricing
- Unique room enforcement
- Room merging logic

---

## Release v1.8: Quest & Exploration SPECIAL Rewards
**Estimated Time**: 4-6 hours
**Goal**: Add SPECIAL stat increases as quest/exploration rewards

### Backend Tasks

#### 4.1 SPECIAL Reward System
**File**: `backend/app/models/reward.py`

```python
class SpecialReward(BaseModel):
    """Reward for increasing SPECIAL stat."""
    stat: SPECIALEnum
    increase: int = Field(ge=1, le=3, default=1)  # Usually +1, rare cases +2 or +3

class RewardBundle(BaseModel):
    """Bundle of rewards from quests/events."""
    caps: int = 0
    experience: int = 0
    items: list[dict] = Field(default_factory=list)
    special_increases: list[SpecialReward] = Field(default_factory=list)
```

#### 4.2 Quest Reward Enhancement
**File**: `backend/app/data/quests/*/quest_name.json`

Add SPECIAL rewards to quest definitions:
```json
{
  "name": "The Archivist",
  "description": "Help the overseer organize the vault archives.",
  "rewards": {
    "caps": 200,
    "experience": 300,
    "special_increases": [
      {"stat": "intelligence", "increase": 1}
    ]
  }
}
```

**File**: `backend/app/crud/quest.py`

Update quest completion to award SPECIAL increases:
```python
async def complete_quest(
    db_session: AsyncSession,
    quest_id: UUID4,
    dweller_id: UUID4
) -> dict:
    """Complete quest and award rewards including SPECIAL increases."""

    quest = await quest_crud.get(db_session, quest_id)
    dweller = await dweller_crud.get(db_session, dweller_id)

    # Award caps, XP, items (existing logic)
    # ...

    # Award SPECIAL increases (NEW)
    if quest.special_rewards:
        for reward in quest.special_rewards:
            stat_name = reward.stat.lower()
            current_value = getattr(dweller, stat_name)
            new_value = min(10, current_value + reward.increase)
            setattr(dweller, stat_name, new_value)

            # Log for notification
            special_increases.append({
                "stat": reward.stat,
                "old_value": current_value,
                "new_value": new_value
            })

    await db_session.commit()

    return {
        "caps": caps_awarded,
        "experience": xp_awarded,
        "items": items_awarded,
        "special_increases": special_increases
    }
```

#### 4.3 Exploration Event: Bobblehead Discovery
**File**: `backend/app/services/wasteland_service.py`

Add rare event type for finding Bobbleheads:
```python
def generate_event(self, exploration: Exploration) -> dict | None:
    """Generate wasteland event (existing method)."""

    # ... existing event logic ...

    # NEW: Very rare chance to find a Bobblehead (1-2% chance)
    bobblehead_chance = 0.01 + (exploration.dweller_luck * 0.001)  # Luck increases chance

    if random.random() < bobblehead_chance:
        # Random SPECIAL stat
        stat = random.choice(list(SPECIALEnum))

        return {
            "type": "bobblehead_found",
            "description": f"Found a {stat.value} Bobblehead! Your {stat.value} permanently increased!",
            "special_reward": {
                "stat": stat,
                "increase": 1
            }
        }

    # ... rest of existing event logic ...

async def process_event(
    self,
    db_session: AsyncSession,
    exploration: Exploration,
) -> Exploration:
    """Process generated event (existing method)."""

    event = self.generate_event(exploration)
    if not event:
        return exploration

    # ... existing event processing ...

    # NEW: Handle SPECIAL rewards
    if event.get("special_reward"):
        dweller = await dweller_crud.get(db_session, exploration.dweller_id)
        reward = event["special_reward"]

        stat_name = reward["stat"].lower()
        current_value = getattr(dweller, stat_name)
        new_value = min(10, current_value + reward["increase"])
        setattr(dweller, stat_name, new_value)

        # Store in event data
        event["special_reward"]["old_value"] = current_value
        event["special_reward"]["new_value"] = new_value

    # Add event to exploration
    await crud_exploration.add_event(
        db_session,
        exploration_id=exploration.id,
        event_type=event["type"],
        description=event["description"],
        loot=event.get("loot"),
        special_reward=event.get("special_reward")
    )

    # ... rest of existing logic ...
```

#### 4.4 Update Exploration Model
**File**: `backend/app/models/exploration.py`

Add field to track SPECIAL rewards:
```python
class Exploration(BaseUUIDModel, ExplorationBase, TimeStampMixin, table=True):
    # ... existing fields ...

    special_rewards_gained: list[dict] = Field(
        default_factory=list,
        sa_column=sa.Column(JSONB)
    )

    def add_event(
        self,
        event_type: str,
        description: str,
        loot: dict | None = None,
        special_reward: dict | None = None  # NEW
    ) -> None:
        """Add event to journey log."""
        event = {
            "type": event_type,
            "description": description,
            "timestamp": datetime.utcnow().isoformat(),
            "time_elapsed_hours": round(self.elapsed_time_seconds() / 3600, 2),
        }
        if loot:
            event["loot"] = loot
        if special_reward:
            event["special_reward"] = special_reward
            self.special_rewards_gained.append(special_reward)

        self.events.append(event)
```

#### 4.5 Testing
**Files**:
- `backend/app/tests/test_services/test_wasteland_special_rewards.py`
- `backend/app/tests/test_api/test_quest_special_rewards.py`

**Test Coverage**:
- Bobblehead discovery in exploration
- SPECIAL stat increase from Bobblehead
- SPECIAL stat cap at 10
- Quest completion with SPECIAL rewards
- Reward display in responses

---

## Summary Table

| Release | Focus | Backend Hours | Frontend Hours | Total |
|---------|-------|---------------|----------------|-------|
| v1.5 | Core Leveling System | 6-8 | - | 6-8 |
| v1.6 | Training System (Core) | 8-10 | - | 8-10 |
| v1.7 | Room System Improvements | 6-8 | - | 6-8 |
| v1.8 | Quest/Exploration SPECIAL Rewards | 4-6 | - | 4-6 |
| **Total Backend** | | **24-32 hours** | - | **24-32 hours** |
| **Frontend** (Later) | Training UI, Level-up UI, XP bars | - | 10-15 | 10-15 |
| **Grand Total** | | | | **34-47 hours** |

---

## Frontend Implementation (Later Phase)

### Components Needed:
1. **XP Progress Bar** - Show XP progress to next level in dweller cards
2. **Level-up Notification** - Toast/modal when dweller levels up
3. **Training Room UI** - Start training, view progress, cancel training
4. **Training Progress Indicators** - Progress bars for active training
5. **Training Queue Panel** - List all dwellers currently training
6. **SPECIAL Stat Display** - Highlight stats that can be trained, show training history
7. **Room Template Browser** - UI for browsing and building rooms from templates
8. **Bobblehead Discovery Animation** - Special animation when found in exploration
9. **Quest Reward Display** - Show SPECIAL increases in quest completion

---

## Game Balance Summary

### Leveling
- **XP Curve**: `100 * (level ^ 1.5)`
- **Level 1→50**: ~353,553 total XP
- **HP per level**: +5 HP
- **Max level**: 50

### Training
- **Base duration**: 2 hours
- **Scaling**: +30min per current stat level
- **Example durations**:
  - 1→2: 2h
  - 5→6: 4.5h
  - 9→10: 6.5h (T1), 3.9h (T3)
- **Room capacity**: Based on room tier and size
- **Training XP**: 50 XP per hour trained

### Experience Sources
- **Exploration**: (distance×10) + (enemies×50) + (events×20) + luck bonus + survival bonus
- **Combat**: 30-300 XP per incident (scaled by difficulty)
- **Working**: 2 XP per minute (120 XP/hour)
- **Training**: 50 XP per hour

### SPECIAL Increases
- **Training rooms**: Primary method, time-based
- **Quests**: Rare rewards (+1 to +3 stat)
- **Exploration**: Bobbleheads (1-2% chance, +1 stat)
- **Max SPECIAL**: 10 (enforced)

---

## Dependencies & Prerequisites

### Must Complete Before Starting:
- None - can start immediately

### Integration Points:
- Game loop (already exists)
- Exploration system (already exists)
- Room system (already exists)
- Quest system (already exists)
- Combat/incident system (already exists)

### Database:
- PostgreSQL with existing schema
- Will need migrations for new `training` table

---

## Testing Strategy

### Unit Tests:
- Leveling calculations
- Training duration formulas
- XP reward calculations
- SPECIAL stat cap enforcement

### Integration Tests:
- Training flow (start → progress → complete)
- Level-up flow (gain XP → level up → stat increase)
- Quest completion with SPECIAL rewards
- Exploration with Bobblehead discovery

### Performance Tests:
- Game loop processing 100+ active training sessions
- Leveling checks for 200+ dwellers per tick

---

## Documentation Needs

### Developer Docs:
- Leveling formula explanation
- Training duration calculation
- Room template system architecture
- SPECIAL reward system

### User Docs (Later):
- How leveling works
- Training room guide
- SPECIAL stat progression guide
- Optimal training strategies

---

## Future Enhancements (Post-Release)

### Potential v2.0 Features:
- **Perks system**: Unlock perks at certain levels
- **Training bonuses**: Higher-level dwellers train faster
- **Group training**: Multiple dwellers training together get bonus
- **Trainer role**: Assign a high-stat dweller as trainer for bonus
- **Skill books**: Consumable items that grant SPECIAL increases
- **Training specializations**: Advanced training for specific roles
- **Prestige system**: Reset dweller level for permanent bonuses

---

## Migration Path

### From Current System:
1. All existing dwellers keep current level and experience
2. No data loss - new fields are nullable/defaulted
3. Training rooms already exist - just need backend logic
4. Room building continues to work - template system is enhancement

### Backwards Compatibility:
- Existing rooms continue to function
- Old exploration/quest data compatible
- No breaking API changes (only additions)

---

## Success Metrics

### Technical:
- ✅ All tests passing (>95% coverage)
- ✅ Game loop performance <100ms per tick
- ✅ API response times <200ms
- ✅ No memory leaks in long-running training sessions

### Gameplay:
- ✅ Dwellers level up at reasonable pace (1 level per 2-4 hours gameplay)
- ✅ Training feels rewarding (visible progress, meaningful stat increases)
- ✅ Room building is intuitive with templates
- ✅ SPECIAL increases are rare but impactful

---

## Test Improvements & Technical Debt
**Priority**: Medium | **Estimated Time**: 4-6 hours
**Status**: Planned for future iteration

### Issues Identified:

1. **Random test failures** due to fixture edge cases
   - Vault number fixture generated 1000 (exceeds lt=1000 validation)
   - Random stat values exceeding new limits
   - Timezone-aware datetime issues

2. **XP calculation assumptions** in existing tests
   - Tests expect base XP without bonuses
   - Need updates when survival/luck bonuses added
   - Missing edge case tests (70% health threshold)

3. **Missing integration tests**
   - Game loop dweller processing not fully tested
   - No tests for simultaneous level-ups
   - Work XP distribution edge cases

4. **Coverage gaps** in services
   - Incident service: 24.36% coverage
   - Game loop: 15.62% coverage
   - Wasteland service: 16.38% coverage
   - Breeding service: 20.00% coverage

5. **No performance tests**
   - Game loop tick processing time not validated
   - No benchmarks for XP calculations
   - Training duration calculations unchecked

### Test Rework Tasks:

#### Phase 1: Fixture Standardization (1-2 hours)
**Files**: `backend/app/tests/conftest.py`, `backend/app/tests/utils/`

- Create deterministic test data factories
- Add validation constraint helpers
- Document all fixture edge cases
- Add factory methods for common test scenarios

**Deliverables**:
```python
# Factory pattern for test data
class DwellerFactory:
    @staticmethod
    def create_with_stats(strength=5, perception=5, ...):
        """Create dweller with specific stats."""

    @staticmethod
    def create_low_level():
        """Level 1 dweller for leveling tests."""

    @staticmethod
    def create_max_level():
        """Level 50 dweller for cap tests."""
```

#### Phase 2: XP Calculation Tests (1-2 hours)
**Files**: `backend/app/tests/test_services/test_wasteland_service.py`

- Parametrize tests with different dweller stats
- Test survival bonus edge cases (69%, 70%, 71% health)
- Test luck multiplier ranges (luck 1-10)
- Test combined bonuses
- Add regression tests for XP formula changes

**Test Coverage**:
- All XP source combinations
- Boundary conditions (0 distance, 0 enemies, 0 events)
- Maximum XP scenarios
- Bonus stacking validation

#### Phase 3: Game Loop Integration Tests (2 hours)
**Files**: `backend/app/tests/test_services/test_game_loop_leveling.py` (NEW)

- Test work XP distribution per tick
- Test level-up during game loop
- Test multiple dwellers leveling simultaneously
- Test XP from multiple sources in one tick
- Performance benchmarks (<100ms per tick)

**Scenarios**:
- Vault with 50 dwellers all working
- Multiple dwellers level up in same tick
- Training + working + exploration all active
- Resource depletion affecting XP

#### Phase 4: Service Coverage Improvements (2-3 hours)
**Target**:
- Incident service: 24% → 60%+
- Game loop: 16% → 40%+
- Wasteland service: 16% → 50%+

**Focus Areas**:
- Error handling paths
- Edge case validations
- Service integration points
- Database transaction scenarios

#### Phase 5: Performance & Stress Tests (1 hour)
**Files**: `backend/app/tests/test_performance/` (NEW)

```python
@pytest.mark.performance
async def test_game_loop_tick_performance():
    """Game loop tick should complete in <100ms."""

@pytest.mark.performance
async def test_xp_calculation_performance():
    """XP calculations should be sub-millisecond."""

@pytest.mark.stress
async def test_100_simultaneous_level_ups():
    """Handle 100 dwellers leveling in same tick."""
```

### Deliverables:

- ✅ Zero random test failures
- ✅ All fixtures documented with constraints
- ✅ Coverage report shows improvements:
  - Overall: 48% → 65%+
  - Critical services: 60%+ coverage
- ✅ Performance benchmarks documented
- ✅ Test suite execution time <30 seconds
- ✅ Integration test scenarios documented

### Timeline:

Can be done incrementally alongside feature development:
- Phase 1: Before v1.6 (required for training tests)
- Phases 2-3: During v1.6 development
- Phases 4-5: After v1.6, before v1.7

---

**Last Updated**: January 2, 2026
**Status**: v1.5 Complete - Ready for v1.6 Training System
**Next Step**: Begin v1.6 (Training System)
