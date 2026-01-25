# Timezone-Naive Datetime Usage Analysis

This document lists all occurrences of timezone-naive datetime usage in the codebase.

## Executive Summary

**Total Issues Found:** 169

### Issues by Pattern

- **datetime.utcnow():** 91 occurrences
- **sa.DateTime() (no timezone):** 53 occurrences
- **datetime.now() (naive):** 7 occurrences
- **Field(default_factory=datetime.utcnow):** 7 occurrences
- **replace(tzinfo=None):** 6 occurrences
- **datetime.fromisoformat():** 5 occurrences

## Detailed Findings

### Field(default_factory=datetime.utcnow)

Found 7 occurrence(s) of timezone-naive datetime usage.

#### `analyze_tz.py`

**Line 22:**
```python
"Field(default_factory=datetime.utcnow)": re.compile(
```

#### `backend\app\models\base.py`

**Line 9:**
```python
created_at: datetime | None = Field(default_factory=datetime.utcnow)
```

#### `backend\app\models\chat_message.py`

**Line 39:**
```python
created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
```

#### `backend\app\models\game_state.py`

**Line 14:**
```python
last_tick_time: datetime = Field(default_factory=datetime.utcnow)
```

#### `backend\app\models\incident.py`

**Line 40:**
```python
start_time: datetime = Field(default_factory=datetime.utcnow)
```

#### `backend\app\models\notification.py`

**Line 76:**
```python
created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
```

#### `backend\app\models\pregnancy.py`

**Line 18:**
```python
conceived_at: datetime = Field(default_factory=datetime.utcnow)
```

### datetime.fromisoformat()

Found 5 occurrence(s) of timezone-naive datetime usage.

#### `analyze_tz.py`

**Line 21:**
```python
"datetime.fromisoformat()": re.compile(r"datetime\.fromisoformat\s*\("),
```

**Line 182:**
```python
f.write("### 4. Handle `datetime.fromisoformat()` carefully\n\n")
```

**Line 184:**
```python
"**Problem:** `datetime.fromisoformat()` can parse both naive and aware strings.\n\n"
```

**Line 190:**
```python
f.write("dt = datetime.fromisoformat(timestamp_str)\n")
```

#### `backend\app\services\exploration\event_generator.py`

**Line 43:**
```python
last_event_time = datetime.fromisoformat(last_event["timestamp"])
```

### datetime.now() (naive)

Found 7 occurrence(s) of timezone-naive datetime usage.

#### `analyze_tz.py`

**Line 18:**
```python
"datetime.now() (naive)": re.compile(r"datetime\.now\s*\(\s*\)"),
```

**Line 47:**
```python
elif pattern_name == "datetime.now() (naive)":
```

**Line 48:**
```python
# Only match datetime.now() with no args or only non-tz args
```

**Line 155:**
```python
f.write("### 2. Replace `datetime.now()` with timezone-aware version\n\n")
```

**Line 157:**
```python
"**Problem:** `datetime.now()` without arguments returns a naive datetime.\n\n"
```

**Line 162:**
```python
f.write("now = datetime.now()\n\n")
```

#### `backend\app\alembic\versions\2026_01_08_1455-34f9ec11db72_initial.py`

**Line 657:**
```python
now = datetime.now()
```

### datetime.utcnow()

Found 91 occurrence(s) of timezone-naive datetime usage.

#### `analyze_tz.py`

**Line 17:**
```python
"datetime.utcnow()": re.compile(r"datetime\.utcnow\s*\("),
```

**Line 141:**
```python
f.write("### 1. Replace `datetime.utcnow()` with timezone-aware alternatives\n\n")
```

**Line 143:**
```python
"**Problem:** `datetime.utcnow()` returns a naive datetime object (no timezone info).\n\n"
```

**Line 149:**
```python
f.write("now = datetime.utcnow()\n\n")
```

**Line 206:**
```python
f.write("3. **Business Logic:** Replace all `datetime.utcnow()` calls with `datetime.now(timezone.utc)`\n")
```

**Line 213:**
```python
f.write("- **Security:** JWT token creation uses `datetime.utcnow()`\n")
```

#### `backend\app\api\v1\endpoints\pregnancy.py`

**Line 225:**
```python
pregnancy.due_at = datetime.utcnow() - timedelta(seconds=1)
```

**Line 226:**
```python
pregnancy.updated_at = datetime.utcnow()
```

#### `backend\app\api\v1\endpoints\system.py`

**Line 47:**
```python
build_date=datetime.utcnow().isoformat(),
```

#### `backend\app\core\security.py`

**Line 21:**
```python
expire = datetime.utcnow() + expires_delta
```

