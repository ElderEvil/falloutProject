# Lighthouse Performance & Accessibility Fixes Plan

## Current Scores
- **Performance**: 54/100 ❌ (Target: 90+)
- **Accessibility**: 87/100 ⚠️ (Target: 95+)
- **Best Practices**: 100/100 ✅
- **SEO**: 83/100 ⚠️ (Target: 90+)

## Key Metrics to Improve
- **First Contentful Paint (FCP)**: 15.3s → Target: <1.8s
- **Largest Contentful Paint (LCP)**: 28.9s → Target: <2.5s
- **Time to Interactive (TTI)**: 28.9s → Target: <3.8s
- **Speed Index**: 15.3s → Target: <3.4s

---

## Phase 1: Critical Performance Issues (High Impact) 🔴

### 1.1 First Contentful Paint (FCP: 15.3s → Target: <1.8s)
**Root cause**: Slow initial page render, blocking resources

**Tasks**:
- [ ] Add loading skeleton screens for vault view
- [ ] Implement route-based code splitting with lazy loading
- [ ] Add resource hints (`<link rel="preload">` for critical assets)
- [ ] Optimize font loading with `font-display: swap`
- [ ] Move non-critical CSS to separate chunks

**Files to modify**:
- `frontend/index.html` - Add preload links
- `frontend/src/views/VaultView.vue` - Add skeleton screen
- `frontend/src/router/index.ts` - Lazy load routes
- `frontend/vite.config.ts` - Configure chunking

**Estimated time**: 3-4 hours
**Expected impact**: FCP 15.3s → 3-5s

---

### 1.2 Largest Contentful Paint (LCP: 28.9s → Target: <2.5s)
**Root cause**: Large/slow-loading content blocks rendering, heavy room grid

**Tasks**:
- [ ] Optimize room grid rendering with virtualization for >30 rooms
- [ ] Add image lazy loading for dweller avatars
- [ ] Implement progressive/incremental loading for vault data
- [ ] Add `fetchpriority="high"` for critical above-the-fold content
- [ ] Defer loading of below-the-fold components

**Files to modify**:
- `frontend/src/components/rooms/RoomGrid.vue` - Add virtual scrolling
- `frontend/src/stores/room.ts` - Implement progressive data loading
- `frontend/src/stores/dweller.ts` - Lazy load dweller details
- Create `frontend/src/components/common/VirtualScroller.vue`

**Estimated time**: 4-5 hours
**Expected impact**: LCP 28.9s → 4-6s

---

### 1.3 Time to Interactive (TTI: 28.9s → Target: <3.8s)
**Root cause**: Heavy JavaScript execution blocking interactivity

**Tasks**:
- [ ] Defer non-critical JavaScript loading
- [ ] Split vendor bundles (Vue, Pinia, Router, Axios, Iconify)
- [ ] Remove unused JavaScript (7 files identified in audit)
- [ ] Move polling logic to Web Worker
- [ ] Reduce main thread work from 2.2s to <600ms

**Files to modify**:
- `frontend/vite.config.ts` - Configure manual chunks
- `frontend/src/workers/polling.worker.ts` - Create new worker
- `frontend/src/stores/incident.ts` - Move polling to worker
- `frontend/package.json` - Audit dependencies

**Estimated time**: 4-5 hours
**Expected impact**: TTI 28.9s → 5-7s

---

## Phase 2: Accessibility Fixes (Medium Impact) 🟡

### 2.1 Color Contrast Issues (5 instances) - WCAG AA Violation
**Current failures**:
1. Terminal glow buttons: green #00ff00 on green #008900 (ratio 3.34, needs 4.5)
2. White text on progress bars: white #ffffff on green #00f200 (ratio 1.53, needs 4.5) - 3 instances
3. Pause button: white on orange #c58000 (ratio 3.24, needs 4.5)

**Tasks**:
- [ ] Fix terminal glow button contrast
  - Option A: Darken background from #008900 to #005500
  - Option B: Add 2px border and transparent background
