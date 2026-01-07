# Codebase Audit Report - January 6, 2026

## Executive Summary

**Priorities**: Consistency > Performance > DX/UX

This audit identifies opportunities to improve code consistency, reduce duplication, and enhance developer experience through better type safety and shared utilities.

---

## 📊 Current State

### Statistics
- **Total Vue Components**: 88 files
- **Components with Scoped Styles**: 54 (61%)
- **Views with Scoped Styles**: 16 (100%)
- **Total Scoped Styles Size**: ~134KB
- **Composables**: 10 files
- **Manual Type Models**: 441 lines across 11 files (41 type exports)
- **Generated API Types**: 9,436 lines (auto-generated)
- **Files Importing from `/models`**: 36 files

### Key Findings

#### ✅ **GOOD**
1. **OpenAPI Type Generation Working** - `api.generated.ts` exists with 9,436 lines
2. **Models Already Using Generated Types** - Most models re-export from `api.generated.ts`
3. **Composables Are Clean** - Only 10 composables, well-organized
4. **Type Safety** - 66 files have manual interface definitions (good TypeScript coverage)

#### ⚠️ **NEEDS IMPROVEMENT**

1. **Style Duplication** (Priority 1 - Consistency)
   - 70 files with scoped styles (~134KB)
   - Common patterns repeated 45+ times:
     - `.main-content` (45x)
     - `.terminal-input` (14x)
     - `.terminal-button` (14x)
     - `.empty-state` (14x)
     - `.modal-body` (10x)
   - **Impact**: Maintenance burden, inconsistent spacing/colors

2. **Partial Type Migration** (Priority 2 - DX)
   - Models correctly re-export from `api.generated.ts` ✅
   - But 441 lines of manual type definitions still exist
   - Some types like `VisualAttributes` should be in `api.generated.ts`
   - **Impact**: Type drift between frontend/backend

3. **Component Organization** (Priority 3 - DX)
   - 88 components with varying style approaches
   - Mix of inline styles, scoped styles, and Tailwind
   - No shared base component styles
   - **Impact**: Inconsistent UI, harder onboarding

---

## 🎯 Recommended Actions

### Phase 1: Style Consolidation (High Priority)

**Goal**: Reduce scoped styles by 50%, create shared utility classes

#### Actions:
1. **Create `frontend/src/assets/styles/components.css`**
   - Extract common patterns (`.main-content`, `.terminal-input`, `.modal-body`, etc.)
   - Define reusable terminal-theme utilities
   - Move repeated animations (pulse, flicker, etc.)

2. **Create `frontend/src/assets/styles/utilities.css`**
   - Terminal-themed utility classes
   - Layout utilities (`.vault-layout`, `.section-title`)
   - State utilities (`.loading-state`, `.error-state`, `.empty-state`)

3. **Update `main.ts`** to import shared styles
   ```ts
   import './assets/styles/components.css'
   import './assets/styles/utilities.css'
   ```

4. **Refactor Components** (Target: 35 components in Phase 1)
   - Replace scoped styles with shared classes
   - Keep only component-specific styles scoped
   - Update Tailwind config for terminal theme

**Expected Results**:
- **-50KB** scoped styles
- **+2KB** shared styles
- **Net savings**: ~48KB
- **Consistency**: Same spacing/colors everywhere

---

### Phase 2: Type System Cleanup (Medium Priority)

**Goal**: Full migration to OpenAPI-generated types

#### Actions:
1. **Audit Backend Schemas**
   - Ensure all frontend types exist in backend Pydantic models
   - Add missing schemas (`VisualAttributes`, `Special`, etc.)
   - Run `pnpm types:generate` to regenerate

2. **Update Models**
   - Keep models as re-export files only
   - Remove manual type definitions
   - Add JSDoc comments for developer guidance

3. **Update Imports**
   - Search/replace: `from '@/models/` → `from '@/types/api.generated'`
   - Keep model files for backward compatibility (with deprecation notice)

**Expected Results**:
- **-441 lines** of manual types
- **100% type safety** with backend
- **Zero type drift**
- **Better IDE autocomplete**

