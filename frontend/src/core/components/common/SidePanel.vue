<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { useRoute, useRouter } from 'vue-router'
import { useSidePanel } from '@/core/composables/useSidePanel'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/core/components/ui/tooltip'

const route = useRoute()
const router = useRouter()
const { isCollapsed, toggle } = useSidePanel()

const props = defineProps<{ vaultId?: string | null }>()

const vaultId = computed(() => (route.params.id as string | undefined) ?? props.vaultId)

interface NavItem {
  id: string
  label: string
  icon: string
  path: string
  hotkey?: string
  wip?: boolean
}

interface ComingSoonItem {
  id: string
  label: string
  icon: string
}

const navItems = computed((): NavItem[] => {
  if (!vaultId.value) return []

  const navItems: NavItem[] = [
    {
      id: 'overview',
      label: 'Overview',
      icon: 'mdi:view-dashboard',
      path: `/vault/${vaultId.value}`,
      hotkey: '1',
    },
    {
      id: 'dwellers',
      label: 'Dwellers',
      icon: 'mdi:account-group',
      path: `/vault/${vaultId.value}/dwellers`,
      hotkey: '2',
    },
    {
      id: 'exploration',
      label: 'Exploration',
      icon: 'mdi:compass',
      path: `/vault/${vaultId.value}/exploration`,
      hotkey: '3',
    },
    {
      id: 'objectives',
      label: 'Objectives',
      icon: 'mdi:target',
      path: `/vault/${vaultId.value}/objectives`,
      hotkey: '4',
    },
    {
      id: 'quests',
      label: 'Quests',
      icon: 'mdi:book-open-page-variant',
      path: `/vault/${vaultId.value}/quests`,
      hotkey: '5',
    },
    {
      id: 'relationships',
      label: 'Relationships',
      icon: 'mdi:heart-multiple',
      path: `/vault/${vaultId.value}/relationships`,
      hotkey: '6',
    },
    {
      id: 'training',
      label: 'Training',
      icon: 'mdi:dumbbell',
      path: `/vault/${vaultId.value}/training`,
      hotkey: '7',
    },
    {
      id: 'map',
      label: 'Map',
      icon: 'mdi:map',
      path: `/vault/${vaultId.value}/map`,
      hotkey: '8',
    },
    {
      id: 'storage',
      label: 'Storage',
      icon: 'mdi:package-variant',
      path: `/vault/${vaultId.value}/storage`,
      hotkey: '9',
    },
    {
      id: 'trading',
      label: 'Trading Post',
      icon: 'mdi:store',
      path: `/vault/${vaultId.value}/trading`,
      wip: true,
    },
  ]
  return navItems
})

const comingSoonItems = computed((): ComingSoonItem[] => [
  {
    id: 'achievements',
    label: 'Achievements',
    icon: 'mdi:trophy',
  },
])

const activePath = computed(
  () =>
    navItems.value
      .map((item) => item.path)
      .filter((path) => route.path === path || route.path.startsWith(`${path}/`))
      .sort((first, second) => second.length - first.length)[0]
)

const isActive = (path: string) => path === activePath.value

const navigate = (path: string) => {
  router.push(path)
}

// --- Mobile drawer ---------------------------------------------------------
// Drawer visibility is kept separate from the persisted desktop `isCollapsed`
// flag: collapsing the desktop panel must not hide the mobile drawer (and the
// reverse). The breakpoint mirrors the Tailwind `md` token (768px).
const MOBILE_QUERY = '(max-width: 767.98px)'
const isMobileViewport = () => window.matchMedia(MOBILE_QUERY).matches

const isMobileOpen = ref(false)
const toggleButtonRef = ref<HTMLButtonElement | null>(null)
const panelSurfaceRef = ref<HTMLElement | null>(null)

const openMobile = () => {
  isMobileOpen.value = true
  // Move focus into the drawer so keyboard users land on the nav, not the page.
  nextTick(() => panelSurfaceRef.value?.focus())
}

const closeMobile = () => {
  if (!isMobileOpen.value) return
  isMobileOpen.value = false
  // Return focus to the invoking toggle.
  nextTick(() => toggleButtonRef.value?.focus())
}

