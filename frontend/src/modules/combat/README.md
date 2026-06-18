# Combat

Combat incidents and equipment module. Manages combat encounter data, weapon and outfit equipment cards, and incident alerts. Integrated into VaultView rather than having standalone routes.

## Routes

- _(no dedicated routes — embedded in VaultView)_

## Key Files

- `stores/incident.ts` — combat incident state management
- `stores/equipment.ts` — equipment (weapons/outfits) state management
- `components/incidents/CombatModal.vue` — combat encounter modal
- `components/incidents/IncidentAlert.vue` — incident notification alert
- `components/equipment/WeaponCard.vue` — weapon equipment display card
- `components/equipment/OutfitCard.vue` — outfit equipment display card
- `models/incident.ts` — incident type definitions
- `models/equipment.ts` — equipment type definitions
- `api/` — combat API client layer
- `services/` — combat business logic services
