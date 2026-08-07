# Vault Balance Simulator Findings

Generated: 2026-08-07
Simulators: 4 focused balance scripts

---

## Executive Summary

All four focused simulators run cleanly and produce stable Monte Carlo averages. However, **every subsystem shows signs of being too forgiving under default parameters** — there is insufficient tension between growth and constraints. The game as currently parameterized would present no meaningful challenge to players.

---

## 1. Exploration Balance (`simulate_exploration_balance.py`)

### Observation
Exploration mechanics work as intended. With default parameters (10% discovery chance, 600s event interval, 2 concurrent explorations):

- **Discovery rate**: ~1.3 discoveries/hour — healthy pace
- **Map growth**: ~1.5 points/hour from all sources (discoveries + bio-places + home vault)
- **Population explosion**: Starting from 10 dwellers, population reaches ~1,230 in 24h (births=~1,214, deaths≈0)

### Finding
**Exploration is not the bottleneck.** The map grows at a reasonable rate, but population growth is completely decoupled from it. Recruitment adds ~3–4 dwellers per day, which is negligible compared to the ~1,200 from breeding. The exploration system could be balanced independently; the real problem is elsewhere.

---

## 2. Room Economy (`simulate_room_balance.py`)

### Observation
The room simulator models actual room templates from `backend/app/data/vault/rooms.json` with costs, prerequisites, and per-room production.

With defaults (500 caps, 10 dwellers, build interval 2h):

- **Room builds**: 0.0 over 24h — no new rooms constructed
- **Room upgrades**: 1.0 over 24h — one existing room gets upgraded to tier 2
- **Population cap**: 14 (from 1 Living room, tier 1) — never expands
- **Final population**: ~1,290 in 24h — 92× over capacity
- **Caps remaining**: 0 — economy is exhausted immediately

### Finding
**The room economy is broken.** Starting caps (500) are insufficient to build even a single additional room after the initial 4. With Power Generator at 100 caps + 25 incremental, Diner at 100, Water Treatment at 100, and Living room at 100, the vault door itself is already a sunk cost not accounted for. The AI builds logic tries to construct rooms when resources run low, but caps are depleted within the first few hours, leaving the vault with:
- 3 production rooms serving 1,290 dwellers
- 0 additional living quarters despite the "build Living room when near cap" rule
- Population capped at 14 but breeding continues unabated

**Implication**: Players would hit a "soft wall" where resources stay at 100% (production outpaces consumption due to simplified scaling) but no new rooms can be built, making the room-building mechanic irrelevant after hour 2.

**Recommendation**: Either increase starting caps to 2,000–5,000, reduce room costs by 50–70%, or make caps regenerate from incident rewards / exploration loot.

---

## 3. Incident System (`simulate_incident_balance.py`)

### Observation
The incident simulator uses real incident types (fire, radroach, mole rat, raider, feral ghoul, deathclaw) with weighted spawn rates and difficulty ranges.

With defaults (20 dwellers, avg SPECIAL 4, level 5, raider power 10):

- **Total incidents**: ~1.6 over 24h
- **Survival rate**: 100% — every incident is resolved instantly
- **Deaths**: 0.0 — no casualties from any incident type
- **Deathclaw incidents**: ~0.1 per day, 0 deaths
- **Max concurrent**: ~0.8 — incidents rarely overlap

### Finding
**Incidents are trivial.** Dweller combat power is calculated as:
```
power = adults × ((strength×0.4 + endurance×0.3 + agility×0.3) + level×2)
       = 18 × ((4×0.4 + 4×0.3 + 4×0.3) + 5×2)
       = 18 × (4.0 + 10.0)
       = 252
```

A deathclaw at difficulty 10 has raider power = 10 × 10 = 100. The vault's 252 power outmatches the hardest incident by 2.5×.

Even sweeping `base_raider_power` from 5 → 25 changed nothing because the gap is so large. The `spread_duration` (60s) is also too short for incidents to persist — they resolve in 0–1 ticks.

**Implication**: Players will never lose dwellers to incidents unless the vault is severely understaffed or underleveled. The incident system becomes a free caps dispenser (reward = 50 + difficulty×20).

**Recommendation**:
- Increase `base_raider_power` to 25–40, or
- Reduce level bonus multiplier from 2 to 0.5–1.0, or
- Make incidents spawn in waves (multiple simultaneous), or
- Increase `spawn_chance_per_hour` to 0.15–0.20 and `max_active_incidents` to 5–8

---

## 4. Happiness System (`simulate_happiness_balance.py`)

### Observation
The happiness simulator models all gain and loss sources from the real `HappinessConfig`:
- **Losses**: base decay (0.5/tick), resource shortage (2.0/tick), incidents (3.0/tick), idle dwellers (1.0/tick), combat (2.0/tick)
- **Gains**: working (1.0/worker), healthy (0.5/healthy dweller), partnered (1.0/partnered), rooms (LQ=1.5, TR=0.5, RD=1.0), training (0.5/trainee), vault-wide (0.3–0.5)