- [ ] Fix progress bar text contrast
  - Add dark text shadow or background overlay
  - Or use theme-primary text color instead of white
- [ ] Fix pause/warning button contrast
  - Darken background from #c58000 to #9a6000

**Files to modify**:
- `frontend/src/components/common/ResourceBar.vue` - Progress bar text
- `frontend/src/components/time/TimeControls.vue` - Pause button
- `frontend/src/styles/main.css` - Terminal glow button styles
- `frontend/src/composables/useTheme.ts` - Verify theme contrast ratios

**Estimated time**: 1-2 hours
**Expected impact**: Accessibility 87 → 93+

---

### 2.2 Label Mismatches (6 navigation buttons) - WCAG Violation
**Issue**: aria-label includes extra info but visible text doesn't match

**Current**:
- Visible: "Overview" | aria-label: "Navigate to Overview (Press 1)"
- Visible: "Dwellers" | aria-label: "Navigate to Dwellers (Press 2)"
- (4 more similar issues)

**Fix**:
- Make aria-label match visible text exactly: `aria-label="Overview"`
- Move keyboard shortcuts to `aria-describedby` or `title` attribute
- Or add sr-only text with full description

**Tasks**:
- [ ] Update navigation component aria-labels to match visible text
- [ ] Add keyboard shortcut hints as separate `aria-describedby` elements
- [ ] Test with screen reader (NVDA/JAWS)

**Files to modify**:
- `frontend/src/components/layout/NavigationBar.vue` or similar navigation component

**Estimated time**: 30 min - 1 hour
**Expected impact**: Accessibility 87 → 95+

---

## Phase 3: Bundle Optimization (Medium Impact) 🟡

### 3.1 Code Splitting & Lazy Loading
**Current issue**: Large initial bundle, 7 unused JS files

**Tasks**:
- [ ] Implement route-level code splitting
  ```ts
  const VaultView = () => import('./views/VaultView.vue')
  const DwellersView = () => import('./views/DwellersView.vue')
  // etc.
  ```
- [ ] Lazy load heavy components:
  - RoomDetailModal
  - IncidentManager
  - TrainingRoomModal
  - DwellerDetailModal
