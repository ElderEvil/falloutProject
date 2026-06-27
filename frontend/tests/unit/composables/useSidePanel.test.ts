import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref } from 'vue'

vi.mock('@vueuse/core', () => ({
  useLocalStorage: <T>(_key: string, defaultValue: T) => ref<T>(defaultValue),
}))

import { useSidePanel } from '@/core/composables/useSidePanel'

describe('useSidePanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should initialize with collapsed false, expanded true', () => {
    const { isCollapsed, isExpanded } = useSidePanel()

    expect(isCollapsed.value).toBe(false)
    expect(isExpanded.value).toBe(true)
  })

  it('toggle() flips isCollapsed', () => {
    const { isCollapsed, toggle } = useSidePanel()

    toggle()
    expect(isCollapsed.value).toBe(true)

    toggle()
    expect(isCollapsed.value).toBe(false)
  })

  it('collapse() sets isCollapsed to true', () => {
    const { isCollapsed, collapse } = useSidePanel()

    collapse()
    expect(isCollapsed.value).toBe(true)
  })

  it('expand() sets isCollapsed to false', () => {
    const { isCollapsed, collapse, expand } = useSidePanel()

    collapse()
    expect(isCollapsed.value).toBe(true)

    expand()
    expect(isCollapsed.value).toBe(false)
  })

  it('isExpanded is the inverse of isCollapsed', () => {
    const { isCollapsed, isExpanded, toggle } = useSidePanel()

    expect(isExpanded.value).toBe(!isCollapsed.value)

    toggle()
    expect(isExpanded.value).toBe(!isCollapsed.value)
  })
})