**Line 23:**
```python
expire = datetime.utcnow() + timedelta(
```

**Line 44:**
```python
expire = datetime.utcnow() + expires_delta
```

**Line 46:**
```python
expire = datetime.utcnow() + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
```

**Line 83:**
```python
expire = datetime.utcnow() + timedelta(days=7)
```

**Line 105:**
```python
expire = datetime.utcnow() + timedelta(hours=1)
```

#### `backend\app\crud\exploration.py`

**Line 50:**
```python
start_time=datetime.utcnow(),
```

#### `backend\app\crud\notification.py`

**Line 47:**
```python
notification.read_at = datetime.utcnow()
```

**Line 63:**
```python
notification.read_at = datetime.utcnow()
```

#### `backend\app\db\session.py`

**Line 16:**
```python
# This ensures datetime.utcnow() values are correctly interpreted as UTC
```

#### `backend\app\models\base.py`

**Line 32:**
```python
self.deleted_at = datetime.utcnow()
```

#### `backend\app\models\exploration.py`

**Line 17:**
```python
return datetime.utcnow()
```

**Line 71:**
```python
now = datetime.utcnow()
```

**Line 99:**
```python
now = datetime.utcnow()
```

**Line 106:**
```python
self.end_time = datetime.utcnow()
```

**Line 111:**
```python
self.end_time = datetime.utcnow()
```

**Line 118:**
```python
"timestamp": datetime.utcnow().isoformat(),
```

**Line 135:**
```python
"found_at": datetime.utcnow().isoformat(),
```

#### `backend\app\models\game_state.py`

**Line 29:**
```python
return int((datetime.utcnow() - self.last_tick_time).total_seconds())
```

**Line 34:**
```python
self.paused_at = datetime.utcnow()
```

**Line 39:**
```python
self.resumed_at = datetime.utcnow()
```

**Line 43:**
```python
self.last_tick_time = datetime.utcnow()
```

#### `backend\app\models\incident.py`

**Line 68:**
```python
return int((datetime.utcnow() - self.start_time).total_seconds())
```

**Line 77:**
```python
self.end_time = datetime.utcnow()
```

#### `backend\app\models\llm_interaction.py`

**Line 25:**
```python
created_at: datetime | None = Field(default_factory=lambda: datetime.utcnow())
```

#### `backend\app\models\pregnancy.py`

**Line 46:**
```python
return datetime.utcnow() >= due_at and self.status == PregnancyStatusEnum.PREGNANT
```

**Line 55:**
```python
elapsed = (datetime.utcnow() - self.conceived_at).total_seconds()
```

**Line 68:**
```python
remaining = (self.due_at - datetime.utcnow()).total_seconds()
```

#### `backend\app\models\training.py`

**Line 81:**
```python
now = datetime.utcnow()
```

**Line 92:**
```python
return datetime.utcnow() >= self.estimated_completion_at
```

#### `backend\app\services\breeding_service.py`

**Line 163:**
```python
conceived_at = datetime.utcnow()
```

**Line 202:**
```python
.where(Pregnancy.due_at <= datetime.utcnow())
```

**Line 266:**
```python
"birth_date": datetime.utcnow(),
```

**Line 287:**
```python
pregnancy.updated_at = datetime.utcnow()
```

**Line 383:**
```python
growth_threshold = datetime.utcnow() - timedelta(hours=game_config.breeding.child_growth_duration_hours)
```

**Line 408:**
```python
child.updated_at = datetime.utcnow()
```

#### `backend\app\services\death_service.py`

**Line 60:**
```python
death_timestamp=datetime.utcnow(),
```

**Line 191:**
```python
now = datetime.utcnow()
```

**Line 209:**
```python
cutoff_date = datetime.utcnow() - timedelta(days=game_config.death.permanent_death_days)
```

#### `backend\app\services\exploration\event_generator.py`

**Line 50:**
```python
now = datetime.utcnow()
```

#### `backend\app\services\game_loop.py`

**Line 44:**
```python
start_time = datetime.utcnow()
```

**Line 59:**
```python
stats["total_time"] = (datetime.utcnow() - start_time).total_seconds()
```

#### `backend\app\services\incident_service.py`

**Line 60:**
```python
seconds_since_last = (datetime.utcnow() - most_recent.start_time).total_seconds()
```

#### `backend\app\services\relationship_service.py`

**Line 98:**
```python
update_data = {"affinity": min(100, relationship.affinity + amount), "updated_at": datetime.utcnow()}
```

**Line 149:**
```python
update_data = {"relationship_type": RelationshipTypeEnum.ROMANTIC, "updated_at": datetime.utcnow()}
```

