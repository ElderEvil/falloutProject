import { computed } from 'vue'
import { useLocalStorage } from '@vueuse/core'

export type BadgeStyle = 'color' | 'mono'

const BADGE_STYLE_ATTRIBUTE = 'data-badge-style'

// Global display preference, not dweller-domain state: any view rendering a
// badge reads the same value without a profile -> dwellers dependency.
// Defaults to colour, i.e. the badges look exactly as they always have.
const badgeStyle = useLocalStorage<BadgeStyle>('badge-style', 'color')

function applyBadgeStyle(style: BadgeStyle) {
  if (typeof document === 'undefined') return
  document.documentElement.setAttribute(BADGE_STYLE_ATTRIBUTE, style)
}

export function useBadgeStyle() {
  function setBadgeStyle(style: BadgeStyle) {
    badgeStyle.value = style
    applyBadgeStyle(style)
  }

  function toggleBadgeStyle() {
    setBadgeStyle(badgeStyle.value === 'mono' ? 'color' : 'mono')
  }

  applyBadgeStyle(badgeStyle.value)

  return {
    badgeStyle: computed(() => badgeStyle.value),
    isMonochrome: computed(() => badgeStyle.value === 'mono'),
    setBadgeStyle,
    toggleBadgeStyle,
  }
}
