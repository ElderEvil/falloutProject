import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import App from '@/App.vue'
import DwellerChatModal from '@/modules/chat/components/DwellerChatModal.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'

// App hosts the global chat modal via the ?chat= query param; without a router
// installed the composables would throw, so stub them for the mount smoke tests.
const routeQuery = reactive<Record<string, string | undefined>>({})
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: routeQuery }),
  useRouter: () => ({ replace: vi.fn() }),
}))

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
vi.mock('@/core/composables/useGaryMode', () => ({
  useGaryMode: () => ({ isGaryMode: ref(false) }),
}))
vi.mock('@/core/composables/useFakeCrash', () => ({
  useFakeCrash: () => ({ isCrashing: ref(false), resetCrash: vi.fn() }),
}))

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeQuery.chat = undefined
  })

  afterEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('mounts without unresolved-component warnings after Nuxt UI removal', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})

    const wrapper = mount(App, {
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
    wrapper.unmount()
  })

  it('loads the profile when authenticated', () => {
    localStorage.setItem('token', 'test-token')

    const wrapper = mount(App, {
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
    wrapper.unmount()
  })

  it('clears the profile when not authenticated', () => {
    const wrapper = mount(App, {
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
    wrapper.unmount()
  })

  it('remounts chat when the query switches directly to another dweller', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useAuthStore().token = 'mock-token'
    const fetchDweller = vi
      .spyOn(useDwellerStore().filter, 'fetchDwellerDetails')
      .mockResolvedValue(null)
    routeQuery.chat = 'dweller-1'
    const wrapper = mount(App, {
      global: {
        plugins: [pinia],
        stubs: {
          DefaultLayout: { template: '<main><slot /></main>' },
          GaryOverlay: true,
          FakeCrashOverlay: true,
          'router-view': true,
        },
      },
    })
    await flushPromises()
    const firstChat = wrapper.findComponent(DwellerChatModal)
    expect(firstChat.exists()).toBe(true)
    expect(fetchDweller).toHaveBeenCalledWith('dweller-1', 'mock-token')

    routeQuery.chat = 'dweller-2'
    await flushPromises()

    const secondChat = wrapper.findComponent(DwellerChatModal)
    expect(secondChat.props('dwellerId')).toBe('dweller-2')
    expect(fetchDweller).toHaveBeenCalledWith('dweller-2', 'mock-token')
    wrapper.unmount()
  })
})
