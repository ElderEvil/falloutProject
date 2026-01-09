# Style Migration Guide

## Overview

We've created shared component styles in `frontend/src/assets/components.css` to reduce duplication and improve consistency. This guide shows how to migrate components from scoped styles to shared utilities.

---

## ✅ Available Shared Classes

### Layout
- `.main-content` - Main content area with side panel margins (45+ uses)
- `.vault-layout` - Flex layout for vault views (8+ uses)
- `.section-title` - Uppercase section headers (8+ uses)

### States
- `.empty-state` - Empty/no-data placeholders (14+ uses)
  - `.empty-state-icon` - Large icon
  - `.empty-state-title` - Title text
  - `.empty-state-message` - Description
- `.loading-state` - Loading indicators
  - `.loading-icon` - Spinning icon
- `.error-state` - Error displays (9+ uses)
  - `.error-icon` - Error icon
  - `.error-title` - Error title
  - `.error-message` - Error description

### Modals
- `.modal-overlay` - Full-screen modal backdrop
- `.modal-content` - Modal container
- `.modal-header` - Modal header with title
- `.modal-title` - Modal title text
- `.modal-body` - Modal content area (10+ uses)
- `.modal-footer` - Modal actions footer
- `.close-btn` - Close button (8+ uses)

### Cards
- `.dweller-card` - Dweller card container (9+ uses)
  - Includes hover effects, glow, gradient overlay
- `.dweller-name` - Dweller name text (8+ uses)

### Grids
- `.dweller-grid` - Responsive dweller grid (10+ uses)
- `.room-menu` - Room selection grid (9+ uses)

### Stats
- `.stat-value` - Large stat numbers (14+ uses)
- `.stat-label` - Stat labels (10+ uses)

### Buttons
- `.vault-button` - Primary vault action buttons (11+ uses)
- `.ai-generate` - AI generation buttons (10+ uses)

### Misc
- `.modifier-item` - Happiness/stat modifiers (11+ uses)
  - `.modifier-item.positive` - Positive modifier
  - `.modifier-item.negative` - Negative modifier
- `.link-text` - Styled links (8+ uses)
- `.reward-icon` - Animated reward icons (12+ uses)

### Animations
- `@keyframes spin` - Spinning animation
- `@keyframes pulse` - Pulse animation
- `@keyframes fadeIn` - Fade in animation
- `@keyframes slideUp` - Slide up animation

---

## 🔄 Migration Process

### Step 1: Identify Candidate Classes

Look for these patterns in `<style scoped>`:

```css
/* BEFORE - Duplicated styles */
.my-card {
  background: rgba(20, 20, 20, 0.95);
  border: 2px solid var(--color-theme-primary);
  border-radius: 4px;
  padding: 1rem;
  cursor: pointer;
  transition: all 0.25s ease;
}

.my-stat-value {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
}
```

### Step 2: Replace with Shared Classes

```vue
<template>
  <!-- AFTER - Using shared classes -->
  <div class="dweller-card">
    <span class="stat-value">{{ value }}</span>
  </div>
</template>

<style scoped>
/* Only component-specific overrides remain */
.dweller-card {
  /* Custom gap if needed */
  gap: 2rem;
}
</style>
```

### Step 3: Remove Redundant Styles

Delete the duplicated style blocks. Keep only:
- Component-specific layouts
- Unique positioning/sizing
- Special behavior overrides

---

## 📝 Example Migration

### Before (DwellerCard.vue)

```vue
<style scoped>
.dweller-card {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  padding: 1.5rem;
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid var(--color-theme-glow);
  border-radius: 8px;
  box-shadow: 0 0 15px var(--color-theme-glow);
}

.stat-label {
  font-weight: 600;
  color: var(--color-theme-primary);
  text-shadow: 0 0 3px var(--color-theme-glow);
  opacity: 0.8;
}

.stat-value {
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.close-btn {
  background: none;
  border: none;
  color: var(--color-theme-primary);
  font-size: 2rem;
  cursor: pointer;
  /* ... */
}
</style>
```

**Lines of scoped styles**: 50+

### After

