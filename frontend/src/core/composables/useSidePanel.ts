import { useLocalStorage } from '@vueuse/core'
import { computed } from 'vue'

/**
 * useSidePanel - Manage side panel state with localStorage persistence
 *
 * Provides:
 * - Collapsed/expanded state
 * - Toggle functionality
 * - Keyboard shortcut support (handled by parent component)
 */
export function useSidePanel() {
  // Persist collapsed state in localStorage
  const isCollapsed = useLocalStorage('sidePanel_collapsed', false)

  // Computed for easier state checks
  const isExpanded = computed(() => !isCollapsed.value)

  function toggle() {
    isCollapsed.value = !isCollapsed.value
  }

  function collapse() {
    isCollapsed.value = true
  }

  function expand() {
    isCollapsed.value = false
  }

  return {
    isCollapsed,
    isExpanded,
    toggle,
    collapse,
    expand,
  }
}
