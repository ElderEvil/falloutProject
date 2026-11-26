import { describe, it, expect, beforeEach, afterEach } from 'vite-plus/test'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import AIUsageCard from '@/modules/profile/components/AIUsageCard.vue'
import type { AIOperationStats, AIUsageStats } from '@/modules/profile/models/aiUsage'

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

const createOperation = (overrides: Partial<AIOperationStats> = {}): AIOperationStats => ({
  operation: 'chat_with_dweller',
  prompt_tokens: 300,
  completion_tokens: 150,
  total_tokens: 450,
  count: 3,
  is_operational: false,
  ...overrides,
})

/** Mounts the card for a given quota percentage, deriving the matching used/limit/flags. */
function renderQuota(percentage: number, overrides: Partial<AIUsageStats> = {}): VueWrapper {
  return mount(AIUsageCard, {
    props: {
      stats: createMockStats({
        quota_used: percentage * 1000,
        quota_limit: 100000,
        quota_percentage: percentage,
        quota_warning: percentage >= 80 && percentage < 100,
        quota_exceeded: percentage >= 100,
        ...overrides,
      }),
    },
  })
}

function progressBarsUsing(wrapper: VueWrapper, token: string) {
  return wrapper
    .findAll('[data-slot="progress"]')
    .filter((bar) => ((bar.attributes('style') ?? '') as string).includes(token))
}

