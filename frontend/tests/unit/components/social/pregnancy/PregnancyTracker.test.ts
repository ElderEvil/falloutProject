import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import PregnancyTracker from '@/modules/social/components/pregnancy/PregnancyTracker.vue'

vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon'],
  },
}))

const {
  activePregnancies,
  allDwellers,
  dwellers,
  fetchVaultPregnancies,
  deliverBaby,
  fetchDwellersByVault,
} = vi.hoisted(() => ({
  activePregnancies: [] as Record<string, unknown>[],
  allDwellers: [] as Record<string, unknown>[],
  dwellers: [] as Record<string, unknown>[],
  fetchVaultPregnancies: vi.fn(),
  deliverBaby: vi.fn(),
  fetchDwellersByVault: vi.fn(),
}))

vi.mock('@/modules/social/stores/pregnancy', () => ({
  usePregnancyStore: () => ({
    activePregnancies,
    isLoading: false,
    fetchVaultPregnancies,
    deliverBaby,
    formatTimeRemaining: (seconds: number) => `${seconds}s`,
  }),
}))

vi.mock('@/modules/dwellers/stores/dweller', () => ({
  useDwellerStore: () => ({
    filter: {
      allDwellers,
      dwellers,
      fetchDwellersByVault,
    },
  }),
}))

vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({ token: 'mock-token' }),
}))

vi.mock('@/core/composables/usePolling', () => ({
  usePolling: () => ({ pause: vi.fn() }),
}))

vi.mock('@/modules/social/components/pregnancy/PregnancyCard.vue', () => ({
  default: {
    name: 'PregnancyCard',
    template: '<div class="pregnancy-card-stub" />',
    props: ['pregnancy', 'mother', 'father', 'isDelivering'],
  },
}))

function mountTracker() {
  return mount(PregnancyTracker, {
    props: { vaultId: 'v1', autoRefresh: false },
    global: {
      stubs: {
        UButton: { template: '<button class="ubutton-stub"><slot /></button>' },
        UBadge: { template: '<span class="ubadge-stub"><slot /></span>' },
        UCard: { template: '<div class="ucard-stub"><slot /></div>' },
      },
    },
  })
}

describe('PregnancyTracker', () => {
  beforeEach(() => {
    activePregnancies.length = 0
    allDwellers.length = 0
    dwellers.length = 0
    fetchVaultPregnancies.mockReset()
    deliverBaby.mockReset()
    fetchDwellersByVault.mockReset()
  })

  it('resolves parent dwellers from allDwellers and passes objects to PregnancyCard', async () => {
    allDwellers.push(
      { id: 'm1', first_name: 'Alice', last_name: 'Smith' },
      { id: 'f1', first_name: 'Bob', last_name: 'Jones' }
    )
    activePregnancies.push({
      id: 'p1',
      mother_id: 'm1',
      father_id: 'f1',
      status: 'pregnant',
      progress_percentage: 50,
      time_remaining_seconds: 5400,
      is_due: false,
    })
    fetchVaultPregnancies.mockResolvedValue(undefined)

    const wrapper = mountTracker()
    await flushPromises()

    const card = wrapper.findComponent({ name: 'PregnancyCard' })
    expect(card.exists()).toBe(true)
    expect(card.props('mother')).toEqual({ id: 'm1', first_name: 'Alice', last_name: 'Smith' })
    expect(card.props('father')).toEqual({ id: 'f1', first_name: 'Bob', last_name: 'Jones' })
  })

  it('falls back to dwellers when allDwellers is empty', async () => {
    dwellers.push({ id: 'm1', first_name: 'Alice', last_name: 'Smith' })
    activePregnancies.push({
      id: 'p1',
      mother_id: 'm1',
      father_id: 'f1',
      status: 'pregnant',
      progress_percentage: 50,
      time_remaining_seconds: 5400,
      is_due: false,
    })
    fetchVaultPregnancies.mockResolvedValue(undefined)

    const wrapper = mountTracker()
    await flushPromises()

    const card = wrapper.findComponent({ name: 'PregnancyCard' })
    expect(card.props('mother')).toEqual({ id: 'm1', first_name: 'Alice', last_name: 'Smith' })
  })

  it('fetches vault pregnancies on mount', async () => {
    fetchVaultPregnancies.mockResolvedValue(undefined)

    mountTracker()
    await flushPromises()

    expect(fetchVaultPregnancies).toHaveBeenCalledWith('v1')
  })
})