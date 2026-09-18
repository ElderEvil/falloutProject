import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { useProfileStore } from '@/modules/profile/stores/profile'
import { useSoundProfileSync } from '@/modules/profile/composables/useSoundProfileSync'
import type { UserProfile } from '@/models/profile'

const audioMock = vi.hoisted(() => {
  const state = {
    muted: true,
    volumes: { ui: 0.6, sfx: 0.8, music: 0.4 } as Record<string, number>,
    handler: null as (() => void) | null,
  }
  return {
    state,
    applySettings: vi.fn(),
    setChangeHandler: vi.fn((fn: (() => void) | null) => {
      state.handler = fn
    }),
    trigger: () => state.handler?.(),
  }
})

vi.mock('@/core/audio/audioManager', () => ({
  audioManager: {
    get muted() {
      return audioMock.state.muted
    },
    get volumes() {
      return audioMock.state.volumes
    },
    applySettings: audioMock.applySettings,
    setChangeHandler: audioMock.setChangeHandler,
  },
}))

const SOUND = { muted: false, volumes: { ui: 0.2, sfx: 0.5, music: 0.9 } }

function makeProfile(preferences: Record<string, unknown>): UserProfile {
  return {
    id: 'profile-1',
    user_id: 'user-1',
    bio: null,
    avatar_url: null,
    preferences,
    total_dwellers_created: 0,
    total_caps_earned: 0,
    total_explorations: 0,
    total_rooms_built: 0,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  }
}

setActivePinia(createPinia())
const store = useProfileStore()
const savePreferences = vi.fn().mockResolvedValue(undefined)
store.savePreferences = savePreferences
useSoundProfileSync()

describe('useSoundProfileSync', () => {
  beforeEach(async () => {
    vi.useFakeTimers()
    store.profile = null
    await nextTick()
    savePreferences.mockClear()
    audioMock.applySettings.mockClear()
    audioMock.state.muted = true
    audioMock.state.volumes = { ui: 0.6, sfx: 0.8, music: 0.4 }
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('hydrates from the profile sound preference', async () => {
    store.profile = makeProfile({ theme: 'fnv', sound: SOUND })
    await nextTick()

    expect(audioMock.applySettings).toHaveBeenCalledWith(SOUND)
  })

  it('does not save when hydration applies settings', async () => {
    store.profile = makeProfile({ sound: SOUND })
    await nextTick()

    expect(audioMock.applySettings).toHaveBeenCalled()
    expect(savePreferences).not.toHaveBeenCalled()
  })

  it('debounces local edits into one save that preserves other preference keys', async () => {
    store.profile = makeProfile({ theme: 'fnv' })
    await nextTick()

    audioMock.state.muted = false
    audioMock.trigger()
    audioMock.trigger()
    audioMock.trigger()
    expect(savePreferences).not.toHaveBeenCalled()

    vi.advanceTimersByTime(400)
    await nextTick()

    expect(savePreferences).toHaveBeenCalledTimes(1)
    expect(savePreferences).toHaveBeenCalledWith({
      theme: 'fnv',
      sound: { muted: false, volumes: { ui: 0.6, sfx: 0.8, music: 0.4 } },
    })
  })

  it('skips saving while no profile is loaded', async () => {
    audioMock.trigger()
    vi.advanceTimersByTime(400)
    await nextTick()

    expect(savePreferences).not.toHaveBeenCalled()
  })
})
