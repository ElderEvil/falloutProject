import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import AIUsageCard from '@/modules/profile/components/AIUsageCard.vue'
import type { AIUsageStats } from '@/modules/profile/models/aiUsage'

vi.mock('vue-router', () => ({
  RouterLink: {
    name: 'RouterLink',
    template: '<a><slot /></a>',
  },
  useRouter: () => ({
    push: vi.fn(),
  }),
}))

const localStorageMock = (() => {
  let store: Record<string, string> = {}

  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value.toString()
    },
    removeItem: (key: string) => {
      delete store[key]
    },
    clear: () => {
      store = {}
    },
  }
})()

Object.defineProperty(global, 'localStorage', {
  value: localStorageMock,
  configurable: true,
  writable: true,
})

describe('AIUsageCard', () => {
  const createMockStats = (overrides: Partial<AIUsageStats> = {}): AIUsageStats => ({
    all_time: {
      prompt_tokens: 1000,
      completion_tokens: 500,
      total_tokens: 1500,
    },
    current_month: {
      prompt_tokens: 500,
      completion_tokens: 250,
      total_tokens: 750,
    },
    month: 'January 2026',
    quota_limit: 100000,
    quota_used: 0,
    quota_remaining: 100000,
    quota_percentage: 0,
    quota_warning: false,
    quota_exceeded: false,
    reset_date: '2026-02-01',
    ...overrides,
  })

  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
  })

  describe('Quota Progress Display', () => {
    it('should display correct percentage in progress bar at 50%', () => {
      const stats = createMockStats({
        quota_used: 50000,
        quota_limit: 100000,
        quota_percentage: 50,
        quota_warning: false,
        quota_exceeded: false,
      })

      const wrapper = mount(AIUsageCard, {
        props: { stats },
      })

      expect(wrapper.text()).toContain('50%')
      expect(wrapper.text()).toContain('50.0K / 100.0K')
    })

    it('should display correct percentage in progress bar at 75%', () => {
      const stats = createMockStats({
        quota_used: 75000,
        quota_limit: 100000,
        quota_percentage: 75,
        quota_warning: false,
        quota_exceeded: false,
      })

      const wrapper = mount(AIUsageCard, {
        props: { stats },
      })

      expect(wrapper.text()).toContain('75%')
    })

    it('should cap progress bar at 100% width even when exceeded', () => {
      const stats = createMockStats({
        quota_used: 120000,
        quota_limit: 100000,
        quota_percentage: 120,
        quota_warning: false,
        quota_exceeded: true,
      })

      const wrapper = mount(AIUsageCard, {
        props: { stats },
      })

      expect(wrapper.text()).toContain('120%')
    })
  })

  describe('Warning Banner at 80%', () => {
    it('should show warning banner when quota_warning is true', async () => {
      const stats = createMockStats({
        month: '2026-01',
        quota_used: 80000,
        quota_limit: 100000,
        quota_percentage: 80,
        quota_warning: true,
        quota_exceeded: false,
      })

      localStorage.setItem('quota_warning_dismissed_2026-01', 'false')

      const wrapper = mount(AIUsageCard, {
        props: { stats },
      })
      await flushPromises()

      expect(wrapper.text()).toContain("You've used 80% of your monthly token quota")
    })

    it('should show warning indicator below progress bar at 80%', () => {
      const stats = createMockStats({
        quota_used: 80000,
        quota_limit: 100000,
        quota_percentage: 80,
        quota_warning: true,
        quota_exceeded: false,
      })

      const wrapper = mount(AIUsageCard, {
        props: { stats },
      })

      expect(wrapper.text()).toContain('Approaching quota limit')
    })

    it('should not show warning banner when quota_warning is false', () => {
      const stats = createMockStats({
        quota_used: 80000,
        quota_limit: 100000,
        quota_percentage: 80,
        quota_warning: false,
        quota_exceeded: false,
      })

      const wrapper = mount(AIUsageCard, {
        props: { stats },
      })

      expect(wrapper.text()).not.toContain("You've used")
    })
  })

  describe('Blocking Message at 100%', () => {
    it('should show blocking message when quota_exceeded is true', () => {
      const stats = createMockStats({
        quota_used: 100000,
        quota_limit: 100000,
        quota_percentage: 100,
        quota_warning: false,
        quota_exceeded: true,
      })

      const wrapper = mount(AIUsageCard, {
        props: { stats },
      })

      expect(wrapper.text()).toContain('Quota exceeded')
      expect(wrapper.text()).toContain('Some AI features may be limited')
    })

    it('should show exceeded indicator below progress bar at 100%', () => {
      const stats = createMockStats({
        quota_used: 100000,
        quota_limit: 100000,
        quota_percentage: 100,
        quota_warning: false,
        quota_exceeded: true,
      })

      const wrapper = mount(AIUsageCard, {
        props: { stats },
      })

      const exceededAlert = wrapper.find('.text-red-400')
      expect(exceededAlert.exists()).toBe(true)
      expect(exceededAlert.text()).toContain('Quota exceeded')
    })

    it('should not show blocking message when quota_exceeded is false', () => {
      const stats = createMockStats({
        quota_used: 99000,
        quota_limit: 100000,
        quota_percentage: 99,
        quota_warning: true,
        quota_exceeded: false,
      })

      const wrapper = mount(AIUsageCard, {
        props: { stats },
      })

      expect(wrapper.text()).not.toContain('Quota exceeded')
    })
  })

  describe('Color Changes', () => {
    it('should use green theme color when below 80%', () => {
      const stats = createMockStats({
        quota_used: 50000,
        quota_limit: 100000,
        quota_percentage: 50,
        quota_warning: false,
        quota_exceeded: false,
      })

      const wrapper = mount(AIUsageCard, {
        props: { stats },
      })

      const progressBar = wrapper.find('.bg-theme-primary')
      expect(progressBar.exists()).toBe(true)
    })

    it('should use amber color at 80%', () => {
      const stats = createMockStats({
        quota_used: 80000,
        quota_limit: 100000,
        quota_percentage: 80,
        quota_warning: true,
        quota_exceeded: false,
      })

      const wrapper = mount(AIUsageCard, {
        props: { stats },
      })

      const progressBar = wrapper.find('.bg-amber-500')
      expect(progressBar.exists()).toBe(true)

      const percentageText = wrapper.find('.text-amber-500')
      expect(percentageText.exists()).toBe(true)
    })

    it('should use amber color between 80-99%', () => {
      const stats = createMockStats({
        quota_used: 90000,
        quota_limit: 100000,
        quota_percentage: 90,
        quota_warning: true,
        quota_exceeded: false,
      })

      const wrapper = mount(AIUsageCard, {
        props: { stats },
      })

      const progressBar = wrapper.find('.bg-amber-500')
      expect(progressBar.exists()).toBe(true)
    })

    it('should use red color at 100%', () => {
      const stats = createMockStats({
        quota_used: 100000,
        quota_limit: 100000,
        quota_percentage: 100,
        quota_warning: false,
        quota_exceeded: true,
      })

      const wrapper = mount(AIUsageCard, {
        props: { stats },
      })

      const progressBar = wrapper.find('.bg-red-500')
      expect(progressBar.exists()).toBe(true)

      const percentageText = wrapper.find('.text-red-500')
      expect(percentageText.exists()).toBe(true)
    })

    it('should use red color when exceeding 100%', () => {
      const stats = createMockStats({
        quota_used: 120000,
        quota_limit: 100000,
        quota_percentage: 120,
        quota_warning: false,
        quota_exceeded: true,
      })

      const wrapper = mount(AIUsageCard, {
        props: { stats },
      })

      const progressBar = wrapper.find('.bg-red-500')
      expect(progressBar.exists()).toBe(true)
    })
  })

  describe('Loading State', () => {
    it('should show skeleton when loading is true', async () => {
      const wrapper = mount(AIUsageCard, {
        props: {
          stats: null,
          loading: true,
        },
      })
      await flushPromises()

      const skeletons = wrapper.findAll('.skeleton')
      expect(skeletons.length).toBeGreaterThan(0)
    })

    it('should show empty state when stats is null and not loading', () => {
      const wrapper = mount(AIUsageCard, {
        props: {
          stats: null,
          loading: false,
        },
      })

      expect(wrapper.text()).toContain('No AI usage data available')
    })
  })
})
