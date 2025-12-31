<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'
import { useRoute, useRouter } from 'vue-router'
import { useSidePanel } from '@/composables/useSidePanel'

const route = useRoute()
const router = useRouter()
const { isCollapsed, toggle } = useSidePanel()

const vaultId = computed(() => route.params.id as string | undefined)

interface NavItem {
  id: string
  label: string
  icon: string
  path: string
  hotkey?: string
}

const navItems = computed((): NavItem[] => {
  if (!vaultId.value) return []

  return [
    {
      id: 'overview',
      label: 'Overview',
      icon: 'mdi:view-dashboard',
      path: `/vault/${vaultId.value}`,
      hotkey: '1'
    },
    {
      id: 'dwellers',
      label: 'Dwellers',
      icon: 'mdi:account-group',
      path: `/vault/${vaultId.value}/dwellers`,
      hotkey: '2'
    },
    {
      id: 'objectives',
      label: 'Objectives',
      icon: 'mdi:target',
      path: `/vault/${vaultId.value}/objectives`,
      hotkey: '3'
    }
  ]
})

const isActive = (path: string) => {
  return route.path === path
}

const navigate = (path: string) => {
  router.push(path)
}

// Keyboard shortcuts
const handleKeyPress = (e: KeyboardEvent) => {
  // Toggle panel with Ctrl/Cmd + B
  if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
    e.preventDefault()
    toggle()
    return
  }

  // Navigate with number keys (only if not in an input)
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
    return
  }

  const item = navItems.value.find(item => item.hotkey === e.key)
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
</script>

<template>
  <aside
    class="side-panel"
    :class="{ collapsed: isCollapsed }"
    role="navigation"
    aria-label="Game navigation panel"
  >
    <!-- Toggle Button -->
    <button
      @click="toggle"
      class="toggle-btn"
      :aria-label="isCollapsed ? 'Expand navigation panel' : 'Collapse navigation panel'"
      :title="`${isCollapsed ? 'Expand' : 'Collapse'} (Ctrl+B)`"
    >
      <Icon
        :icon="isCollapsed ? 'mdi:chevron-right' : 'mdi:chevron-left'"
        class="h-6 w-6"
      />
    </button>

    <!-- Navigation Items -->
    <nav class="nav-items">
      <button
        v-for="item in navItems"
        :key="item.id"
        @click="navigate(item.path)"
        class="nav-item"
        :class="{ active: isActive(item.path) }"
        :aria-label="`Navigate to ${item.label}${item.hotkey ? ' (Press ' + item.hotkey + ')' : ''}`"
        :title="`${item.label}${item.hotkey ? ' (' + item.hotkey + ')' : ''}`"
      >
        <Icon :icon="item.icon" class="nav-icon" />
        <span v-if="!isCollapsed" class="nav-label">{{ item.label }}</span>
        <span v-if="!isCollapsed && item.hotkey" class="hotkey-badge">{{ item.hotkey }}</span>
      </button>
    </nav>
  </aside>
</template>

<style scoped>
.side-panel {
  position: fixed;
  left: 0;
  top: 64px; /* Below navbar */
  bottom: 0;
  width: 240px;
  background: rgba(0, 0, 0, 0.95);
  border-right: 2px solid #00ff00;
  box-shadow: 0 0 20px rgba(0, 255, 0, 0.3);
  transition: width 0.3s ease, transform 0.3s ease;
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
  background: #000;
  border: 2px solid #00ff00;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #00ff00;
  cursor: pointer;
  transition: all 0.2s;
  z-index: 10;
}

.toggle-btn:hover {
  background: #00ff00;
  color: #000;
  box-shadow: 0 0 15px rgba(0, 255, 0, 0.6);
}

.toggle-btn:focus {
  outline: none;
  box-shadow: 0 0 0 3px rgba(0, 255, 0, 0.4);
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
  color: #00ff00;
  background: transparent;
  border: none;
  border-left: 3px solid transparent;
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
  gap: 12px;
  position: relative;
  width: 100%;
}

.collapsed .nav-item {
  justify-content: center;
  padding: 12px 8px;
}

.nav-item:hover {
  background: rgba(0, 255, 0, 0.1);
  border-left-color: #00ff00;
}

.nav-item:focus {
  outline: none;
  background: rgba(0, 255, 0, 0.15);
  box-shadow: inset 0 0 0 2px rgba(0, 255, 0, 0.4);
}

.nav-item.active {
  background: rgba(0, 255, 0, 0.2);
  border-left-color: #00ff00;
  box-shadow: 0 0 10px rgba(0, 255, 0, 0.3);
}

.nav-icon {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
}

.nav-label {
  flex: 1;
  font-size: 16px; /* Increased from 14px */
  font-weight: 700; /* Bold for better readability */
  white-space: nowrap;
  letter-spacing: 0.025em; /* Better spacing */
  text-shadow: 0 0 4px rgba(0, 255, 0, 0.4); /* Subtle glow */
}

.hotkey-badge {
  font-size: 11px; /* Slightly larger */
  padding: 3px 7px; /* More padding */
  background: rgba(0, 255, 0, 0.2);
  border: 1px solid #00ff00;
  border-radius: 3px;
  font-weight: 700; /* Bolder */
  text-shadow: 0 0 3px rgba(0, 255, 0, 0.5);
}

.collapsed .nav-label,
.collapsed .hotkey-badge {
  display: none;
}

/* Scanline effect */
.side-panel::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: repeating-linear-gradient(
    0deg,
    rgba(0, 255, 0, 0.03) 0px,
    transparent 1px,
    transparent 2px,
    rgba(0, 255, 0, 0.03) 3px
  );
  pointer-events: none;
}
</style>