describe('AIUsageCard', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
  })

  describe('Quota Progress Display', () => {
    it('uses semantic warm surfaces for statistic insets and the quota track', () => {
      const wrapper = mount(AIUsageCard, { props: { stats: createMockStats() } })
      const statisticInsets = wrapper.findAll('.grid > .bg-surface-sunken')
      const quotaTrack = wrapper.find('.relative.h-6')

      expect(statisticInsets).toHaveLength(2)
      expect(statisticInsets.every((inset) => inset.classes().includes('bg-surface-sunken'))).toBe(
        true
      )
      expect(quotaTrack.classes()).toContain('bg-surface-sunken')
    })

    it.each([
      [50, '50.0K / 100.0K'],
      [75, '75.0K / 100.0K'],
      [120, '120.0K / 100.0K'],
    ])('displays %s%% of quota in the progress bar', (percentage, usageLabel) => {
      const wrapper = renderQuota(percentage)

      expect(wrapper.text()).toContain(`${percentage}%`)
      expect(wrapper.text()).toContain(usageLabel)
    })
  })

  describe('Warning Banner at 80%', () => {
    it('should show warning banner when quota_warning is true', async () => {
      localStorage.setItem('quota_warning_dismissed_2026-01', 'false')

      const wrapper = mount(AIUsageCard, {
        props: {
          stats: createMockStats({
            month: '2026-01',
            quota_used: 80000,
            quota_limit: 100000,
            quota_percentage: 80,
            quota_warning: true,
            quota_exceeded: false,
          }),
        },
      })
      await flushPromises()

      expect(wrapper.text()).toContain("You've used 80% of your monthly token quota")
    })

    it('should show warning indicator below progress bar at 80%', () => {
      const wrapper = renderQuota(80)

      expect(wrapper.text()).toContain('Approaching quota limit')
    })

    it('should not show warning banner when quota_warning is false', () => {
      const wrapper = renderQuota(80, { quota_warning: false })

      expect(wrapper.text()).not.toContain("You've used")
    })
  })

  describe('Blocking Message at 100%', () => {
    it('should show blocking message when quota_exceeded is true', () => {
      const wrapper = renderQuota(100)

      expect(wrapper.text()).toContain('Quota exceeded')
      expect(wrapper.text()).toContain('Some AI features may be limited')
    })

    it('should show exceeded indicator below progress bar at 100%', () => {
      const exceededAlert = renderQuota(100)
        .findAll('.text-danger')
        .find((element) => element.text().includes('Quota exceeded'))

      expect(exceededAlert).toBeDefined()
      expect(exceededAlert!.text()).toContain('Quota exceeded')
    })

    it('should not show blocking message when quota_exceeded is false', () => {
      const wrapper = renderQuota(99)

      expect(wrapper.text()).not.toContain('Quota exceeded')
    })
  })

  describe('Color Changes', () => {
    it.each([
      ['green theme when below 80%', 50, 'var(--color-theme-primary)'],
      ['warning token at 80%', 80, 'var(--color-warning)'],
      ['warning token between 80-99%', 90, 'var(--color-warning)'],
      ['danger token at 100%', 100, 'var(--color-danger)'],
      ['danger token when exceeding 100%', 120, 'var(--color-danger)'],
    ])('uses the %s', (_label, percentage, token) => {
      expect(progressBarsUsing(renderQuota(percentage), token).length).toBeGreaterThan(0)
    })

    it.each([
      ['warning token at 80%', 80, '.text-warning'],
      ['danger token at 100%', 100, '.text-danger'],
    ])('marks the percentage text with the %s', (_label, percentage, selector) => {
      expect(renderQuota(percentage).find(selector).exists()).toBe(true)
    })
  })

  describe('Loading State', () => {
    it('should show skeleton when loading is true', async () => {
      const wrapper = mount(AIUsageCard, { props: { stats: null, loading: true } })
      await flushPromises()

      expect(wrapper.findAll('[data-slot="skeleton"]').length).toBeGreaterThan(0)
    })

    it('should show empty state when stats is null and not loading', () => {
      const wrapper = mount(AIUsageCard, { props: { stats: null, loading: false } })

      expect(wrapper.text()).toContain('No AI usage data available')
    })
  })

  describe('Monthly operation briefing', () => {
    it('presents the monthly mix with text labels, counts, and accessible progress bars', () => {
      const wrapper = mount(AIUsageCard, {
        props: {
          stats: createMockStats({
            by_operation: [
              createOperation(),
              createOperation({
                operation: 'quota_tracking',
                prompt_tokens: 0,
                completion_tokens: 0,
                total_tokens: 300,
                count: 1,
                is_operational: true,
              }),
            ],
          }),
        },
      })

      expect(wrapper.text()).toContain('This Month by Operation')
      expect(wrapper.text()).toContain('Dweller chat')
      expect(wrapper.text()).toContain('3 requests')
      expect(wrapper.text()).not.toContain('quota_tracking')
      expect(wrapper.text()).not.toContain('Other AI activity')
      expect(
        wrapper
          .find('[aria-label="Dweller chat: 450 tokens across 3 requests, 60% of this month"]')
          .exists()
      ).toBe(true)
    })

    it('uses a safe label for unrecognised operations and explains chat-heavy use', () => {
      const wrapper = mount(AIUsageCard, {
        props: {
          stats: createMockStats({
            by_operation: [
              createOperation({
                operation: 'future_operation',
                prompt_tokens: 100,
                completion_tokens: 0,
                total_tokens: 100,
                count: 1,
              }),
            ],
            chat_heavy: true,
          }),
        },
      })

      expect(wrapper.text()).toContain('Other AI activity')
      expect(wrapper.text()).toContain('Most AI use this month is dwelling chat')
    })

    it('does not claim an exceeded quota is available', () => {
      const wrapper = mount(AIUsageCard, {
        props: {
          stats: createMockStats({
            quota_remaining: 0,
            quota_used: 100000,
            quota_exceeded: true,
            chat_heavy: true,
            by_operation: [
              createOperation({
                prompt_tokens: 700,
                completion_tokens: 300,
                total_tokens: 1000,
                count: 2,
              }),
            ],
          }),
        },
      })

      expect(wrapper.text()).toContain('Most AI use this month is dwelling chat')
      expect(wrapper.text()).not.toContain('quota is still available')
      expect(wrapper.find('[aria-label^="Dweller chat:"]').attributes('aria-valuenow')).toBe('100')
    })
  })
})
