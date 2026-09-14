import { describe, it, expect, afterEach } from 'vitest'
import { useBackNavigation } from '@/core/composables/useBackNavigation'

function setHistoryState(state: unknown): void {
  Object.defineProperty(window.history, 'state', {
    value: state,
    configurable: true,
    writable: true,
  })
}

describe('useBackNavigation', () => {
  afterEach(() => setHistoryState(null))

  it('returns to the vault overview when the user came from Overview', () => {
    setHistoryState({ back: '/vault/abc' })
    const nav = useBackNavigation('Settings', () => '/')

    expect(nav.backPath()).toBe('/vault/abc')
    expect(nav.backLabel()).toBe('Back to Overview')
    expect(nav.breadcrumbs()).toEqual([
      { label: 'Overview', to: '/vault/abc' },
      { label: 'Settings' },
    ])
  })

  it('returns to the profile screen when the user came from Profile', () => {
    setHistoryState({ back: '/profile' })
    const nav = useBackNavigation('Settings', () => '/vault/abc')

    expect(nav.backLabel()).toBe('Back to Profile')
    expect(nav.breadcrumbs()).toEqual([
      { label: 'Profile', to: '/profile' },
      { label: 'Settings' },
    ])
  })

  it('labels unknown origins generically instead of guessing', () => {
    setHistoryState({ back: '/somewhere/else' })
    const nav = useBackNavigation('Settings', () => '/')

    expect(nav.backLabel()).toBe('Back')
    expect(nav.backPath()).toBe('/somewhere/else')
    expect(nav.breadcrumbs()).toEqual([
      { label: 'Previous screen', to: '/somewhere/else' },
      { label: 'Settings' },
    ])
  })

  it('falls back to the given screen when there is no in-app history', () => {
    setHistoryState(null)
    const nav = useBackNavigation('Settings', () => '/vault/abc')

    expect(nav.backPath()).toBe('/vault/abc')
    expect(nav.backLabel()).toBe('Back to Overview')
    expect(nav.breadcrumbs()).toEqual([])
  })
})
