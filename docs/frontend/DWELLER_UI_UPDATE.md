# Dweller Detail Page Structure Update

## Completed

The dweller detail page was simplified to remove the previous Container → Pane → Panel prop and event forwarding chain.

- `useDwellerDetail` owns detail-page loading, UI state, and action orchestration.
- `DwellerDetailContainer` creates and provides a typed `DwellerDetailContext`.
- Detail-pane, panel, and tab components consume that context directly.
- Detail sections are defined by the `dwellerDetailSections` registry and rendered dynamically by `DwellerPanel`.
- `MapPlaceLink` was moved from a component export to `models/dweller.ts`.
- Navigation between `:dwellerId` route params retains stale-request protection.

## Deliberate boundaries

- This is a frontend-only refactor; no backend model or API changes were made.
- The section registry includes only the currently available sections: Profile, Appearance, Stats, Equipment, and Family.
- Pets and apprentices are not represented until their backend support and UI requirements exist.

## Validation

Before handoff, run:

```bash
cd frontend
pnpm run lint
pnpm run typecheck
pnpm run test:run
```
