# Theme System Unification Plan

## Problem Analysis
- **481 color references** across 56 files use various CSS variable names
- **40+ hardcoded color values** (e.g., `#00ff00`, `rgba(0, 255, 0, ...)`)
- **Missing RGB variants** - `--color-theme-primary-rgb` wasn't defined until now
- **Three different naming conventions**:
  - `--theme-primary` (from useTheme.ts)
  - `--color-theme-primary` (from tailwind.css)
  - `--color-primary` (legacy)

## Root Cause
- `useTheme.ts` only set `--theme-primary` variables
- Components used `--color-theme-primary` (expecting it from elsewhere)
- No RGB variants for `rgba()` usage
- Tailwind.css provided fallbacks but they only work if base vars are set

## Solution: Three-Phase Approach

### Phase 1: Fix Theme System Foundation ✅ (DONE)
- [x] Update `useTheme.ts` to set all variable variants
- [x] Add `hexToRgb()` helper for RGB conversion
- [x] Set `--color-theme-*` and `--color-theme-*-rgb` variables
- [x] Fix ExplorationRewardsModal.vue to use theme variables
- [x] Fix DwellerChat.vue audio replay button theme

### Phase 2: Create Theme Utility & Documentation (TODO)
**Files to create:**

1. **`frontend/src/styles/theme-guide.md`** - Developer documentation
   - Standard variable names to use
   - Examples for common patterns
   - Migration guide for old code

2. **`frontend/src/composables/useThemeColors.ts`** - Utility composable
   ```ts
   // Provides type-safe theme color access
   export function useThemeColors() {
     return {
       primary: 'var(--color-theme-primary)',
       primaryRgb: 'var(--color-theme-primary-rgb, 0, 255, 0)',
       glow: 'var(--color-theme-glow)',
       secondary: 'var(--color-theme-secondary)',
       accent: 'var(--color-theme-accent)',
       // Helper for rgba usage
       rgba: (color: 'primary' | 'secondary' | 'accent', alpha: number) => {
         const rgbVar = `--color-theme-${color}-rgb`;
         return `rgba(var(${rgbVar}, 0, 255, 0), ${alpha})`;
       }
     }
   }
   ```

3. **VS Code snippets** - `frontend/.vscode/theme.code-snippets`
   ```json
   {
     "Theme Primary Color": {
       "prefix": "theme-primary",
       "body": "var(--color-theme-primary)",
       "description": "Primary theme color"
     },
     "Theme Primary RGBA": {
       "prefix": "theme-primary-rgba",
       "body": "rgba(var(--color-theme-primary-rgb, 0, 255, 0), $1)",
       "description": "Primary theme color with alpha"
     }
   }
   ```

### Phase 3: Bulk Cleanup (OPTIONAL - Can be done incrementally)

**Replace hardcoded colors in ~40 remaining files:**
- Auth forms (LoginFormTerminal.vue, RegisterForm.vue)
- Legacy components still using hardcoded values
- Components using `rgba(0, 255, 0, X)` without fallbacks

**Files with most hardcoded colors:**
```bash
# Find all hardcoded green colors
grep -r "rgba(0, 255, 0" frontend/src/components --include="*.vue"
grep -r "#00ff00" frontend/src/components --include="*.vue"
grep -r "#00ff9f" frontend/src/components --include="*.vue"
```

**Approach:**
- Use find/replace with regex
- Test each component category (auth, dwellers, rooms, etc.)
- Or leave for incremental cleanup when touching files

## Standard Variable Names (USE THESE)

### Primary Usage
```css
/* Solid colors */
color: var(--color-theme-primary);
border-color: var(--color-theme-primary);

/* RGBA with fallback */
background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.1);

/* Glow effects */
text-shadow: 0 0 10px var(--color-theme-glow);
box-shadow: 0 0 20px var(--color-theme-glow);
```

### Complete Variable Set
- `--color-theme-primary` - Main theme color
- `--color-theme-primary-rgb` - RGB values for rgba()
- `--color-theme-secondary` - Secondary/background color
- `--color-theme-secondary-rgb` - RGB values
- `--color-theme-accent` - Accent/hover color
- `--color-theme-accent-rgb` - RGB values
- `--color-theme-glow` - Pre-defined glow rgba

## Benefits
✅ Single source of truth for theme variables
✅ Type-safe color access
✅ Auto-complete prevents mistakes
✅ Clear migration path
✅ Self-documenting system
✅ Prevents future "green on amber theme" bugs

## Recommendation
**Do Phase 2 next** (15-20 min):
- Creates clear standards going forward
- Prevents future issues
- Provides self-documenting code

**Phase 3 can wait**:
- Current system now works
- Can fix hardcoded colors incrementally
- Only affects components when themes other than FO4 are used

## Current Status (January 2026)
- ✅ Phase 1 complete
- ⏳ Phase 2 pending
- ⏳ Phase 3 pending (low priority)
