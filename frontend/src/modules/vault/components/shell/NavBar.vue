<script setup lang="ts">
import { ref, computed, inject, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useRouter, useRoute } from 'vue-router'
import NotificationBell from './NotificationBell.vue'
import { useVersionDetection } from '@/core/composables/useVersionDetection'

const authStore = useAuthStore()
const vaultStore = useVaultStore()
const router = useRouter()
const route = useRoute()
const { versionBadgeVisible, showChangelog } = useVersionDetection({
  isAuthenticated: () => authStore.isAuthenticated,
})
const isAuthenticated = computed(() => authStore.isAuthenticated)
const user = computed(() => authStore.user)
const isProfileRoute = computed(() => route.path === '/profile')
const currentVaultId = computed(() => {
  // For chat routes, use activeVaultId from store
  // For vault routes, use route param
  if (route.name === 'DwellerChatPage') {
    return vaultStore.activeVaultId
  }
  return route.params.id as string | undefined
})

const logout = async () => {
  await authStore.logout()
  router.push('/login')
}

const isFlickering = inject('isFlickering')
const toggleFlickering = inject('toggleFlickering')

// User Dropdown
const isDropdownOpen = ref(false)
const dropdownRef = ref<HTMLElement | null>(null)

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
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <nav
    class="fixed left-0 right-0 top-0 z-50 bg-surface-warm p-4 shadow-lg"
    role="navigation"
    aria-label="Main navigation"
  >
    <!-- Skip to main content link for accessibility -->
    <a
      href="#main-content"
      class="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:bg-[var(--color-theme-primary)] focus:text-black focus:px-4 focus:py-2 focus:rounded"
    >
      Skip to main content
    </a>

    <div class="container mx-auto flex items-center justify-between">
      <div class="flex space-x-4 items-center" role="menubar">
        <!-- Vault List Button (main navigation) -->
        <router-link
          to="/"
          class="text-[var(--color-theme-primary)] hover:underline font-bold focus:outline-none focus:ring-2 focus:ring-[var(--color-theme-primary)] focus:ring-offset-2 focus:ring-offset-[var(--color-surface-warm)] rounded px-2 py-1"
          role="menuitem"
          aria-label="Navigate to vaults list"
        >
          Vaults
        </router-link>
      </div>
      <div class="flex items-center space-x-4">
        <!-- Version Update Badge (only when authenticated and there's an update) -->
        <button
          v-if="isAuthenticated && versionBadgeVisible"
          @click="showChangelog()"
          :class="[
            'relative text-[var(--color-theme-primary)] hover:text-[var(--color-theme-glow)]',
            'focus:outline-none focus:ring-2 focus:ring-[var(--color-theme-primary)]',
            'focus:ring-offset-2 focus:ring-offset-gray-800 rounded px-2 py-1 transition-colors',
          ]"
          aria-label="View changelog for new version"
        >
          <Icon icon="mdi:newspaper" class="h-5 w-5" />
          <span
            class="absolute -top-1 -right-1 h-2 w-2 bg-red-500 rounded-full animate-pulse"
          ></span>
        </button>

        <!-- Notification Bell (only when authenticated) -->
        <NotificationBell v-if="isAuthenticated" />

        <!-- User-related actions on the right -->
        <router-link
          to="/login"
          v-if="!isAuthenticated"
          class="text-[var(--color-theme-primary)] hover:underline focus:outline-none focus:ring-2 focus:ring-[var(--color-theme-primary)] focus:ring-offset-2 focus:ring-offset-gray-800 rounded px-2 py-1"
          aria-label="Go to login page"
        >
          Login
        </router-link>
        <router-link
          to="/register"
          v-if="!isAuthenticated"
          class="text-[var(--color-theme-primary)] hover:underline focus:outline-none focus:ring-2 focus:ring-[var(--color-theme-primary)] focus:ring-offset-2 focus:ring-offset-gray-800 rounded px-2 py-1"
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
              'text-[var(--color-theme-primary)] hover:underline hover:bg-theme-primary/10 focus:outline-none focus:ring-2 focus:ring-[var(--color-theme-primary)] focus:ring-offset-2 focus:ring-offset-[var(--color-surface-warm)] rounded px-2 py-1 border-2 border-[var(--color-theme-primary)]/30',
              isProfileRoute ? 'bg-theme-primary/10 shadow-glow-sm' : '',
            ]"
            :aria-expanded="isDropdownOpen"
            aria-haspopup="true"
            :aria-label="`User menu for ${user?.username || 'user'}`"
          >
            {{ user?.username }}
          </button>
          <Transition name="dropdown">
            <div
              v-if="isDropdownOpen"
              class="absolute right-0 mt-2 w-48 bg-black shadow-[0_0_20px_var(--color-theme-glow)] rounded border border-[var(--color-theme-primary)]"
              role="menu"
              aria-label="User menu"
              style="z-index: 50"
            >
              <router-link
                to="/profile"
                class="block px-4 py-2 text-[var(--color-theme-primary)] hover:bg-theme-primary/10 focus:outline-none focus:bg-theme-primary/15 transition-colors"
                role="menuitem"
                aria-label="View profile"
                @click="isDropdownOpen = false"
              >
                <Icon icon="mdi:account" class="inline h-4 w-4 mr-2" />
                Profile
              </router-link>
              <router-link
                to="/preferences"
                class="block px-4 py-2 text-[var(--color-theme-primary)] hover:bg-theme-primary/10 focus:outline-none focus:bg-theme-primary/15 transition-colors"
                role="menuitem"
                aria-label="Display preferences"
                @click="isDropdownOpen = false"
              >
                <Icon icon="mdi:palette" class="inline h-4 w-4 mr-2" />
                Preferences
              </router-link>
              <router-link
                to="/settings"
                class="block px-4 py-2 text-[var(--color-theme-primary)] hover:bg-theme-primary/10 focus:outline-none focus:bg-theme-primary/15 transition-colors"
                role="menuitem"
                aria-label="Settings"
                @click="isDropdownOpen = false"
              >
                <Icon icon="mdi:cog" class="inline h-4 w-4 mr-2" />
                Settings
              </router-link>
              <router-link
                to="/about"
                class="block px-4 py-2 text-[var(--color-theme-primary)] hover:bg-theme-primary/10 focus:outline-none focus:bg-theme-primary/15 transition-colors"
                role="menuitem"
                aria-label="About this application"
                @click="isDropdownOpen = false"
              >
                <Icon icon="mdi:information" class="inline h-4 w-4 mr-2" />
                About
              </router-link>
              <router-link
                to="/changelog"
                class="block px-4 py-2 text-[var(--color-theme-primary)] hover:bg-theme-primary/10 focus:outline-none focus:bg-theme-primary/15 transition-colors"
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
                class="block w-full px-4 py-2 text-left text-[var(--color-theme-primary)] hover:bg-theme-primary/10 focus:outline-none focus:bg-theme-primary/15 rounded-b transition-colors"
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
  </nav>
</template>

<style scoped>
.dropdown-enter-active {
  transition:
    opacity 0.15s ease,
    transform 0.15s ease;
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