**Line 187:**
```python
update_data = {"relationship_type": RelationshipTypeEnum.PARTNER, "updated_at": datetime.utcnow()}
```

**Line 263:**
```python
"updated_at": datetime.utcnow(),
```

#### `backend\app\services\training_service.py`

**Line 162:**
```python
now = datetime.utcnow()
```

**Line 215:**
```python
now = datetime.utcnow()
```

**Line 278:**
```python
training.completed_at = datetime.utcnow()
```

**Line 334:**
```python
training.completed_at = datetime.utcnow()
```

#### `backend\app\tests\test_services\test_breeding_service.py`

**Line 299:**
```python
pregnancy.due_at = datetime.utcnow() - timedelta(hours=1)
```

**Line 345:**
```python
pregnancy.due_at = datetime.utcnow() - timedelta(hours=1)
```

**Line 379:**
```python
pregnancy.due_at = datetime.utcnow() - timedelta(hours=1)
```

**Line 414:**
```python
pregnancy.due_at = datetime.utcnow() - timedelta(hours=1)
```

**Line 443:**
```python
pregnancy.due_at = datetime.utcnow() - timedelta(hours=1)
```

**Line 468:**
```python
pregnancy.due_at = datetime.utcnow() - timedelta(hours=1)
```

**Line 510:**
```python
"birth_date": datetime.utcnow(),  # Just born
```

**Line 547:**
```python
birth_date = datetime.utcnow() - timedelta(hours=game_config.breeding.child_growth_duration_hours + 1)
```

#### `backend\app\tests\test_services\test_death_service.py`

**Line 55:**
```python
"death_timestamp": datetime.utcnow() - timedelta(days=2),
```

**Line 81:**
```python
"death_timestamp": datetime.utcnow() - timedelta(days=10),
```

**Line 284:**
```python
"death_timestamp": datetime.utcnow() - timedelta(days=2),
```

**Line 310:**
```python
"death_timestamp": datetime.utcnow() - timedelta(days=6, hours=12),
```

**Line 337:**
```python
"death_timestamp": datetime.utcnow() - timedelta(days=10),
```

**Line 354:**
```python
"death_timestamp": datetime.utcnow() - timedelta(days=2),
```

#### `backend\app\tests\test_services\test_exploration_coordinator.py`

**Line 301:**
```python
exploration.start_time = datetime.utcnow() - timedelta(hours=1)
```

#### `backend\app\tests\test_services\test_exploration_service.py`

**Line 77:**
```python
exploration.start_time = datetime.utcnow() - timedelta(minutes=10)
```

**Line 95:**
```python
exploration.events[-1]["timestamp"] = (datetime.utcnow() - timedelta(minutes=11)).isoformat()
```

**Line 126:**
```python
exploration.start_time = datetime.utcnow() - timedelta(minutes=10)
```

**Line 171:**
```python
exploration.start_time = datetime.utcnow() - timedelta(minutes=10)
```

#### `backend\app\tests\test_services\test_game_loop_exploration.py`

**Line 49:**
```python
exploration.start_time = datetime.utcnow() - timedelta(minutes=10)
```

**Line 92:**
```python
exploration.start_time = datetime.utcnow() - timedelta(hours=2)
```

**Line 147:**
```python
exploration2.start_time = datetime.utcnow() - timedelta(hours=3)
```

**Line 189:**
```python
exploration1.start_time = datetime.utcnow() - timedelta(minutes=10)
```

**Line 190:**
```python
exploration2.start_time = datetime.utcnow() - timedelta(minutes=10)
```

**Line 260:**
```python
exploration.start_time = datetime.utcnow() - timedelta(hours=2)
```

**Line 310:**
```python
exploration1.start_time = datetime.utcnow() - timedelta(hours=2)
```

**Line 311:**
```python
exploration2.start_time = datetime.utcnow() - timedelta(hours=2)
```

**Line 341:**
```python
exploration.start_time = datetime.utcnow() - timedelta(minutes=10)
```

**Line 380:**
```python
exploration.start_time = datetime.utcnow() - timedelta(minutes=10)
```

#### `backend\app\tests\test_services\test_incident_service.py`

**Line 222:**
```python
incident.last_spread_time = datetime.utcnow() - timedelta(seconds=61)
```

**Line 275:**
```python
incident.start_time = datetime.utcnow() - timedelta(minutes=1)
```

### replace(tzinfo=None)

Found 6 occurrence(s) of timezone-naive datetime usage.

#### `analyze_tz.py`

