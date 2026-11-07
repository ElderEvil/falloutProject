import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import FirstRunSetupModal from '@/modules/profile/components/FirstRunSetupModal.vue'
import { useProfileStore } from '@/modules/profile/stores/profile'
import { useTheme } from '@/core/composables/useTheme'
import { audioManager } from '@/core/audio/audioManager'
import { apiPut } from '@/core/utils/api'
import type { UserProfile } from '@/models/profile'

vi.mock('@/core/utils/api', () => ({
  apiGet: vi.fn(),
  apiPut: vi.fn(),
}))

const mockProfile: UserProfile = {
  id: 'profile-123',
  user_id: 'user-123',
  bio: null,
  avatar_url: null,
  preferences: {},
  total_dwellers_created: 0,
  total_caps_earned: 0,
  total_explorations: 0,
  total_rooms_built: 0,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

function mountModal() {
  return mount(FirstRunSetupModal, {
    global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
  })
}

const buttonWithText = (wrapper: ReturnType<typeof mountModal>, text: string) =>
  wrapper.findAll('button').find((button) => button.text().includes(text))

describe('FirstRunSetupModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
    audioManager.setMuted(true)
    const store = useProfileStore()
    store.profile = { ...mockProfile, preferences: {} }
    vi.mocked(apiPut).mockImplementation(async (_url, data) => {
      const preferences = (data as { preferences: Record<string, unknown> }).preferences
      return { ...mockProfile, preferences }
    })
  })

  it('saves a completed setup when continuing', async () => {
    const wrapper = mountModal()

    await buttonWithText(wrapper, 'Continue')?.trigger('click')
    await flushPromises()

    expect(apiPut).toHaveBeenCalledWith('/api/v1/users/me/profile', {
      preferences: { setup: { version: 1, completed: true, skipped: false } },
    })
    expect(wrapper.emitted('complete')).toHaveLength(1)
  })

  it('saves a skipped setup when the player skips', async () => {
    const wrapper = mountModal()

    await buttonWithText(wrapper, 'Skip for now')?.trigger('click')
    await flushPromises()

    expect(apiPut).toHaveBeenCalledWith('/api/v1/users/me/profile', {
      preferences: { setup: { version: 1, completed: true, skipped: true } },
    })
    expect(wrapper.emitted('complete')).toHaveLength(1)
  })

  it('applies and persists a selected theme', async () => {
    const wrapper = mountModal()

    await wrapper.get('[aria-label="Select Fallout: New Vegas — Amber Terminal"]').trigger('click')
    await flushPromises()

    expect(useTheme().currentTheme.value.name).toBe('fnv')
    expect(apiPut).toHaveBeenCalledWith('/api/v1/users/me/profile', {
      preferences: { theme: 'fnv' },
    })
  })

  it('enables sound from the setup controls', async () => {
    const wrapper = mountModal()

    await wrapper.get('button[role="switch"][aria-label="Enable sound"]').trigger('click')

    expect(audioManager.muted).toBe(false)
    audioManager.setMuted(true)
  })

  it('keeps the modal open and reports a save failure', async () => {
    vi.mocked(apiPut).mockRejectedValueOnce(new Error('network down'))
    const wrapper = mountModal()

    await buttonWithText(wrapper, 'Continue')?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Could not save this setup')
    expect(wrapper.emitted('complete')).toBeUndefined()
  })
})
