<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, useTemplateRef, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useRouter, useRoute } from 'vue-router'
import NotificationBell from './NotificationBell.vue'
import ResourceBar from './ResourceBar.vue'
import PageHeaderMetric from '@/core/components/common/PageHeaderMetric.vue'
import { useVersionDetection } from '@/core/composables/useVersionDetection'
import { audioManager } from '@/core/audio/audioManager'
import { useIncidentStore } from '@/modules/combat/stores/incident'
import type { ResourceName } from '@/modules/rooms/models/roomParts'
import { useVaultHeaderContext } from '@/modules/vault/composables/useVaultHeaderContext'

defineProps<{
  isFlickering?: boolean
  flickerOpacity?: number
  scanlinesEnabled?: boolean
}>()

const authStore = useAuthStore()
const incidentStore = useIncidentStore()
const router = useRouter()
const route = useRoute()
const {
  vault,
  isVaultRoute,
  isReady,
  loadFailed,
  dwellersCount,
  populationMax,
  populationColor,
  happiness,
  happinessColor,
  energy,
  food,
  water,
  resourceRates,
  bottleCaps,
  dwellersTooltip,
  happinessTooltip,
  capsTooltip,
} = useVaultHeaderContext()
const vaultNumber = computed(() => vault.value?.number)
const { versionBadgeVisible, showChangelog } = useVersionDetection({
  isAuthenticated: () => authStore.isAuthenticated,
})
const isAuthenticated = computed(() => authStore.isAuthenticated)
const user = computed(() => authStore.user)
const isProfileRoute = computed(() => route.path === '/profile')

// Params of the currently open vault; a critical resource warning deep-links to the room that fixes it.
const activeVaultId = computed(() => (typeof route.params.id === 'string' ? route.params.id : null))

// The rooms module is heavy, so it stays out of the FCP/LCP critical path and is loaded
// behind a dynamic import once a vault header is ready — the point at which a critical
// resource warning can deep-link to the production room that fixes it.
const productionRoomRoutes = ref<Partial<Record<ResourceName, string>>>({})
let productionRoomsTracked = false
let stopProductionRoomsWatch: (() => void) | undefined
let isUnmounted = false

async function trackProductionRooms() {
  if (productionRoomsTracked) return
  productionRoomsTracked = true
  try {
    const [{ useRoomStore }, { findProductionRoom }] = await Promise.all([
      import('@/modules/rooms/stores/room'),
      import('@/modules/rooms/models/roomParts'),
    ])
    if (isUnmounted) return
    const roomStore = useRoomStore()
    stopProductionRoomsWatch = watch(
      [() => roomStore.rooms, activeVaultId],
      ([rooms, id]) => {
        if (!id) return
        for (const resource of ['power', 'food', 'water'] as const) {
          const room = findProductionRoom(rooms, resource)
          productionRoomRoutes.value[resource] = room
            ? `/vault/${id}?roomId=${room.id}`
            : `/vault/${id}`
        }
      },
      { immediate: true }
    )
  } catch (error) {
    // A chunk can 404 after a deploy; reset the guard so the next watcher
    // trigger retries the load instead of leaving the links unresolved.
    productionRoomsTracked = false
    console.error('[NavBar] Failed to load production room modules; will retry', error)
  }
}

watch(
  [activeVaultId, isReady],
  ([id, ready]) => {
    if (id && ready) void trackProductionRooms()
  },
  { immediate: true }
)

const productionRoomRoute = (resource: ResourceName): string | undefined =>
  productionRoomRoutes.value[resource]

const logout = async () => {
  await authStore.logout()
  router.push('/login')
}

// Sound toggle — reachable while an incident is active. Reads the manager's
// reactive settings so profile hydration is reflected.
const soundMuted = computed(() => audioManager.muted)

// Only surface the sound toggle mid-incident; the alarm is the reason to mute.
const hasActiveIncidents = computed(() => incidentStore.hasActiveIncidents)

// Informational at-a-glance signal: how many designated responders are on scene.
const responderCountLabel = computed(() => {
  const count = incidentStore.totalResponderCount
  return `${count} responder${count === 1 ? '' : 's'} on scene`
})

const toggleSound = () => {
  audioManager.setMuted(!audioManager.muted)
}

// User Dropdown
const isDropdownOpen = ref(false)
const dropdownRef = ref<HTMLElement | null>(null)
const navRoot = useTemplateRef<HTMLElement>('navRoot')
let navObserver: ResizeObserver | null = null

const publishNavbarHeight = () => {
  const height = navRoot.value?.offsetHeight
  if (height) {
    document.documentElement.style.setProperty('--navbar-height', `${height}px`)
  }
}

