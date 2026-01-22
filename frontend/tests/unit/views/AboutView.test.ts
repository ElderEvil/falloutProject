import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import AboutView from '@/modules/profile/views/AboutView.vue'

// Mock the axios client
vi.mock('@/core/plugins/axios', () => ({
  default: {
    get: vi.fn().mockResolvedValue({
      data: {
        app_version: '1.13.7',
        api_version: 'v1',
        environment: 'local',
        python_version: '3.13.1',
        build_date: '2026-01-22T00:00:00+00:00'
      }
    })
  }
}))

// Mock the UI components
vi.mock('@/core/components/ui', () => ({
  UCard: {
    name: 'UCard',
    props: ['title', 'glow', 'crt'],
    template: '<div class="u-card"><h2>{{ title }}</h2><slot /></div>'
  },
  USkeleton: {
    name: 'USkeleton',
    template: '<div class="skeleton"></div>'
  },
  UButton: {
    name: 'UButton',
    props: ['variant', 'size'],
    template: '<button class="u-button"><slot /></button>'
  }
}))

// Mock vue-router
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn()
  })
}))

describe('AboutView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders system information title', async () => {
    const wrapper = mount(AboutView)
    await flushPromises()

    expect(wrapper.text()).toContain('System Information')
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
    const skeletons = wrapper.findAll('.skeleton')
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it('handles API error gracefully', async () => {
    // Override mock for this test
    const axios = await import('@/core/plugins/axios')
    vi.mocked(axios.default.get).mockRejectedValueOnce(new Error('Network error'))

    const wrapper = mount(AboutView)
    await flushPromises()

    expect(wrapper.text()).toContain('Failed to load backend info')
  })
})
