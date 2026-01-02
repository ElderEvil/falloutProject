<script setup lang="ts">
import { ref, computed, inject, onMounted, onUnmounted, type Ref, type ComputedRef } from 'vue';
import { Icon } from '@iconify/vue';
import { useAuthStore } from '@/stores/auth';
import { useVaultStore } from '@/stores/vault';
import { useRouter, useRoute } from 'vue-router';
import type { Theme, ThemeName } from '@/composables/useTheme';

const authStore = useAuthStore();
const vaultStore = useVaultStore();
const router = useRouter();
const route = useRoute();
const isAuthenticated = computed(() => authStore.isAuthenticated);
const user = computed(() => authStore.user);
const currentVaultId = computed(() => route.params.id as string | undefined);

const logout = async () => {
  await authStore.logout();
  router.push('/login');
};

const isFlickering = inject('isFlickering');
const toggleFlickering = inject('toggleFlickering');

// Theme switcher
const currentTheme = inject<ComputedRef<Theme>>('currentTheme')!;
const setTheme = inject<(theme: ThemeName) => void>('setTheme')!;
const availableThemes = inject<ComputedRef<Theme[]>>('availableThemes')!;
const isThemeDropdownOpen = ref(false);
const themeDropdownRef = ref<HTMLElement | null>(null);

// User Dropdown
const isDropdownOpen = ref(false);
const dropdownRef = ref<HTMLElement | null>(null);

const toggleDropdown = () => {
  isDropdownOpen.value = !isDropdownOpen.value;
  isThemeDropdownOpen.value = false; // Close theme dropdown
};

const closeDropdown = () => {
  isDropdownOpen.value = false;
};

const toggleThemeDropdown = () => {
  isThemeDropdownOpen.value = !isThemeDropdownOpen.value;
  isDropdownOpen.value = false; // Close user dropdown
};

const closeThemeDropdown = () => {
  isThemeDropdownOpen.value = false;
};

const selectTheme = (themeName: ThemeName) => {
  setTheme(themeName);
  closeThemeDropdown();
};

// Close dropdown when clicking outside
const handleClickOutside = (event: MouseEvent) => {
  if (dropdownRef.value && !dropdownRef.value.contains(event.target as Node)) {
    closeDropdown();
  }
  if (themeDropdownRef.value && !themeDropdownRef.value.contains(event.target as Node)) {
    closeThemeDropdown();
  }
};

onMounted(() => {
  document.addEventListener('click', handleClickOutside);
});

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside);
});

</script>

