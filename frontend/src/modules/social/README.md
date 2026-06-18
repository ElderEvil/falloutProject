# Social

Social system module managing dweller relationships and pregnancy mechanics. Tracks relationship pairs, children, and pregnancy progression with dedicated card components for each entity.

## Routes

- `/vault/:id/relationships` — RelationshipsView

## Key Files

- `views/RelationshipsView.vue` — relationship management view
- `stores/relationship.ts` — relationship state management
- `stores/pregnancy.ts` — pregnancy state management
- `components/relationships/RelationshipCard.vue` — relationship pair display
- `components/relationships/RelationshipList.vue` — relationship listing
- `components/relationships/ChildrenList.vue` — children listing
- `components/pregnancy/PregnancyCard.vue` — pregnancy status card
- `components/pregnancy/PregnancyTracker.vue` — pregnancy progress tracker
- `models/` — relationship and pregnancy type definitions