- [ ] Extract vendor bundles using manual chunks:
  - `vue` (core framework)
  - `vue-router` + `pinia` (state/routing)
  - `axios` (API client)
  - `iconify` (icons)
  - `ui-components` (all /components/ui/*)

**Files to modify**:
- `frontend/src/router/index.ts` - Lazy load all routes
- `frontend/vite.config.ts` - Configure `manualChunks`
- Components: Use `defineAsyncComponent` for modals

**Estimated time**: 2-3 hours
**Expected impact**: Initial bundle size 4.4 MB → 1.5-2 MB

---

### 3.2 Tree Shaking & Dead Code Elimination

**Tasks**:
- [ ] Audit package.json for unused dependencies
- [ ] Remove unused imports across codebase
- [ ] Configure Vite for aggressive tree-shaking
- [ ] Enable `drop_console` in production builds
- [ ] Remove unused CSS classes (if using PurgeCSS)

**Files to modify**:
- `frontend/package.json` - Remove unused deps
- `frontend/vite.config.ts` - Add terser options
- `frontend/tailwind.config.js` - Configure content purging

**Estimated time**: 2-3 hours
**Expected impact**: Bundle size reduction 15-20%

---

## Phase 4: Rendering Optimization (Medium Impact) 🟡

### 4.1 Virtual Scrolling Implementation

**Tasks**:
- [ ] Create reusable `VirtualScroller.vue` component
- [ ] Implement virtual scrolling for room grid (threshold: >30 rooms)
- [ ] Implement virtual scrolling for dweller list (threshold: >50 dwellers)
- [ ] Add virtual scrolling to long modals (training logs, etc.)
- [ ] Handle dynamic item heights

**Files to create**:
- `frontend/src/components/common/VirtualScroller.vue`

**Files to modify**:
- `frontend/src/components/rooms/RoomGrid.vue`
- `frontend/src/components/dwellers/DwellerGridView.vue`
- `frontend/src/components/dwellers/DwellerListView.vue`

**Estimated time**: 3-4 hours
**Expected impact**: Rendering time for large lists 500ms → 50ms

---

### 4.2 Reduce Re-renders & Optimize Reactivity

**Tasks**:
- [ ] Add `v-memo` to expensive list items (rooms, dwellers)
- [ ] Use `shallowRef` for large data structures (room arrays, dweller arrays)
- [ ] Memoize expensive computed properties
- [ ] Add stable `key` attributes to prevent unnecessary re-renders
- [ ] Use `v-once` for static content

**Files to modify**:
- `frontend/src/components/rooms/RoomGrid.vue`
- `frontend/src/components/rooms/RoomItem.vue`
- `frontend/src/components/dwellers/DwellerGridItem.vue`
- `frontend/src/stores/room.ts`
- `frontend/src/stores/dweller.ts`

**Estimated time**: 2-3 hours
**Expected impact**: Re-render time reduction 30-40%

---

### 4.3 Polling & Background Tasks Optimization

**Tasks**:
- [ ] Increase polling intervals from 10s to 30s (or use WebSocket)
- [ ] Debounce search/filter inputs (300ms)
- [ ] Throttle scroll handlers (100ms)
- [ ] Use `requestIdleCallback` for non-critical updates
- [ ] Pause polling when tab is not visible (Page Visibility API)
- [ ] Consider moving to Server-Sent Events (SSE) for real-time updates

**Files to modify**:
- `frontend/src/stores/incident.ts`
- `frontend/src/stores/training.ts`
- `frontend/src/composables/usePolling.ts` (create new composable)
- `frontend/src/components/search/SearchBar.vue`

**Estimated time**: 2-3 hours
**Expected impact**: CPU usage reduction 40-50%

---

## Phase 5: Progressive Loading & UX (Low Impact) 🟢

### 5.1 Loading States & Skeleton Screens

**Tasks**:
- [ ] Create skeleton components:
  - VaultOverviewSkeleton
  - RoomGridSkeleton
  - DwellerListSkeleton
- [ ] Add loading spinners to all async operations
- [ ] Implement progress indicators for long operations
- [ ] Add optimistic UI updates (show change immediately, revert on error)

**Files to create**:
- `frontend/src/components/common/skeletons/VaultOverviewSkeleton.vue`
- `frontend/src/components/common/skeletons/RoomGridSkeleton.vue`
- `frontend/src/components/common/skeletons/DwellerListSkeleton.vue`

**Files to modify**:
- `frontend/src/views/VaultView.vue`
- `frontend/src/views/DwellersView.vue`

**Estimated time**: 2-3 hours
**Expected impact**: Perceived performance improvement, better UX

---

### 5.2 Stale-While-Revalidate Strategy

**Tasks**:
- [ ] Implement SWR caching for API responses
- [ ] Cache vault data, rooms, dwellers in IndexedDB
- [ ] Show cached data immediately on load
- [ ] Fetch fresh data in background
- [ ] Add cache invalidation logic
- [ ] Add "Last updated" timestamp display

**Files to create**:
- `frontend/src/utils/cache.ts`
- `frontend/src/composables/useSWR.ts`

**Files to modify**:
- `frontend/src/stores/vault.ts`
- `frontend/src/stores/room.ts`
- `frontend/src/stores/dweller.ts`

**Estimated time**: 3-4 hours
**Expected impact**: Instant subsequent loads

---

## Phase 6: SEO Improvements (Low Impact) 🟢

### 6.1 Meta Tags & Social Sharing

**Tasks**:
- [ ] Add proper `<meta name="description">`
- [ ] Add Open Graph tags (og:title, og:description, og:image)
- [ ] Add Twitter Card tags
- [ ] Ensure viewport meta tag is correct
- [ ] Add canonical URLs
- [ ] Add favicon and app icons

**Files to modify**:
- `frontend/index.html`
- Create `frontend/public/og-image.png`

**Estimated time**: 1 hour
**Expected impact**: SEO 83 → 90+

---

### 6.2 Semantic HTML & Structure

**Tasks**:
- [ ] Audit heading hierarchy (ensure proper h1 → h2 → h3 order)
- [ ] Add `<main>`, `<nav>`, `<article>`, `<section>` where appropriate
- [ ] Ensure all images have meaningful `alt` attributes
- [ ] Add schema.org structured data (if applicable)
- [ ] Add `lang` attribute to html tag

**Files to modify**:
- `frontend/index.html`
- Various Vue components with semantic issues

**Estimated time**: 1-2 hours
**Expected impact**: SEO 83 → 95+

---

## Implementation Priority (by ROI)

### Quick Wins (Day 1-2) - 6-8 hours
1. ✅ **Color contrast fixes** (1-2 hrs) - Accessibility +6 points
2. ✅ **Label mismatch fixes** (0.5-1 hrs) - Accessibility +2 points
3. ✅ **SEO meta tags** (1 hr) - SEO +7 points
4. ✅ **Loading skeletons** (2-3 hrs) - Perceived performance boost

### High Impact (Day 3-5) - 12-15 hours
5. 🔥 **Code splitting & lazy loading** (2-3 hrs) - Performance +15 points
6. 🔥 **Bundle optimization** (2-3 hrs) - Performance +8 points
7. 🔥 **Virtual scrolling** (3-4 hrs) - Performance +5 points
8. 🔥 **Reduce re-renders** (2-3 hrs) - Performance +5 points

### Fine Tuning (Day 6-7) - 8-10 hours
9. ⚡ **Resource hints & preloading** (1-2 hrs) - Performance +3 points
10. ⚡ **Polling optimization** (2-3 hrs) - Performance +2 points
11. ⚡ **SWR caching** (3-4 hrs) - UX improvement
12. ⚡ **Semantic HTML audit** (1-2 hrs) - SEO +5 points

---

## Expected Final Scores

### Before
- Performance: 54/100
- Accessibility: 87/100
- Best Practices: 100/100
- SEO: 83/100

### After (Conservative Estimate)
- **Performance**: 85-90/100 (+31-36 points)
- **Accessibility**: 95-100/100 (+8-13 points)
- **Best Practices**: 100/100 (maintained)
- **SEO**: 90-95/100 (+7-12 points)

### After (Optimistic Estimate)
- **Performance**: 92-95/100 (+38-41 points)
- **Accessibility**: 100/100 (+13 points)
- **Best Practices**: 100/100 (maintained)
- **SEO**: 95-98/100 (+12-15 points)

---

## Total Estimated Time
- **Quick wins**: 6-8 hours
- **High impact**: 12-15 hours
- **Fine tuning**: 8-10 hours

**Total**: 26-33 hours (3-4 full work days)

---

## Success Metrics
- [ ] FCP < 1.8s
- [ ] LCP < 2.5s
- [ ] TTI < 3.8s
- [ ] All color contrast ratios ≥ 4.5:1
- [ ] All form labels properly associated
- [ ] Initial bundle < 2 MB
- [ ] Performance score ≥ 85
- [ ] Accessibility score ≥ 95
- [ ] SEO score ≥ 90

---

## Testing Checklist
- [ ] Run Lighthouse audit on localhost
- [ ] Run Lighthouse audit on production build
- [ ] Test with slow 3G throttling
- [ ] Test with screen reader (NVDA/JAWS)
- [ ] Test keyboard navigation
- [ ] Verify lazy loading works correctly
- [ ] Verify virtual scrolling with large datasets
- [ ] Check bundle sizes with `vite build --mode analyze`
- [ ] Validate meta tags with social media preview tools