const handleToggleClick = () => {
  if (!isMobileViewport()) {
    toggle()
    return
  }
  if (isMobileOpen.value) {
    closeMobile()
  } else {
    openMobile()
  }
}

const toggleLabel = computed(() => {
  if (isMobileViewport()) {
    return isMobileOpen.value ? 'Close navigation panel' : 'Open navigation panel'
  }
  return isCollapsed.value ? 'Expand navigation panel' : 'Collapse navigation panel'
})

const toggleIcon = computed(() => {
  if (isMobileViewport()) {
    return isMobileOpen.value ? 'mdi:close' : 'mdi:menu'
  }
  return isCollapsed.value ? 'mdi:chevron-right' : 'mdi:chevron-left'
})

// Shared editable-surface guard: number hotkeys and Ctrl/Cmd+B must not hijack
// typing in inputs, textareas, or contenteditable surfaces.
const isEditableTarget = (target: EventTarget | null): boolean =>
  target instanceof HTMLElement &&
  (target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target.isContentEditable)

// Keyboard shortcuts
const handleKeyPress = (e: KeyboardEvent) => {
  // Escape closes the mobile drawer (focus returns to the toggle).
  if (e.key === 'Escape' && isMobileOpen.value) {
    closeMobile()
    return
  }

  // Toggle panel with Ctrl/Cmd + B (layout-independent via code)
  if ((e.ctrlKey || e.metaKey) && e.code === 'KeyB') {
    if (isEditableTarget(e.target)) {
      return
    }

    e.preventDefault()
    toggle()
    return
  }

  // Number hotkeys must not fire while a modifier is held (Ctrl/Cmd/Alt+1..9
  // belong to the browser/OS) or while an editable surface has focus.
  if (e.ctrlKey || e.metaKey || e.altKey) {
    return
  }
  if (isEditableTarget(e.target)) {
    return
  }

  const item = navItems.value.find((item) => item.hotkey === e.key)
  if (item) {
    e.preventDefault()
    navigate(item.path)
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyPress)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyPress)
})

// Navigating away from a drawer-opened item closes the drawer.
watch(
  () => route.fullPath,
  () => closeMobile()
)
</script>

<template>
  <nav
    class="side-panel"
    :class="{ collapsed: isCollapsed, 'mobile-open': isMobileOpen }"
    aria-label="Game navigation panel"
  >
    <div id="side-panel-nav" ref="panelSurfaceRef" class="panel-surface" tabindex="-1">
      <!-- Navigation Items -->
      <div class="nav-items">
        <TooltipProvider :delay-duration="200">
          <Tooltip v-for="item in navItems" :key="item.id">
            <TooltipTrigger as-child>
              <RouterLink
                :to="item.path"
                class="nav-item"
                :class="{ active: isActive(item.path) }"
                :aria-label="`${item.label}${!isCollapsed && item.hotkey ? ' ' + item.hotkey : ''}`"
                :aria-current="isActive(item.path) ? 'page' : undefined"
                :aria-keyshortcuts="item.hotkey"
              >
                <Icon :icon="item.icon" class="nav-icon" />
                <span v-if="!isCollapsed" class="nav-label">{{ item.label }}</span>
                <TooltipProvider v-if="!isCollapsed && item.wip" :delay-duration="200">
                  <Tooltip>
                    <TooltipTrigger as-child>
                      <span class="wip-badge">WIP</span>
                    </TooltipTrigger>
                    <TooltipContent>Work in progress</TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                <span
                  v-else-if="!isCollapsed && item.hotkey"
                  class="hotkey-badge"
                  aria-hidden="true"
                  >{{ item.hotkey }}</span
                >
              </RouterLink>
            </TooltipTrigger>
            <TooltipContent>{{
              `${item.label}${item.hotkey ? ' (Shortcut: ' + item.hotkey + ')' : ''}`
            }}</TooltipContent>
          </Tooltip>
        </TooltipProvider>

        <!-- Coming Soon Divider -->
        <div v-if="!isCollapsed" class="nav-divider">
          <span class="divider-text">Upcoming Features</span>
        </div>

        <!-- Coming Soon Items -->
        <TooltipProvider :delay-duration="200">
          <Tooltip v-for="item in comingSoonItems" :key="item.id">
            <TooltipTrigger as-child>
              <div class="nav-item locked">
                <Icon :icon="item.icon" class="nav-icon" />
                <span v-if="!isCollapsed" class="nav-label locked-label">{{ item.label }}</span>
                <span v-if="!isCollapsed" class="lock-icon-wrap">
                  <Icon icon="mdi:lock" class="lock-icon" />
                </span>
              </div>
            </TooltipTrigger>
            <TooltipContent>{{ `${item.label} - Coming soon` }}</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    </div>

    <!-- Toggle Button -->
    <TooltipProvider :delay-duration="200">
      <Tooltip>
        <TooltipTrigger as-child>
          <button
            ref="toggleButtonRef"
            type="button"
            class="toggle-btn"
            :aria-label="toggleLabel"
            :aria-expanded="isMobileViewport() ? isMobileOpen : !isCollapsed"
            aria-controls="side-panel-nav"
            @click="handleToggleClick"
          >
            <Icon :icon="toggleIcon" class="h-6 w-6" />
          </button>
        </TooltipTrigger>
        <TooltipContent>{{ `${isCollapsed ? 'Expand' : 'Collapse'} (Ctrl+B)` }}</TooltipContent>
      </Tooltip>
    </TooltipProvider>

    <!-- Mobile drawer backdrop -->
    <div v-if="isMobileOpen" class="panel-backdrop" aria-hidden="true" @click="closeMobile" />
  </nav>