---

### Phase 3: Composables Review (Low Priority)

**Goal**: Ensure composables are optimized and not duplicated

#### Current Composables (10):
```
✅ useAuth.ts           - Auth state management
✅ useFlickering.ts     - Terminal flicker effect
✅ useHoverPreview.ts   - Hover preview functionality
✅ useNotifications.ts  - Notification system
✅ useRoomInteractions.ts - Room interaction logic
✅ useSidePanel.ts      - Side panel state
✅ useTheme.ts          - Theme management
✅ useToast.ts          - Toast notifications (recently improved)
✅ useVaultOperations.ts - Vault CRUD operations
✅ useVisualEffects.ts  - Visual effects (scanlines, CRT)
```

#### Actions:
1. **Audit for Duplication**
   - Check if `useNotifications` and `useToast` can be merged
   - Review `useVisualEffects` vs `useFlickering` overlap

2. **Add JSDoc Comments**
   - Document each composable's purpose
   - Add usage examples
   - Document return types

3. **Performance Check**
   - Ensure refs are properly readonly where needed
   - Check for unnecessary reactivity

**Expected Results**:
- Potentially merge 2 composables
- Better documentation
- Improved DX

---

## 📋 Implementation Plan

### Week 1: Style Consolidation
- [x] Audit complete ✅
- [ ] Create `components.css` with extracted common styles
- [ ] Create `utilities.css` with terminal utilities
- [ ] Refactor 10 high-usage components (DwellerCard, RoomCard, etc.)
- [ ] Test visual consistency
- [ ] Commit: "refactor: consolidate component styles"

### Week 2: More Style Refactoring
- [ ] Refactor remaining 25 components
- [ ] Update views to use shared styles
- [ ] Remove duplicate style blocks
- [ ] Measure bundle size reduction
- [ ] Commit: "refactor: complete style consolidation"

### Week 3: Type System
- [ ] Review backend schemas for missing types
- [ ] Add missing Pydantic models
- [ ] Regenerate `api.generated.ts`
- [ ] Update model files to re-export only
- [ ] Update imports across codebase
- [ ] Commit: "refactor: complete OpenAPI type migration"

### Week 4: Composables & Documentation
- [ ] Review composables for duplication
- [ ] Add JSDoc documentation
- [ ] Update README with style/type conventions
- [ ] Create CONTRIBUTING.md with guidelines
- [ ] Commit: "docs: improve DX documentation"

---

## 🎯 Success Metrics

### Consistency
- ✅ All terminal-green colors use same hex value
- ✅ All spacing uses consistent scale (0.5rem increments)
- ✅ All animations use same timing functions
- ✅ All terminal effects use shared utilities

### Performance
- ✅ Bundle size reduced by ~50KB
- ✅ Fewer scoped style compilations
- ✅ Shared styles cached by browser

### DX/UX
- ✅ 100% type safety with backend
- ✅ Zero type drift
- ✅ Faster onboarding (clear conventions)
- ✅ Better IDE autocomplete

---

## 🔧 Technical Details

### Most Duplicated Styles to Extract:

```css
/* Terminal Theme Base */
.main-content { /* 45 occurrences */ }
.terminal-input { /* 14 occurrences */ }
.terminal-button { /* 14 occurrences */ }
.empty-state { /* 14 occurrences */ }
.modal-body { /* 10 occurrences */ }
.stat-value { /* 14 occurrences */ }
.section-title { /* 8 occurrences */ }
.error-message { /* 9 occurrences */ }
```

### Files Importing Manual Types (36 files):
- Components: 27 files
- Stores: 11 files
- Services: 2 files
- Composables: 1 file
- **Action**: Update to use `api.generated.ts` directly

---

## 📝 Notes

- Mantra: **"Lesser is better, consistency matters"**
- Focus on reducing duplication, not adding features
- Prioritize consistency over cleverness
- Keep changes incremental and testable
- Document decisions in commit messages

---

Last updated: January 6, 2026
