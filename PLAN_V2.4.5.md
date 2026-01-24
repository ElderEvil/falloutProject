# Plan v2.4.5 - Bug Fixes & Fun Features

> **Status:** Planned
> **Branch:** `feat/v2.4.5`
> **Date:** 2026-01-25

## 🐛 Bug Fixes

### 1. Population Progress Bar Not Showing
**Priority:** High
**Location:** `frontend/src/modules/vault/views/VaultView.vue`

**Issue:**
- Dweller count displays correctly (e.g., "20 / 32")
- Progress bar remains empty despite correct values
- Calculation returns correct percentage but bar doesn't render

**Investigation Needed:**
- Verify `populationUtilization` computed value
- Check if CSS styling is preventing bar visibility
- Confirm `:style="{ width: ... }"` is applying correctly
- Test with browser devtools to see actual computed width

**Expected Behavior:**
- 20/32 dwellers should show ~62% filled progress bar
- Color should change at 75% (yellow) and 90% (red)

---

## 🎮 New Features

### 2. Emotional Damage System
**Priority:** Medium
**Category:** Fun/Comedy Feature

**Concept:**
- Overseer can "damage" dwellers with harsh words/criticism
- Affects dweller happiness/morale (not actual HP)
- Funny/comedic feature for player interaction
- Think: "critical hit to their feelings" 💔

**Implementation Details:**
- *(User will provide more details later)*

**Potential Design:**
- Add "Criticize Dweller" action in dweller detail modal
- Random cruel/funny overseer phrases
- Reduces happiness temporarily
- Maybe adds "Emotionally Damaged" status effect
- Could tie into relationship system (dweller remembers who hurt their feelings)

**Technical Scope:**
- Backend: New endpoint for emotional damage action
- Frontend: UI button/action in dweller interactions
- Database: Track emotional damage events (optional)
- Effects: Temporary happiness debuff

---

## 📋 Checklist

- [ ] Fix population progress bar rendering
- [ ] Design emotional damage system mechanics
- [ ] Implement emotional damage backend
- [ ] Implement emotional damage frontend UI
- [ ] Add tests for both features
- [ ] Update documentation
