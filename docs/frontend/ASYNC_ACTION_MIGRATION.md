# `useAsyncAction` migration manifest

This manifest records the handling contract for the remaining manual loading
blocks found during v2.30. It is deliberately checked in before caller
migration so that error-return behaviour is not changed by a mechanical refactor.

| Location | Operations | Contract | Notes |
| --- | --- | --- | --- |
| `modules/map/stores/map.ts` | map fetch | return-null | Store-owned loading state must remain the source of truth. |
| `modules/social/views/RelationshipsView.vue` | relationship fetch | return-null | View can render an empty/error state after a failed fetch. |
| `modules/social/stores/relationship.ts` | CRUD and refresh | rethrow | Callers use failures for dialog/action flow. |
| `modules/social/stores/pregnancy.ts` | pregnancy CRUD | rethrow | Mutation callers need to preserve their current failure path. |
| `modules/exploration/stores/exploration.ts` | send, fetch, recall, complete | rethrow | Existing callers catch these actions to show operation-specific feedback. |
| `modules/storage/views/StorageView.vue` | inventory fetch | return-null | Loading is local to the view. |
| `modules/vault/views/HappinessView.vue` | dashboard fetch | return-null | Loading is local to the view. |
| `modules/vault/stores/vault.ts` | vault fetch | rethrow | Dependent view initialization needs the failure signal. |
| `modules/dwellers/stores/dwellerFilter.ts` | filtered dweller fetch | return-null | Store already surfaces fetch errors and can use the composable result. |
| `modules/vault/views/VaultView.vue` | vault initialization | bespoke-excluded | Several coordinated requests share local state; keep explicit orchestration. |
| `modules/combat/stores/equipment.ts` | equipment fetch/equip | rethrow | Mutating callers need to preserve their failure path. |
| `modules/progression/stores/quest.ts` | quest fetch/refresh | bespoke-excluded | `silent` requests intentionally do not toggle the shared loading flag. |
| `modules/progression/stores/training.ts` | training fetch | rethrow | Caller flow depends on thrown action errors. |
| `modules/radio/stores/radio.ts` | radio fetch | return-null | Read-only state refresh. |
| `modules/vault/components/shell/NotificationBell.vue` | notification fetch | return-null | Loading is local to the component. |
| `modules/chat/components/DwellerChatPage.vue` | chat session fetch | return-null | Loading is local to the component. |
| `modules/auth/components/LoginFormTerminal.vue` | sign-in submit | rethrow | Form must retain its existing authentication failure flow. |
| `modules/dwellers/stores/dwellerDeath.ts` | revive/death operations | bespoke-excluded | Uses an in-flight concurrency counter (`deadLoadingCount`). |
| `modules/dwellers/views/DwellersView.vue` | AI portrait generation | bespoke-excluded | Uses a per-dweller loading map (`generatingAI`). |

`bespoke-excluded` sites must retain an inline `// bespoke: see
useAsyncAction contract` note when touched. `useAsyncAction` itself owns a
pending counter so it remains safe for overlapping single-operation requests;
the exclusions are for callers whose UI needs a distinct counter or key map.