**Line 19:**
```python
"replace(tzinfo=None)": re.compile(r"replace\s*\(\s*tzinfo\s*=\s*None\s*\)"),
```

**Line 195:**
```python
f.write("### 5. Avoid `replace(tzinfo=None)`\n\n")
```

#### `backend\app\api\v1\endpoints\auth.py`

**Line 121:**
```python
user.password_reset_expires = datetime.now(tz=UTC).replace(tzinfo=None) + timedelta(hours=1)
```

**Line 164:**
```python
now = now.replace(tzinfo=None)
```

#### `backend\app\models\pregnancy.py`

**Line 45:**
```python
due_at = self.due_at.replace(tzinfo=None) if self.due_at.tzinfo else self.due_at
```

#### `backend\app\tests\test_api\test_auth.py`

**Line 326:**
```python
assert user.password_reset_expires > datetime.now(tz=UTC).replace(tzinfo=None)
```

### sa.DateTime() (no timezone)

Found 53 occurrence(s) of timezone-naive datetime usage.

#### `analyze_tz.py`

**Line 20:**
```python
"sa.DateTime() (no timezone)": re.compile(r"sa\.DateTime\s*\(([^)]*)\)"),
```

**Line 33:**
```python
if pattern_name == "sa.DateTime() (no timezone)":
```

**Line 172:**
```python
"**Problem:** `sa.DateTime()` without `timezone=True` creates TIMESTAMP WITHOUT TIME ZONE columns.\n\n"
```

**Line 177:**
```python
f.write("sa.Column('created_at', sa.DateTime())\n\n")
```

#### `backend\app\alembic\versions\2026_01_08_1455-34f9ec11db72_initial.py`

**Line 46:**
```python
sa.Column("created_at", sa.DateTime(), nullable=True),
```

**Line 47:**
```python
sa.Column("updated_at", sa.DateTime(), nullable=True),
```

**Line 60:**
```python
sa.Column("created_at", sa.DateTime(), nullable=True),
```

**Line 61:**
```python
sa.Column("updated_at", sa.DateTime(), nullable=True),
```

**Line 69:**
```python
sa.Column("password_reset_expires", sa.DateTime(), nullable=True),
```

**Line 87:**
```python
sa.Column("created_at", sa.DateTime(), nullable=True),
```

**Line 101:**
```python
sa.Column("created_at", sa.DateTime(), nullable=True),
```

**Line 102:**
```python
sa.Column("updated_at", sa.DateTime(), nullable=True),
```

**Line 119:**
```python
sa.Column("created_at", sa.DateTime(), nullable=True),
```

**Line 120:**
```python
sa.Column("updated_at", sa.DateTime(), nullable=True),
```

**Line 144:**
```python
sa.Column("created_at", sa.DateTime(), nullable=True),
```

**Line 145:**
```python
sa.Column("updated_at", sa.DateTime(), nullable=True),
```

**Line 146:**
```python
sa.Column("last_tick_time", sa.DateTime(), nullable=False),
```

**Line 150:**
```python
sa.Column("paused_at", sa.DateTime(), nullable=True),
```

**Line 151:**
```python
sa.Column("resumed_at", sa.DateTime(), nullable=True),
```

**Line 161:**
```python
sa.Column("created_at", sa.DateTime(), nullable=True),
```

**Line 162:**
```python
sa.Column("updated_at", sa.DateTime(), nullable=True),
```

**Line 249:**
```python
sa.Column("created_at", sa.DateTime(), nullable=True),
```

**Line 250:**
```python
sa.Column("updated_at", sa.DateTime(), nullable=True),
```

**Line 262:**
```python
sa.Column("birth_date", sa.DateTime(), nullable=True),
```

**Line 301:**
```python
sa.Column("created_at", sa.DateTime(), nullable=True),
```

**Line 302:**
```python
sa.Column("updated_at", sa.DateTime(), nullable=True),
```

**Line 320:**
```python
sa.Column("start_time", sa.DateTime(), nullable=False),
```

**Line 321:**
```python
sa.Column("end_time", sa.DateTime(), nullable=True),
```

**Line 342:**
```python
sa.Column("created_at", sa.DateTime(), nullable=True),
```

**Line 343:**
```python
sa.Column("updated_at", sa.DateTime(), nullable=True),
```

**Line 377:**
```python
sa.Column("created_at", sa.DateTime(), nullable=False),
```

**Line 401:**
```python
sa.Column("created_at", sa.DateTime(), nullable=True),
```

**Line 402:**
```python
sa.Column("updated_at", sa.DateTime(), nullable=True),
```

**Line 404:**
```python
sa.Column("start_time", sa.DateTime(), nullable=False),
```

