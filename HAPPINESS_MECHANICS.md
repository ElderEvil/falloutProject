# Happiness System Mechanics

## Overview

The happiness system dynamically adjusts each dweller's happiness based on their conditions, activities, and vault status. Happiness affects vault-wide morale and can influence future events.

## Happiness Range

- **Minimum**: 10%
- **Maximum**: 100%
- **Default**: 50% (new dwellers)

## Happiness Levels & Colors

| Level | Range | Color | Status |
|-------|-------|-------|--------|
| **Excellent** | 75-100% | Bright Green | 😊 Excellent morale! |
| **Good** | 50-74% | Green | 😐 Acceptable morale |
| **Low** | 25-49% | Yellow | 😟 Low morale - needs attention |
| **Critical** | 10-24% | Red | 😢 Critical - dwellers are unhappy! |

## Happiness Changes Per Tick (60 seconds)

### 🔻 Negative Factors (Decrease Happiness)

#### Base Decay
- **-0.5 per tick** - Natural happiness decay

#### Vault Conditions
- **Low Resources** (<20% power/food/water): **-2.0 per tick**
- **Critical Resources** (<5% power/food/water): **-5.0 per tick**
- **Active Incidents**: **-3.0 per incident per tick**

#### Dweller Status
- **Idle** (not assigned): **-1.0 extra per tick**
- **Combat** (fighting incidents): **-2.0 per tick**

#### Health & Needs
- **Low Health**:
  - <30% health: **-2.0 per tick**
  - 30-50% health: **-1.0 per tick**
- **High Radiation** (>50): **-1.0 per tick**

### 🔺 Positive Factors (Increase Happiness)

#### Work & Purpose
- **Working in Room**: **+1.0 per tick**
- **Training**: **+0.5 per tick** (learning and self-improvement)
- **High Health** (>80%) while working: **+0.5 extra per tick**

#### Room-Specific Bonuses
- **Living Quarters**: **+1.5 per tick** (romance, privacy, comfort)
- **Radio Room** (working in room): **+1.0 per tick** (entertainment, music)
- **Radio Room** (Happiness Mode): **+1.0 to +10.0 per tick** (based on speedup multiplier, applies to ALL dwellers)
- **Recreation Room** (future): **+2.0 per tick** (lounges, game rooms)

#### Relationships
- **Has Partner**: **+0.17 per tick** (PARTNER_HAPPINESS_BONUS / 60)
- **Partner in Same Room**: **+1.0 extra per tick**

#### Vault Prosperity
- **High Resources** (>80% all): **+0.5 per tick**
- **No Active Incidents**: **+0.3 per tick**

## Detailed Breakdown by Activity

### 💼 Working in Production Rooms (Power/Water/Food)
**Net Change**: +1.5 to +3.0 per tick
- Base working bonus: +1.0
- High health bonus: +0.5 (if >80% health)
- No incidents bonus: +0.3
- High resources bonus: +0.5
- Minus base decay: -0.5

### 🏠 Living Quarters
**Net Change**: +2.5 to +5.0 per tick
- Working bonus: +1.0
- Living quarters bonus: +1.5
- Partner nearby: +1.0 (if partner also in room)
- Partner bonus: +0.17
- High health: +0.5
- No incidents: +0.3
- High resources: +0.5
- Minus base decay: -0.5

### 📻 Radio Room (Working)
**Net Change**: +2.0 to +3.5 per tick
- Working bonus: +1.0
- Radio room bonus: +1.0
- High health: +0.5
- No incidents: +0.3
- High resources: +0.5
- Minus base decay: -0.5

### 📻 Radio Room (Happiness Mode - ALL Dwellers)
**Net Change**: +0.5 to +9.5 per tick (based on speedup)
- Radio happiness mode: +1.0 to +10.0 (RADIO_HAPPINESS_BONUS × speedup multiplier)
- No incidents: +0.3
- High resources: +0.5
- Minus base decay: -0.5

**Speedup Examples:**
- 1.0x speedup: +1.0 per tick to all dwellers
- 4.5x speedup: +4.5 per tick to all dwellers
- 10.0x speedup: +10.0 per tick to all dwellers

**Note**: Radio happiness mode is vault-wide! All dwellers benefit regardless of location.

