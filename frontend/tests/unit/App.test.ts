import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import App from '@/App.vue'

const profileStoreMock = vi.hoisted(() => ({
  ensureProfileLoaded: vi.fn(),
  clearProfile: vi.fn(),
}))

vi.mock('@/modules/profile/stores/profile', () => ({
  useProfileStore: () => ({
    profile: null,
    ensureProfileLoaded: profileStoreMock.ensureProfileLoaded,
    clearProfile: profileStoreMock.clearProfile,
    savePreferences: vi.fn(),
  }),
}))

vi.mock('@/modules/profile/composables/useSoundProfileSync', () => ({
  useSoundProfileSync: () => ({ flush: vi.fn() }),
}))

vi.mock('@/core/composables/useVisualEffects', () => ({
  useVisualEffects: () => ({
    flickering: ref(false),
    scanlines: ref(false),
    glowClass: ref(''),
    flickerOpacity: ref(1),
    toggleFlickering: vi.fn(),
  }),
}))
vi.mock('@/core/composables/useTheme', () => ({
  useTheme: () => ({
    currentTheme: ref('green'),
    setTheme: vi.fn(),
    availableThemes: [],
  }),
}))
vi.mock('@/core/composables/useTokenRefresh', () => ({ useTokenRefresh: vi.fn() }))
vi.mock('@/modules/vault/composables/useResourceWarnings', () => ({ useResourceWarnings: vi.fn() }))
vi.mock('@/core/composables/useVersionDetection', () => ({
  useVersionDetection: () => ({
    showChangelogModal: ref(false),
    versionInfo: { current: '2.30.0', lastSeen: null },
    markVersionAsSeen: vi.fn(),
    hideChangelog: vi.fn(),
  }),
}))
vi.mock('@/core/composables/useGaryMode', () => ({ useGaryMode: () => ({ isGaryMode: ref(false) }) }))
vi.mock('@/core/composables/useFakeCrash', () => ({
  useFakeCrash: () => ({ isCrashing: ref(false), resetCrash: vi.fn() }),
}))

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('mounts without unresolved-component warnings after Nuxt UI removal', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})

    mount(App, {
      global: {
        plugins: [createPinia()],
        stubs: {
          DefaultLayout: { template: '<main><slot /></main>' },
          UToastContainer: true,
          ChangelogModal: true,
          GaryOverlay: true,
          FakeCrashOverlay: true,
          'router-view': true,
        },
      },
    })

    expect(warn).not.toHaveBeenCalledWith(expect.stringContaining('Failed to resolve component'))
    expect(warn).not.toHaveBeenCalledWith(expect.stringContaining('UApp'))
  })

  it('loads the profile when authenticated', () => {
    localStorage.setItem('token', 'test-token')

    mount(App, {
      global: {
        plugins: [createPinia()],
        stubs: {
          DefaultLayout: { template: '<main><slot /></main>' },
          UToastContainer: true,
          ChangelogModal: true,
          GaryOverlay: true,
          FakeCrashOverlay: true,
          'router-view': true,
        },
      },
    })

    expect(profileStoreMock.ensureProfileLoaded).toHaveBeenCalled()
    expect(profileStoreMock.clearProfile).not.toHaveBeenCalled()
  })

  it('clears the profile when not authenticated', () => {
    mount(App, {
      global: {
        plugins: [createPinia()],
        stubs: {
          DefaultLayout: { template: '<main><slot /></main>' },
          UToastContainer: true,
          ChangelogModal: true,
          GaryOverlay: true,
          FakeCrashOverlay: true,
          'router-view': true,
        },
      },
    })

    expect(profileStoreMock.clearProfile).toHaveBeenCalled()
    expect(profileStoreMock.ensureProfileLoaded).not.toHaveBeenCalled()
  })
})
