import { describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import App from '@/App.vue'

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
    warn.mockRestore()
  })
})