```vue
<style scoped>
/* Using shared .dweller-card, .stat-label, .stat-value, .close-btn */
.dweller-card {
  gap: 1.5rem; /* Override default gap */
}
</style>
```

**Lines of scoped styles**: 3
**Savings**: 47 lines (~94% reduction)

---

## 🎯 High-ROI Migration Targets

Based on our audit, these components have the highest duplication:

### Priority 1 (High Impact)
1. **DwellerCard.vue** - 423 lines of styles (!)
   - Uses: `.dweller-card`, `.stat-value`, `.stat-label`
   - **Potential savings**: ~150 lines

2. **RoomDetailModal.vue** - Est. 200+ lines
   - Uses: `.modal-overlay`, `.modal-content`, `.modal-body`, `.close-btn`
   - **Potential savings**: ~80 lines

3. **HappinessDashboard.vue** - 190+ lines
   - Uses: `.section-title`, `.stat-value`, `.modifier-item`
   - **Potential savings**: ~60 lines

### Priority 2 (Medium Impact)
4. **RoomMenu.vue** - 75 lines
   - Uses: `.modal-overlay`, `.modal-content`, `.room-menu`
   - **Potential savings**: ~40 lines

5. **RoomMenuItem.vue** - 100+ lines
   - Uses: `.dweller-card` pattern, `.stat-label`
   - **Potential savings**: ~50 lines

6. **VaultView.vue** - 100+ lines
   - Uses: `.main-content`, `.vault-layout`
   - **Potential savings**: ~30 lines

7. **DwellersView.vue** - Est. 150+ lines
   - Uses: `.main-content`, `.dweller-grid`, `.empty-state`
   - **Potential savings**: ~50 lines

### Priority 3 (Quick Wins)
8. **CombatModal.vue**
   - Uses: `.modal-*` classes
   - **Potential savings**: ~40 lines

9. **IncidentAlert.vue**
   - Uses: `.error-state`, `.modifier-item`
   - **Potential savings**: ~30 lines

10. **UnassignedDwellers.vue**
    - Uses: `.empty-state`, `.dweller-grid`
    - **Potential savings**: ~25 lines

---

## 📊 Expected Results

### Phase 1 (Top 3 components)
- **Lines removed**: ~290
- **Bundle size reduction**: ~15KB
- **Time**: 2-3 hours

### Phase 2 (All 10 components)
- **Lines removed**: ~555+
- **Bundle size reduction**: ~30KB
- **Time**: 1 week

### Full Migration (70 components)
- **Lines removed**: ~2,000+
- **Bundle size reduction**: ~50KB
- **Time**: 2-3 weeks

---

## ⚠️ Important Notes

### DO
- ✅ Use shared classes for common patterns
- ✅ Keep component-specific styles scoped
- ✅ Test visual consistency after migration
- ✅ Remove entire style blocks if empty

### DON'T
- ❌ Remove unique component styles
- ❌ Change component behavior
- ❌ Mix Tailwind with shared classes (use one or the other per element)
- ❌ Migrate without testing

---

## 🧪 Testing Checklist

After migrating a component:

1. [ ] Visual appearance unchanged
2. [ ] Hover/active states work
3. [ ] Responsive behavior intact
4. [ ] Animations still work
5. [ ] No console errors
6. [ ] File size reduced

---

## 📈 Tracking Progress

Run this command to check progress:

```bash
# Count remaining scoped styles
find frontend/src -name "*.vue" -exec grep -l "<style scoped>" {} \; | wc -l

# Calculate total scoped style size
find frontend/src -name "*.vue" -exec sh -c 'grep -Pzo "(?s)<style scoped>.*?</style>" "$1" | wc -c' _ {} \; | awk '{sum+=$1} END {print sum " bytes"}'
```

**Baseline**: 70 files, ~134KB
**Target**: 35 files, ~70KB

---

## 🤝 Contributing

When migrating components:

1. Create a branch: `refactor/migrate-<component-name>-styles`
2. Migrate one component at a time
3. Test thoroughly
4. Commit with message: `refactor: migrate <Component> to shared styles`
5. Include before/after line counts in PR description

---

Last updated: January 6, 2026