</template>

<style scoped>
.side-panel {
  position: fixed;
  left: 0;
  top: var(--chrome-height); /* Below the fixed navbar, including its vault status row */
  bottom: 0;
  width: 240px;
  background: rgba(0, 0, 0, 0.95);
  border-right: 2px solid var(--color-theme-primary);
  box-shadow: var(--glow-1);
  transition:
    width 0.3s ease,
    transform 0.3s ease;
  z-index: 40;
  display: flex;
  flex-direction: column;
  font-family: 'Courier New', monospace;
}

.side-panel.collapsed {
  width: 64px;
}

.toggle-btn {
  position: absolute;
  right: -12px;
  top: 16px;
  width: 24px;
  height: 24px;
  background: var(--color-terminal-background);
  border: 2px solid var(--color-theme-primary);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-theme-primary);
  cursor: pointer;
  transition: all 0.2s;
  z-index: 10;
}

.toggle-btn:hover {
  background: var(--color-theme-primary);
  color: var(--color-terminal-background);
  box-shadow: var(--glow-2);
}

.toggle-btn:focus {
  outline: none;
  box-shadow: 0 0 0 3px var(--color-theme-glow);
}

/* WCAG 2.2 AA pointer target: keep the 24px visual, extend the hit area to 44x44. */
.toggle-btn::after {
  content: '';
  position: absolute;
  inset: -10px;
}

/* Mobile drawer backdrop; shown only inside the drawer media query below. */
.panel-backdrop {
  display: none;
}

.nav-items {
  display: flex;
  flex-direction: column;
  padding: 24px 0;
  gap: 8px;
}

.nav-item {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  color: var(--color-theme-primary);
  background: transparent;
  border: none;
  border-left: 3px solid transparent;
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
  text-decoration: none;
  gap: 12px;
  position: relative;
  width: 100%;
}

.collapsed .nav-item {
  justify-content: center;
  padding: 12px 8px;
}

.nav-item:hover {
  background: var(--color-theme-glow);
  border-left-color: var(--color-theme-primary);
}

.nav-item:focus {
  outline: none;
  background: var(--color-theme-glow);
  box-shadow: inset 0 0 0 2px var(--color-theme-glow);
}

.nav-item.active {
  background: var(--color-theme-glow);
  border-left-color: var(--color-theme-primary);
}

.nav-icon {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
}

.nav-label {
  flex: 1;
  font-size: 16px;
  font-weight: 700;
  white-space: nowrap;
  letter-spacing: 0.025em;
}