### 💪 Training Room
**Net Change**: +0.5 to +1.8 per tick
- Training bonus: +0.5
- No incidents: +0.3
- High resources: +0.5
- Minus base decay: -0.5

### ⚔️ Combat (Fighting Incidents)
**Net Change**: -2.5 to -7.5 per tick
- Combat penalty: -2.0
- Incident penalty: -3.0 (per incident)
- Base decay: -0.5
- Possible health loss: -1.0 to -2.0 (if injured)

### 😴 Idle (Unassigned)
**Net Change**: -1.5 per tick (worsens with vault conditions)
- Base decay: -0.5
- Idle penalty: -1.0
- Resource penalty: 0 to -5.0 (if resources low)
- Incident penalty: 0 to -3.0 per incident

## Vault-Wide Happiness

The vault happiness is calculated as the **average of all dwellers' happiness**. This is updated every game tick and displayed in the vault overview.

## API Endpoints

### Get Happiness Modifiers
```
GET /api/v1/dwellers/{dweller_id}/happiness_modifiers
```

Returns detailed breakdown of all factors affecting a dweller's happiness:
```json
{
  "current_happiness": 75,
  "positive": [
    {"name": "Working", "value": 1.0},
    {"name": "Has Partner", "value": 0.17},
    {"name": "High Health", "value": 0.5}
  ],
  "negative": [
    {"name": "Base Decay", "value": -0.5},
    {"name": "Active Incidents (1)", "value": -3.0}
  ]
}
```

## Radio Happiness Mode

The radio room has two modes:

1. **Recruitment Mode** (default): Attracts new dwellers to the vault
2. **Happiness Mode**: Boosts happiness for ALL dwellers in the vault

When in **Happiness Mode**:
- The happiness bonus applies to EVERY dweller, regardless of location
- The bonus scales with the **Speedup Multiplier** (1x to 10x)
- Formula: `happiness_bonus = RADIO_HAPPINESS_BONUS (1.0) × total_speedup`
- Multiple radio rooms: speedup values are summed together

**Example with 2 radio rooms:**
- Radio Room 1: 3.0x speedup
- Radio Room 2: 2.5x speedup
- Total speedup: 5.5x
- Happiness bonus: +5.5 per tick to ALL dwellers

This makes radio happiness mode extremely powerful for vault-wide morale!

## Configuration

All constants can be adjusted in `app/config/game_balance.py`:

```python
# Decay rates
BASE_HAPPINESS_DECAY = 0.5
RESOURCE_SHORTAGE_DECAY = 2.0
CRITICAL_RESOURCE_DECAY = 5.0
INCIDENT_HAPPINESS_PENALTY = 3.0
IDLE_HAPPINESS_DECAY = 1.0

# Gain rates
WORKING_HAPPINESS_GAIN = 1.0
HIGH_HEALTH_BONUS = 0.5
PARTNER_NEARBY_BONUS = 1.0

# Room bonuses (working in room)
LIVING_QUARTERS_HAPPINESS_BONUS = 1.5
RADIO_ROOM_HAPPINESS_BONUS = 1.0  # When working in radio room
RECREATION_ROOM_HAPPINESS_BONUS = 2.0

# Radio happiness mode (vault-wide)
RADIO_HAPPINESS_BONUS = 1.0  # Multiplied by speedup, affects all dwellers

# Combat
COMBAT_HAPPINESS_PENALTY = 2.0
```

## Future Enhancements

### Planned (v1.9+)
- [ ] **Happiness-Based Events**: Low happiness (<25%) triggers negative events
- [ ] **Production Bonuses**: High happiness (>75%) increases production efficiency
- [ ] **Relationship Formation**: Happiness affects romance/friendship formation rates
- [ ] **Happiness Change Notifications**: Toast notifications when dweller happiness changes significantly
- [ ] **Happiness History**: Track happiness trends over time

### Possible (v2.0+)
- [ ] **Personality Traits**: Different dwellers have different happiness baselines
- [ ] **Social Activities**: Special rooms/events that boost happiness
- [ ] **Decoration System**: Vault decorations increase base happiness
- [ ] **Mood System**: Short-term mood separate from long-term happiness