const toggleDropdown = () => {
  isDropdownOpen.value = !isDropdownOpen.value
}

const closeDropdown = () => {
  isDropdownOpen.value = false
}

// Close dropdown when clicking outside
const handleClickOutside = (event: MouseEvent) => {
  if (dropdownRef.value && !dropdownRef.value.contains(event.target as Node)) {
    closeDropdown()
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  if (typeof ResizeObserver !== 'undefined' && navRoot.value) {
    navObserver = new ResizeObserver(publishNavbarHeight)
    navObserver.observe(navRoot.value)
  }
  publishNavbarHeight()
})

onUnmounted(() => {
  isUnmounted = true
  stopProductionRoomsWatch?.()
  document.removeEventListener('click', handleClickOutside)
  navObserver?.disconnect()
  document.documentElement.style.removeProperty('--navbar-height')
})
</script>

<template>
  <nav
    ref="navRoot"
    class="fixed left-0 right-0 top-0 z-50 bg-surface-warm p-3 shadow-lg sm:px-0 sm:py-4"
    :class="{ flicker: isFlickering && flickerOpacity === undefined }"
    :style="flickerOpacity !== undefined ? { opacity: flickerOpacity } : {}"
    role="navigation"
    aria-label="Main navigation"
  >
    <div
      v-if="scanlinesEnabled"
      class="pointer-events-none absolute inset-0 z-10 bg-[repeating-linear-gradient(to_bottom,rgba(0,0,0,0.1)_0px,rgba(0,0,0,0.1)_1px,transparent_1px,transparent_2px)]"
      aria-hidden="true"
    ></div>
    <!-- Skip to main content link for accessibility -->
    <a
      href="#main-content"
      class="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:bg-theme-primary focus:text-black focus:px-4 focus:py-2 focus:rounded"
    >
      Skip to main content
    </a>

    <div class="flex w-full items-center gap-3 sm:gap-0">
      <div
        class="flex shrink-0 items-center gap-2 sm:w-60 sm:px-4"
        role="group"
        aria-label="Vaults and current vault"
      >
        <router-link
          to="/"
          class="flex shrink-0 items-center gap-1.5 rounded px-1 py-1 font-bold text-theme-primary hover:underline focus:outline-none focus:ring-2 focus:ring-theme-primary"
          aria-label="Navigate to vaults list"
        >
          <Icon icon="mdi:format-list-bulleted" class="h-5 w-5" :ariaHidden="true" />
          <span class="hidden sm:inline">Vaults</span>
        </router-link>
        <span
          v-if="vaultNumber !== undefined"
          class="shrink-0 whitespace-nowrap font-mono text-base font-black tracking-tight text-theme-primary terminal-glow sm:text-xl"
          :aria-label="`Current vault ${vaultNumber}`"
        >
          <span class="hidden sm:inline">Vault </span>{{ vaultNumber }}
        </span>
      </div>
      <div
        class="container mx-auto flex min-w-0 flex-1 items-center gap-5 px-0 sm:gap-6 sm:px-4 lg:px-8"
      >
        <div
          class="flex min-w-0 flex-1 items-center justify-between gap-5 overflow-x-auto sm:gap-6"
        >
          <div
            v-if="isVaultRoute && isAuthenticated"
            class="flex shrink-0 items-center gap-2 sm:gap-3"
            role="group"
            aria-label="Vault population"
          >
            <div v-if="isReady" class="flex items-center gap-3">
              <PageHeaderMetric
                compact
                icon="mdi:account-group"
                :value="`${dwellersCount} / ${populationMax}`"
                label="Dwellers"
                :tooltip="dwellersTooltip"
                :value-class="populationColor"
              />
              <PageHeaderMetric
                compact
                icon="mdi:emoticon-happy"
                :value="`${happiness}%`"
                label="Happiness"
                :tooltip="happinessTooltip"
                :value-class="happinessColor"
              />
            </div>
          </div>
          <div
            v-if="isVaultRoute && isAuthenticated"
            class="shrink-0"
            role="region"
            aria-label="Vault resources"
          >
            <div
              v-if="!isReady"
              class="flex min-h-8 items-center gap-2 text-xs text-theme-primary/70"
              role="status"
              aria-live="polite"
            >
              <Icon
                :icon="loadFailed ? 'mdi:alert' : 'mdi:loading'"
                class="h-4 w-4"
                :class="{ 'animate-spin': !loadFailed }"
                :ariaHidden="true"
              />
              {{ loadFailed ? 'Vault status unavailable' : 'Syncing vault status' }}
            </div>
            <div v-else class="flex items-center gap-4">
              <ResourceBar
                navbar
                :current="energy.current"
                :max="energy.max"
                icon="mdi:lightning-bolt"
                label="Power"
                :production-rate="resourceRates?.power"
                :critical-to="productionRoomRoute('power')"
              />
              <ResourceBar
                navbar
                :current="food.current"
                :max="food.max"
                icon="mdi:food-apple"
                label="Food"
                :production-rate="resourceRates?.food"
                :critical-to="productionRoomRoute('food')"
              />
              <ResourceBar
                navbar
                :current="water.current"
                :max="water.max"
                icon="mdi:water"
                label="Water"
                :production-rate="resourceRates?.water"
                :critical-to="productionRoomRoute('water')"
              />
            </div>
          </div>
          <div
            v-if="isVaultRoute && isAuthenticated && isReady"
            class="flex shrink-0 items-center gap-3 tabular-nums"
            role="group"
            aria-label="Vault currency"
          >
            <PageHeaderMetric
              compact
              icon="mdi:bottle-soda-classic"
              value="—"
              label="Nuka bottles"
              tooltip="Nuka bottles are a preview; balances are not tracked yet."
              value-class="text-theme-primary/55"
            />
            <PageHeaderMetric
              compact
              icon="mdi:currency-usd"
              :value="bottleCaps.toLocaleString('en-US')"
              label="Caps"
              :tooltip="capsTooltip"
            />
          </div>
        </div>
        <div
          class="ml-auto flex shrink-0 items-center gap-2 sm:gap-4"
          role="group"
          aria-label="Account and notifications"
        >
          <!-- Version Update Badge (only when authenticated and there's an update) -->
          <button
            v-if="isAuthenticated && versionBadgeVisible"
            @click="showChangelog()"
            :class="[
              'relative text-theme-primary hover:text-theme-glow',
              'focus:outline-none focus:ring-2 focus:ring-theme-primary',
              'focus:ring-offset-2 focus:ring-offset-gray-800 rounded px-2 py-1 transition-colors',
            ]"
            aria-label="View changelog for new version"
          >
            <Icon icon="mdi:newspaper" class="h-5 w-5" />
            <span
              class="absolute -top-1 -right-1 h-2 w-2 bg-red-500 rounded-full animate-pulse"
            ></span>
          </button>

          <!-- Sound toggle (only while an incident is active) -->
          <button
            v-if="hasActiveIncidents"
            @click="toggleSound"
            :class="[
              'relative text-theme-primary hover:text-theme-glow',
              'focus:outline-none focus:ring-2 focus:ring-theme-primary',
              'focus:ring-offset-2 focus:ring-offset-gray-800 rounded px-2 py-1 transition-colors',
            ]"
            :aria-label="soundMuted ? 'Unmute sounds' : 'Mute sounds'"
            :aria-pressed="!soundMuted"
          >
            <Icon :icon="soundMuted ? 'mdi:volume-off' : 'mdi:volume-high'" class="h-5 w-5" />
          </button>

          <!-- Responder count (informational, only while incidents are active) -->
          <span
            v-if="hasActiveIncidents"
            class="badge-info flex items-center gap-1 rounded-full border border-theme-primary/30 px-2 py-1 text-xs text-theme-primary"
            :aria-label="responderCountLabel"
            :title="responderCountLabel"
          >
            <Icon icon="mdi:account-group" class="h-4 w-4" />
            {{ incidentStore.totalResponderCount }}
          </span>

          <!-- Notification Bell (only when authenticated) -->
          <NotificationBell v-if="isAuthenticated" />

          <!-- User-related actions on the right -->
          <router-link
            to="/login"
            v-if="!isAuthenticated"
            class="text-theme-primary hover:underline focus:outline-none focus:ring-2 focus:ring-theme-primary focus:ring-offset-2 focus:ring-offset-gray-800 rounded px-2 py-1"
            aria-label="Go to login page"
          >
            Login
          </router-link>
          <router-link
            to="/register"
            v-if="!isAuthenticated"
            class="text-theme-primary hover:underline focus:outline-none focus:ring-2 focus:ring-theme-primary focus:ring-offset-2 focus:ring-offset-gray-800 rounded px-2 py-1"
            aria-label="Go to registration page"
          >
            Register
          </router-link>

          <!-- User Dropdown -->
          <div v-if="isAuthenticated" class="relative" ref="dropdownRef">
            <button
              @click="toggleDropdown"
              @keydown.escape="closeDropdown"
              :class="[
                'inline-flex items-center gap-2 text-theme-primary hover:underline hover:bg-theme-primary/10 focus:outline-none focus:ring-2 focus:ring-theme-primary focus:ring-offset-2 focus:ring-offset-surface-warm rounded px-2 py-1 border-2 border-theme-primary/30',
                isProfileRoute ? 'bg-theme-primary/10 shadow-glow-sm' : '',
              ]"
              :aria-expanded="isDropdownOpen"
              aria-haspopup="true"
              :aria-label="`User menu for ${user?.username || 'user'}`"
            >
              <Icon icon="mdi:account-circle" class="h-5 w-5" :ariaHidden="true" />
              <span class="hidden sm:inline">{{ user?.username }}</span>
            </button>
            <Transition name="dropdown">
              <!-- Raw role="menuitem" rows: a DropdownMenu primitive is not vendored (docs/frontend/RAW_NATIVE_CONTROLS.md). -->
              <div
                v-if="isDropdownOpen"
                class="absolute right-0 mt-2 w-48 bg-black shadow-[0_0_20px_var(--color-theme-glow)] rounded border border-theme-primary z-50"
                role="menu"
                aria-label="User menu"
              >
                <router-link
                  to="/profile"
                  class="block px-4 py-2 text-theme-primary hover:bg-theme-primary/10 focus:outline-none focus:bg-theme-primary/15 transition-colors"
                  role="menuitem"
                  aria-label="View profile"
                  @click="isDropdownOpen = false"
                >
                  <Icon icon="mdi:account" class="inline h-4 w-4 mr-2" />
                  Profile
                </router-link>
                <router-link
                  to="/preferences"
                  class="block px-4 py-2 text-theme-primary hover:bg-theme-primary/10 focus:outline-none focus:bg-theme-primary/15 transition-colors"
                  role="menuitem"
                  aria-label="Display preferences"
                  @click="isDropdownOpen = false"
                >
                  <Icon icon="mdi:palette" class="inline h-4 w-4 mr-2" />
                  Preferences
                </router-link>
                <router-link
                  to="/settings"
                  class="block px-4 py-2 text-theme-primary hover:bg-theme-primary/10 focus:outline-none focus:bg-theme-primary/15 transition-colors"
                  role="menuitem"
                  aria-label="Settings"
                  @click="isDropdownOpen = false"
                >
                  <Icon icon="mdi:cog" class="inline h-4 w-4 mr-2" />
                  Settings
                </router-link>
                <router-link
                  to="/about"
                  class="block px-4 py-2 text-theme-primary hover:bg-theme-primary/10 focus:outline-none focus:bg-theme-primary/15 transition-colors"
                  role="menuitem"
                  aria-label="About this application"
                  @click="isDropdownOpen = false"
                >
                  <Icon icon="mdi:information" class="inline h-4 w-4 mr-2" />
                  About
                </router-link>
                <router-link
                  to="/changelog"
                  class="block px-4 py-2 text-theme-primary hover:bg-theme-primary/10 focus:outline-none focus:bg-theme-primary/15 transition-colors"
                  role="menuitem"
                  aria-label="View changelog"
                  @click="isDropdownOpen = false"
                >
                  <Icon icon="mdi:newspaper" class="inline h-4 w-4 mr-2" />
                  Changelog
                </router-link>
                <hr class="border-gray-700 my-1" />
                <button
                  @click="logout"
                  class="block w-full px-4 py-2 text-left text-theme-primary hover:bg-theme-primary/10 focus:outline-none focus:bg-theme-primary/15 rounded-b transition-colors"
                  role="menuitem"
                  aria-label="Logout"
                >
                  <Icon icon="mdi:logout" class="inline h-4 w-4 mr-2" />
                  Logout
                </button>
              </div>
            </Transition>
          </div>
        </div>
      </div>
    </div>
  </nav>
</template>

<style scoped>
.dropdown-enter-active {
  /* Root must outlast the staggered children (last starts at 250ms + 150ms run). */
  transition:
    opacity 0.4s ease,
    transform 0.4s ease;
}

.dropdown-leave-active {
  transition:
    opacity 0.1s ease,
    transform 0.1s ease;
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-10px) scale(0.95);
}

/* Staggered item reveal */
.dropdown-enter-active > * {
  animation: dropdown-item-in 0.15s ease both;
}

.dropdown-enter-active > *:nth-child(1) {
  animation-delay: 0.05s;
}

.dropdown-enter-active > *:nth-child(2) {
  animation-delay: 0.1s;
}

.dropdown-enter-active > *:nth-child(3) {
  animation-delay: 0.15s;
}

.dropdown-enter-active > *:nth-child(n + 4) {
  animation-delay: 0.2s;
}

.dropdown-enter-active > *:last-child {
  animation-delay: 0.25s;
}

@keyframes dropdown-item-in {
  from {
    opacity: 0;
    transform: translateX(-10px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .dropdown-enter-active,
  .dropdown-leave-active {
    transition-duration: 0s;
  }

  .dropdown-enter-active > * {
    animation: none;
  }
}
</style>