<template>
  <nav class="bg-gray-800 p-4 shadow-lg" role="navigation" aria-label="Main navigation">
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
          class="text-[var(--color-theme-primary)] hover:underline font-bold focus:outline-none focus:ring-2 focus:ring-[var(--color-theme-primary)] focus:ring-offset-2 focus:ring-offset-gray-800 rounded px-2 py-1"
          role="menuitem"
          aria-label="Navigate to vaults list"
        >
          Vaults
        </router-link>

        <!-- Context-aware navigation (only when in a vault) -->
        <template v-if="isAuthenticated && currentVaultId">
          <span class="text-gray-600" aria-hidden="true">|</span>
          <router-link
            :to="`/vault/${currentVaultId}/dwellers`"
            class="text-[var(--color-theme-primary)] hover:underline focus:outline-none focus:ring-2 focus:ring-[var(--color-theme-primary)] focus:ring-offset-2 focus:ring-offset-gray-800 rounded px-2 py-1"
            role="menuitem"
            aria-label="Navigate to dwellers management"
          >
            Dwellers
          </router-link>
          <router-link
            :to="`/vault/${currentVaultId}/objectives`"
            class="text-[var(--color-theme-primary)] hover:underline focus:outline-none focus:ring-2 focus:ring-[var(--color-theme-primary)] focus:ring-offset-2 focus:ring-offset-gray-800 rounded px-2 py-1"
            role="menuitem"
            aria-label="Navigate to objectives"
          >
            Objectives
          </router-link>
        </template>
      </div>
      <div class="flex items-center space-x-4">
        <!-- Theme Switcher -->
        <div class="relative" ref="themeDropdownRef">
          <button
            @click="toggleThemeDropdown"
            @keydown.escape="closeThemeDropdown"
            class="terminal-glow-subtle text-[var(--color-theme-primary)] hover:underline focus:outline-none focus:ring-2 focus:ring-[var(--color-theme-primary)] focus:ring-offset-2 focus:ring-offset-gray-800 rounded px-2 py-1 flex items-center gap-2"
            :aria-expanded="isThemeDropdownOpen"
            aria-haspopup="true"
            aria-label="Switch theme"
            title="Switch UI theme"
          >
            <Icon icon="mdi:palette" class="h-4 w-4" />
          </button>
          <div
            v-if="isThemeDropdownOpen"
            class="absolute right-0 mt-2 w-64 bg-black shadow-[0_0_20px_var(--color-theme-glow)] rounded border border-[var(--color-theme-primary)]"
            role="menu"
            aria-label="Theme menu"
            style="z-index: 50"
          >
            <button
              v-for="theme in availableThemes"
              :key="theme.name"
              @click="selectTheme(theme.name)"
              class="block w-full px-4 py-3 text-left transition-colors"
              :class="[
                currentTheme.name === theme.name
                  ? 'bg-[var(--color-theme-primary)]/20 text-[var(--color-theme-primary)] font-bold'
                  : 'text-[var(--color-theme-primary)] hover:bg-gray-900'
              ]"
              role="menuitem"
              :aria-label="`Switch to ${theme.displayName}`"
            >
              <div class="flex items-center gap-2">
                <Icon
                  v-if="currentTheme.name === theme.name"
                  icon="mdi:check-circle"
                  class="h-4 w-4"
                />
                <div class="flex-1">
                  <div class="font-bold text-sm">{{ theme.displayName }}</div>
                  <div class="text-xs opacity-70 mt-1">{{ theme.description }}</div>
                </div>
              </div>
            </button>
          </div>
        </div>

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
            class="terminal-glow text-[var(--color-theme-primary)] hover:underline focus:outline-none focus:ring-2 focus:ring-[var(--color-theme-primary)] focus:ring-offset-2 focus:ring-offset-gray-800 rounded px-2 py-1"
            :aria-expanded="isDropdownOpen"
            aria-haspopup="true"
            :aria-label="`User menu for ${user?.username || 'user'}`"
          >
            {{ user?.username }}
          </button>
          <div
            v-if="isDropdownOpen"
            class="absolute right-0 mt-2 w-48 bg-black shadow-[0_0_20px_var(--color-theme-glow)] rounded border border-[var(--color-theme-primary)]"
            role="menu"
            aria-label="User menu"
            style="z-index: 50"
          >
            <router-link
              to="/profile"
              class="block px-4 py-2 text-[var(--color-theme-primary)] hover:bg-gray-900 focus:outline-none focus:bg-gray-900 transition-colors"
              role="menuitem"
              aria-label="View profile"
              @click="isDropdownOpen = false"
            >
              <Icon icon="mdi:account" class="inline h-4 w-4 mr-2" />
              Profile
            </router-link>
            <router-link
              to="/about"
              class="block px-4 py-2 text-[var(--color-theme-primary)] hover:bg-gray-900 focus:outline-none focus:bg-gray-900 transition-colors"
              role="menuitem"
              aria-label="About this application"
              @click="isDropdownOpen = false"
            >
              <Icon icon="mdi:information" class="inline h-4 w-4 mr-2" />
              About
            </router-link>
            <hr class="border-gray-700 my-1" />
            <button
              @click="logout"
              class="block w-full px-4 py-2 text-left text-[var(--color-theme-primary)] hover:bg-gray-900 focus:outline-none focus:bg-gray-900 rounded-b transition-colors"
              role="menuitem"
              aria-label="Logout"
            >
              <Icon icon="mdi:logout" class="inline h-4 w-4 mr-2" />
              Logout
            </button>
          </div>
        </div>
      </div>
    </div>
  </nav>
</template>
