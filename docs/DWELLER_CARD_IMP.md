Below is a **short, actionable UI doc** you can drop next to `ui.md` (or merge
into it).
It focuses only on **what to change** and **why**, without redesign scope creep.

---

# Dweller Detail Layout – Actionable Improvements

This document defines **small, low‑risk layout improvements** for the Dweller
detail screen to improve readability, balance, and UX while preserving the
Fallout/terminal aesthetic.

---

## Goals

- Improve readability of long text
- Reduce unused horizontal space
- Make stats and actions scannable
- Keep visual identity unchanged

---

## Layout Changes

### 1. Switch to a 2‑Column Layout

**Why:** Current layout is left‑heavy and wastes space.

**Action:**

- Left column: fixed width (identity & stats)
- Right column: flexible width (narrative content)

```mermaid
flowchart LR
    L[Identity + Stats + Actions] --> R[Biography / Details]
```

---

### 2. Constrain Biography Text Width

**Why:** Very long lines reduce readability.

**Action:**

- Limit bio text to ~60–75 characters per line

```css
.bio {
    max-width: 65ch;
    line-height: 1.5;
}
```

---

### 3. Group Identity Information

**Why:** Users decide actions immediately after identifying the character.

**Action:**

- Group together:
    - Avatar
    - Name + status badge
    - Level / health / happiness
- Place primary actions nearby (Chat, Assign, Recall)

---

### 4. Improve SPECIAL Stats Scannability

**Why:** Stats are currently flat and hard to compare.

**Action:**

- Show numeric values alongside bars
- Keep bars, but emphasize values

```text
Strength     2 ▓▓░░░
Perception   1 ▓░░░░
Endurance    2 ▓▓░░░
```

Optional:

- Slight highlight on highest stat
- Slight dim on lowest stat

---

### 5. Clarify Expand / Collapse Control

**Why:** Chevron affordance is easy to miss.

**Action:**

- Increase hit area
- Add hover glow
- Support keyboard toggle

---

## Accessibility (Surface Level)

- Bio text readable without glow
- Focus styles visible on all interactive elements
- Actions use real `<button>` elements

---

## Summary

✅ Two‑column layout
✅ Readable biography text
✅ Clear identity → action flow
✅ More scannable stats
✅ Minimal visual change

These changes improve UX immediately without altering theme or structure.

---
