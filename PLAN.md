# Current Development Plan

## Active: v2.10.0 - Quests & Objectives Phase 1

**Status**: Planning Complete | **Estimated**: 3-4 weeks

---

## Mission
Transform the existing basic quests and objectives into a fully functional, automated system with structured data, reward distribution, and prerequisite chains.

---

## Quick Overview

| Phase | Focus | Key Deliverables |
|-------|-------|------------------|
| **P1** | Core Infrastructure | Structured requirements/rewards, RewardService, quest types |
| **P2** | Prerequisites & Chains | Quest prerequisites, quest chains, unlock progression |
| **P3** | Progress Automation | Event system, objective evaluators, real-time updates |
| **P4** | UI/UX Enhancements | Quest detail view, progress bars, notifications |
| **P5** | Data Migration | Convert string-based quests to structured format |
| **P6** | Testing | 80%+ coverage, integration tests |

---

## What's In Scope

✅ **Quest Prerequisites** - Lock quests until requirements met (level, items, previous quests)  
✅ **Quest Chains** - Multi-quest sequences with automatic progression  
✅ **Reward Distribution** - Automatic granting of caps, items, dwellers, resources  
✅ **Quest Types** - Main, side, daily, repeatable with visual distinction  
✅ **Progress Automation** - Objectives auto-update when you collect/build/train  
✅ **Real-time Updates** - WebSocket notifications for progress/completion  
✅ **Better UI** - Quest detail view, progress bars, reward previews  

---

## What's Deferred to Phase 2 (v2.12+)

❌ **Combat System** - Battle mechanics, enemies, combat resolution  
❌ **Quest Parties** - Sending dwellers on quests (UI only in Phase 1)  
❌ **Time-Limited Events** - Complex event scheduling  
❌ **Advanced Rewards** - Buffs, temporary bonuses, cosmetics  

---

## Key Files

- **Full Plan**: `.sisyphus/plans/v2.10.0-quests-objectives-phase1.md`
- **Roadmap**: `ROADMAP.md`
- **Backend Models**: `backend/app/models/quest.py`, `backend/app/models/objective.py`
- **Frontend Stores**: `frontend/src/modules/progression/stores/quest.ts`, `frontend/src/modules/progression/stores/objectives.ts`

---

## Success Criteria

1. Player can view quests with clear prerequisites and rewards
2. Player can start quests only when prerequisites are met
3. Player sees objective progress update automatically
4. Player receives rewards automatically on completion
5. Player can complete multi-quest chains
6. Developer can add new quests easily via JSON with full structure

---

## Next Steps

1. Review full plan in `.sisyphus/plans/v2.10.0-quests-objectives-phase1.md`
2. Start with P1: Core Infrastructure (database schema changes)
3. Create feature branch: `feat/v2.10.0-quests-objectives`

---

*Last updated: February 8, 2026*  
*See ROADMAP.md for broader release timeline*
