import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AboutView from '@/modules/profile/views/AboutView.vue'
import { useVaultStore } from '@/modules/vault/stores/vault'

// Mock the axios client
vi.mock('@/core/plugins/axios', () => ({
  default: {
    get: vi.fn().mockResolvedValue({
      data: {
        app_version: '1.13.7',
        api_version: 'v1',
        environment: 'local',
        python_version: '3.13.1',
        build_date: '2026-01-22T00:00:00+00:00',
      },
    }),
  },
}))

// Mock vue-router
vi.mock('vue-router', () => ({
  RouterLink: { template: '<a><slot /></a>' },
  useRoute: () => ({ path: '/about', params: {}, meta: {} }),
  useRouter: () => ({
    push: vi.fn(),
  }),
}))

describe('AboutView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('offers navigation back to sections of the loaded vault', async () => {
    useVaultStore().activeVaultId = 'vault-123'

    const wrapper = mount(AboutView)
    await flushPromises()

    expect(wrapper.find('[aria-label="Dwellers 2"]').exists()).toBe(true)
  })

  it('keeps the vault sidebar after a refresh (persisted selection, no active vault)', async () => {
    useVaultStore().selectedVaultId = 'vault-123'

    const wrapper = mount(AboutView)
    await flushPromises()

    expect(wrapper.find('[aria-label="Game navigation panel"]').exists()).toBe(true)
  })

  it('does not show an empty vault sidebar without a loaded vault', async () => {
    const wrapper = mount(AboutView)
    await flushPromises()

    expect(wrapper.find('[aria-label="Game navigation panel"]').exists()).toBe(false)
  })

  it('renders the about title', async () => {
    const wrapper = mount(AboutView)
    await flushPromises()

    expect(wrapper.text()).toContain('About Fallout Shelter')
  })

  it('displays frontend version info', async () => {
    const wrapper = mount(AboutView)
    await flushPromises()

    expect(wrapper.text()).toContain('Frontend')
    expect(wrapper.text()).toContain('Vue 3.5')
    expect(wrapper.text()).toContain('Vite (Rolldown)')
  })

  it('displays backend version info after loading', async () => {
    const wrapper = mount(AboutView)
    await flushPromises()

    expect(wrapper.text()).toContain('Backend')
    expect(wrapper.text()).toContain('1.13.7')
    expect(wrapper.text()).toContain('v1')
    expect(wrapper.text()).toContain('local')
    expect(wrapper.text()).toContain('3.13.1')
  })

  it('displays project info with GitHub link', async () => {
    const wrapper = mount(AboutView)
    await flushPromises()

    expect(wrapper.text()).toContain('Project')
    expect(wrapper.text()).toContain('Fallout Shelter')

    const githubLink = wrapper.find('a[href="https://github.com/ElderEvil/falloutProject"]')
    expect(githubLink.exists()).toBe(true)
    expect(githubLink.text()).toBe('GitHub')
  })

  it('shows loading skeletons initially', () => {
    const wrapper = mount(AboutView)

    // Before flushPromises, should show loading state
    const skeletons = wrapper.findAll('[data-slot="skeleton"]')
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it('handles API error gracefully', async () => {
    // Override mock for this test
    const axios = await import('@/core/plugins/axios')
    vi.mocked(axios.default.get).mockRejectedValueOnce(new Error('Network error'))

    const wrapper = mount(AboutView)
    await flushPromises()

    expect(wrapper.text()).toContain('Failed to load backend info')
    expect(wrapper.text()).toContain('Frontend')
    expect(wrapper.find('a[href="https://github.com/ElderEvil/falloutProject"]').exists()).toBe(
      true
    )
  })
})