With defaults (20 dwellers, 70% working, 80% healthy, 30% partnered):

- **Mean happiness**: 100.0% — pegged at cap
- **Time below 75%**: 0.0%
- **Time above 90%**: 100.0%
- **Productivity multiplier**: 1.00 (100% of nominal)
- **Sweeping base_decay up to 1.5**: Still 100% happiness

### Finding
**Happiness has no tension.** The per-dweller gains scale linearly with population, while penalties are either flat (base_decay) or situational (incidents, resource shortage). With 12 working dwellers:
```
gain_from_working = 12 × 1.0 = +12.0/tick
base_decay = -0.5/tick
net_from_work = +11.5/tick
```

Add 16 healthy (+8.0), 6 partnered (+6.0), 1 training (+0.5), rooms (+3.0), vault-wide (+0.8) = **+29.3/tick net**. Even with 3 incidents (-9.0) and critical resources (-15.0), the net is still **+5.3/tick**.

**Implication**: Happiness is effectively a non-mechanic. It will always be at 100% unless the vault is catastrophically mismanaged (0% working, 100% incidents, 0% resources). The productivity multiplier (0.5 + happiness/200) will always be near 1.0.

**Recommendation**:
- Reduce `working_gain` from 1.0 to 0.2–0.3, or
- Make `working_gain` scale with `1/sqrt(workers)` so marginal returns diminish, or
- Increase `base_decay` to 2.0–3.0, or
- Cap total room bonus at 2.0 regardless of room count

---

## Cross-System Synthesis

| System | Current State | Tension Level |
|---|---|---|
| Exploration | Healthy | ✅ Balanced |
| Room Building | Caps-limited early, but objectives/quests/exploration provide income | ⚠️ OK with other systems |
| Incident Combat | Easy (100% survival) — intentional for early-game feel | ✅ OK for now |
| Happiness | Pegged at 100% — minor decay adjustment may help | ⚠️ Too generous |
| Population Growth | Exponential, uncapped — needs breeding constraint | 🔴 Uncontrolled |

**The core issue**: Breeding has no population pressure. With `conception_chance=20%/tick` and 5 eligible pairs, births scale linearly with time regardless of vault capacity. This dwarfs all other growth sources (exploration recruits ~3/day, room builds ~0/day).

**Accepted design decisions** (from review):

1. **Room economy**: No change needed — objectives, quests, and exploration provide additional caps income not modeled in the standalone simulator.
2. **Combat difficulty**: Keep easy for now — 100% survival is acceptable for the current target experience.
3. **Happiness**: Minor decay adjustment may be explored later.
4. **Breeding**: **Needs a cooldown or cap-scaled conception chance** — this is the highest-priority fix to prevent runaway population.

### Proposed Breeding Mechanics (to be implemented)

**Option A — Hard Cap (simplest)**
```
if population >= population_cap:
    conception_chance = 0
```
- Pros: Brutally clear, no hidden math
- Cons: Abrupt wall; players hit cap and breeding stops entirely

**Option B — Soft Scaling (recommended)**
```
cap_ratio = population / population_cap
effective_chance = base_chance × max(0.05, 1.0 - cap_ratio)
```
- At 50% cap → 50% of base chance (10% → 5%)
- At 90% cap → 10% of base chance (10% → 1%)
- At 100% cap → 5% floor (10% → 0.5%)
- Pros: Smooth pressure ramp, intuitive feedback
- Cons: Still allows slow overgrowth; needs companion mechanic

**Option C — Per-Mother Cooldown**
```
if (now - mother.last_conception_time) < pregnancy_duration_hours × 2:
    conception_chance = 0
```
- Pros: Realistic, caps births per female regardless of vault size
- Cons: Requires tracking per-dweller state; complicates the model

**Option D — Combined (B + C) — final recommendation**
Use soft scaling (Option B) as the primary pressure, with a short per-mother cooldown (e.g., `pregnancy_duration × 1.5`) as a secondary brake. This gives:
- Early game: fast growth (cap_ratio ~0.2 → 80% effective chance)
- Mid game: noticeable slowdown (cap_ratio ~0.6 → 40% effective chance)
- Late game: crawl (cap_ratio ~0.9 → 10% effective chance)
- Emergency: if population exceeds cap by >10%, hard stop to 0%

**Simulator update needed**: Add `population_cap` to `ExplorationConfig` and `RoomConfig`, model `VaultState.population_cap()`, and scale `conception_chance` in `_process_breeding()` using Option B or D.

**Expected outcome with Option B**:
- Starting from 10 dwellers, cap ~14 (4 rooms), growth would slow naturally around hour 2–3
- Population would plateau near cap + 10–20% instead of 1,200+
- Room building becomes meaningful because living quarters directly enable more births

---

*Simulators available in `backend/scripts/` — run with `--sweep <param>` to explore the parameter space.*