.hotkey-badge {
  font-size: 11px;
  padding: 3px 7px;
  background: var(--color-theme-glow);
  border: 1px solid var(--color-theme-primary);
  border-radius: 3px;
  font-weight: 700;
}

.wip-badge {
  font-size: 10px;
  padding: 2px 6px;
  background: var(--color-theme-glow);
  border: 1px dashed var(--color-theme-accent);
  border-radius: 3px;
  font-weight: 700;
  color: var(--color-theme-accent);
  letter-spacing: 0.05em;
}

.collapsed .nav-label,
.collapsed .hotkey-badge {
  display: none;
}

/* Nav Divider */
.nav-divider {
  margin: 16px 0 8px;
  padding: 8px 16px;
  border-top: 1px solid var(--color-theme-glow);
  border-bottom: 1px solid var(--color-theme-glow);
}

.divider-text {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--color-theme-accent);
  text-shadow: var(--glow-1);
}

/* Locked Items */
.nav-item.locked {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: none;
}

.nav-item.locked:hover {
  background: transparent;
  border-left-color: transparent;
}

.locked-label {
  color: var(--color-theme-accent);
  opacity: 0.7;
}

.lock-icon {
  width: 16px;
  height: 16px;
  color: var(--color-theme-accent);
  pointer-events: auto;
  cursor: help;
}

/* Scanline effect - theme-aware */
.side-panel::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: repeating-linear-gradient(
    0deg,
    var(--color-theme-glow) 0px,
    transparent 1px,
    transparent 2px,
    var(--color-theme-glow) 3px
  );
  opacity: 0.15;
  pointer-events: none;
}

/* === Mobile drawer (< md) ===
   Below 768px the panel becomes an off-canvas drawer: the surface slides in
   from the left over a backdrop, while the toggle stays pinned under the
   navbar so it remains reachable while the drawer is closed. */
@media (max-width: 767.98px) {
  .side-panel,
  .side-panel.collapsed {
    width: 0;
    background: transparent;
    border-right: none;
    box-shadow: none;
  }

  .side-panel::before {
    display: none;
  }

  .panel-surface {
    position: fixed;
    top: var(--chrome-height);
    bottom: 0;
    left: 0;
    width: 240px;
    overflow-x: hidden;
    overflow-y: auto;
    background: rgba(0, 0, 0, 0.95);
    border-right: 2px solid var(--color-theme-primary);
    box-shadow: var(--glow-1);
    transform: translateX(-100%);
    /* visibility keeps the closed drawer out of the tab order and the a11y
       tree; it flips immediately on open and after the slide on close. */
    visibility: hidden;
    transition:
      transform 0.3s ease,
      visibility 0s linear 0.3s;
  }

  .side-panel.mobile-open .panel-surface {
    transform: translateX(0);
    visibility: visible;
    transition:
      transform 0.3s ease,
      visibility 0s;
  }

  .panel-surface:focus {
    outline: none;
  }

  /* Scanline overlay lives on the sliding surface while off-canvas. */
  .panel-surface::before {
    content: '';
    position: absolute;
    inset: 0;
    background: repeating-linear-gradient(
      0deg,
      var(--color-theme-glow) 0px,
      transparent 1px,
      transparent 2px,
      var(--color-theme-glow) 3px
    );
    opacity: 0.15;
    pointer-events: none;
  }

  /* The persisted desktop collapse state must not shrink the drawer. */
  .side-panel.collapsed .nav-item {
    justify-content: flex-start;
    padding: 12px 16px;
  }

  .side-panel.collapsed .nav-label {
    display: block;
  }

  .side-panel.collapsed .hotkey-badge {
    display: inline-block;
  }

  /* Keep the first item clear of the pinned toggle. */
  .nav-items {
    padding-top: 64px;
  }

  .toggle-btn {
    left: 10px;
    right: auto;
    top: 12px;
  }

  .panel-backdrop {
    display: block;
    position: fixed;
    inset: 0;
    z-index: -1;
    background: rgba(0, 0, 0, 0.6);
  }
}

@media (max-width: 767.98px) and (prefers-reduced-motion: reduce) {
  .panel-surface {
    transition: none;
  }
}
</style>