**Line 405:**
```python
sa.Column("end_time", sa.DateTime(), nullable=True),
```

**Line 467:**
```python
sa.Column("created_at", sa.DateTime(), nullable=False),
```

**Line 468:**
```python
sa.Column("read_at", sa.DateTime(), nullable=True),
```

**Line 494:**
```python
sa.Column("created_at", sa.DateTime(), nullable=True),
```

**Line 495:**
```python
sa.Column("updated_at", sa.DateTime(), nullable=True),
```

**Line 523:**
```python
sa.Column("created_at", sa.DateTime(), nullable=True),
```

**Line 524:**
```python
sa.Column("updated_at", sa.DateTime(), nullable=True),
```

**Line 527:**
```python
sa.Column("conceived_at", sa.DateTime(), nullable=False),
```

**Line 528:**
```python
sa.Column("due_at", sa.DateTime(), nullable=False),
```

**Line 538:**
```python
sa.Column("created_at", sa.DateTime(), nullable=True),
```

**Line 539:**
```python
sa.Column("updated_at", sa.DateTime(), nullable=True),
```

**Line 556:**
```python
sa.Column("created_at", sa.DateTime(), nullable=True),
```

**Line 557:**
```python
sa.Column("updated_at", sa.DateTime(), nullable=True),
```

**Line 571:**
```python
sa.Column("started_at", sa.DateTime(), nullable=False),
```

**Line 572:**
```python
sa.Column("estimated_completion_at", sa.DateTime(), nullable=False),
```

**Line 573:**
```python
sa.Column("completed_at", sa.DateTime(), nullable=True),
```

**Line 597:**
```python
sa.Column("created_at", sa.DateTime(), nullable=True),
```

**Line 598:**
```python
sa.Column("updated_at", sa.DateTime(), nullable=True),
```

#### `backend\app\alembic\versions\2026_01_22_2259-f36f5baa7bb2_add_death_system_fields_to_dweller_and_.py`

**Line 30:**
```python
op.add_column("dweller", sa.Column("death_timestamp", sa.DateTime(), nullable=True))
```

## Recommendations

### 1. Replace `datetime.utcnow()` with timezone-aware alternatives

**Problem:** `datetime.utcnow()` returns a naive datetime object (no timezone info).

**Solution:**
```python
# OLD (naive)
from datetime import datetime
now = datetime.utcnow()

# NEW (timezone-aware)
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
```

### 2. Replace `datetime.now()` with timezone-aware version

**Problem:** `datetime.now()` without arguments returns a naive datetime.

**Solution:**
```python
# OLD (naive)
now = datetime.now()

# NEW (timezone-aware UTC)
from datetime import timezone
now = datetime.now(timezone.utc)
```

### 3. Use `sa.DateTime(timezone=True)` for PostgreSQL columns

**Problem:** `sa.DateTime()` without `timezone=True` creates TIMESTAMP WITHOUT TIME ZONE columns.

**Solution:**
```python
# OLD (naive)
sa.Column('created_at', sa.DateTime())

# NEW (timezone-aware)
sa.Column('created_at', sa.DateTime(timezone=True))
```

### 4. Handle `datetime.fromisoformat()` carefully

**Problem:** `datetime.fromisoformat()` can parse both naive and aware strings.

**Solution:**
```python
# Parse and ensure timezone-aware
from datetime import timezone
dt = datetime.fromisoformat(timestamp_str)
if dt.tzinfo is None:
    dt = dt.replace(tzinfo=timezone.utc)
```

### 5. Avoid `replace(tzinfo=None)`

**Problem:** Explicitly removing timezone information loses critical data.

**Solution:** Keep timezone information and use proper timezone conversion instead.

## Migration Strategy

1. **Database Schema:** Create migration to convert all `TIMESTAMP` columns to `TIMESTAMP WITH TIME ZONE`
2. **Model Layer:** Update all SQLModel fields to use timezone-aware defaults
3. **Business Logic:** Replace all `datetime.utcnow()` calls with `datetime.now(timezone.utc)`
4. **Tests:** Update test fixtures to use timezone-aware datetimes
5. **Validation:** Add linting rules to prevent new naive datetime usage

## Known Issues

Based on the current analysis, the following areas need attention:

- **Models:** TimeStampMixin uses `datetime.utcnow` as default_factory
- **Security:** JWT token creation uses `datetime.utcnow()`
- **Services:** All business logic services use naive datetimes
- **Database:** PostgreSQL columns defined without timezone support
- **Tests:** Test fixtures create naive datetime objects

---

*Generated by timezone analysis script*
