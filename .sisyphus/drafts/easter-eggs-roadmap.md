# Draft: Easter Eggs (Roadmap features)

## Requirements (unconfirmed)
- Implement roadmap items related to "Easter Eggs & Hidden Features" (ROADMAP v2.8.0 planned).

## Requirements (confirmed so far)
- First slice: **Gary Virus** + **Version number glitch (fake crash screen)**.
- Persistence: **frontend-only** (no backend validation/awards in this slice).
- Gating: **all users**.
- Verification: **automated tests** preferred.

## Decisions (confirmed)
- Gary Virus implementation: **overlay/glitch layer** (not true string replacement).
- Version glitch (7 clicks): **visual-only reboot** (no rewards).
- Click target for 7 clicks: **About page version**.

## Roadmap Items (source: ROADMAP.md)
- The "Gary" Virus (Vault 108 tribute) — rename dweller to "Gary" → temporary UI text override + glitch.
- "It Just Works" (Todd tribute) — rename dweller to "Todd" → buffs + special audio/visual.
- Version number glitch (fake crash screen) — click version 7 times → overlay + reward.
- Konami Code developer mode — key sequence → unlock Debug Room and related behaviors.
- Quantum Mouse trail effect.

## Additional Roadmap Notes (later section)
- Easter egg event tracking (analytics)
- API endpoints for easter egg rewards
- Global state management for active easter eggs
- Unit tests for each trigger
- Optional hints in loading tips
- Optional hidden achievement badges

## Open Questions
- Which specific roadmap bullet(s) are in scope?
- What counts as an easter egg (UI-only, gameplay effect, hidden command, etc.)?
- Where should they live (frontend only vs backend + persistence)?
- Are easter eggs purely cosmetic, or do they affect resources/dwellers?
- Should they be discoverable via hints, or completely hidden?

## Decisions Needed (to plan correctly)
- For **Gary Virus**: do you want a *true text replacement* (every label becomes "Gary") or an *overlay/glitch layer* that visually "Gary-fies" the UI without rewriting all text?
- For **Version glitch crash** (7 clicks): should it be purely visual (no rewards) or show a cosmetic reward/toast only (since frontend-only)?
- Where should the version click target live: footer global version label, About page version, or both?

## Scope Boundaries (pending)
- INCLUDE: define triggers, content, storage/persistence, UI/UX, tests/verification.
- EXCLUDE: anything not explicitly selected from ROADMAP.
