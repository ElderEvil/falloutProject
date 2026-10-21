import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createIconifyMock } from '../../../helpers/mocks'
import { mount, flushPromises } from '@vue/test-utils'
import RelationshipList from '@/modules/social/components/relationships/RelationshipList.vue'

vi.mock('@iconify/vue', () => createIconifyMock())

const { relationships, pregnancies, fetchVaultRelationships, breakUp } = vi.hoisted(() => ({
  breakUp: vi.fn(),
  relationships: [] as Record<string, unknown>[],
  pregnancies: [] as Record<string, unknown>[],
  fetchVaultRelationships: vi.fn(),
}))

vi.mock('@/modules/social/stores/relationship', () => ({
  useRelationshipStore: () => ({
    relationships,
    isLoading: false,
    fetchVaultRelationships,
    initiateRomance: vi.fn(),
    makePartners: vi.fn(),
    marry: vi.fn(),
    breakUp,
  }),
}))

vi.mock('@/modules/social/stores/pregnancy', () => ({
  usePregnancyStore: () => ({
    pregnancies,
  }),
}))

const { allDwellers, dwellers } = vi.hoisted(() => ({
  allDwellers: [] as Record<string, unknown>[],
  dwellers: [] as Record<string, unknown>[],
}))

vi.mock('@/modules/dwellers/stores/dweller', () => ({
  useDwellerStore: () => ({
    filter: { allDwellers, dwellers },
  }),
}))

vi.mock('@/modules/social/components/relationships/RelationshipCard.vue', () => ({
  default: {
    name: 'RelationshipCard',
    template: '<div class="relationship-card-stub" />',
    props: ['relationship', 'dweller1', 'dweller2', 'children', 'pregnancy', 'generation'],
    emits: ['select-dweller', 'initiate-romance', 'make-partners', 'marry', 'break-up'],
  },
}))

const dweller1 = { id: 'd1', first_name: 'Alice', last_name: 'Smith' }
const dweller2 = { id: 'd2', first_name: 'Bob', last_name: 'Jones' }

function mountList() {
  return mount(RelationshipList, {
    props: { vaultId: 'v1' },
    global: {
      stubs: {
        Teleport: { template: '<div><slot /></div>' },
        TerminalEmptyState: { template: '<div class="empty-stub" />' },
      },
    },
  })
}

describe('RelationshipList', () => {
  beforeEach(() => {
    relationships.length = 0
    pregnancies.length = 0
    allDwellers.length = 0
    dwellers.length = 0
    fetchVaultRelationships.mockReset()
    fetchVaultRelationships.mockResolvedValue(undefined)
    breakUp.mockReset().mockResolvedValue(true)
  })

  it('renders a card only when both dwellers resolve', async () => {
    allDwellers.push({ ...dweller1 }, { ...dweller2 })
    relationships.push({
      id: 'r1',
      dweller_1_id: 'd1',
      dweller_2_id: 'd2',
      relationship_type: 'friend',
      affinity: 50,
    })

    const wrapper = mountList()
    await flushPromises()

    const cards = wrapper.findAllComponents({ name: 'RelationshipCard' })
    expect(cards).toHaveLength(1)
    expect(cards[0].props('dweller1')).toEqual(dweller1)
    expect(cards[0].props('dweller2')).toEqual(dweller2)
    expect(wrapper.text()).not.toContain('Refresh')
  })

  it('omits relationships whose dwellers are not loaded yet', async () => {
    relationships.push({
      id: 'r1',
      dweller_1_id: 'd1',
      dweller_2_id: 'd2',
      relationship_type: 'friend',
      affinity: 50,
    })

    const wrapper = mountList()
    await flushPromises()

    expect(wrapper.findAllComponents({ name: 'RelationshipCard' })).toHaveLength(0)
  })

  it('omits a relationship when only one dweller resolves', async () => {
    allDwellers.push({ ...dweller1 })
    relationships.push({
      id: 'r1',
      dweller_1_id: 'd1',
      dweller_2_id: 'd2',
      relationship_type: 'friend',
      affinity: 50,
    })

    const wrapper = mountList()
    await flushPromises()

    expect(wrapper.findAllComponents({ name: 'RelationshipCard' })).toHaveLength(0)
  })

  it('forwards select-dweller events from the card', async () => {
    allDwellers.push({ ...dweller1 }, { ...dweller2 })
    relationships.push({
      id: 'r1',
      dweller_1_id: 'd1',
      dweller_2_id: 'd2',
      relationship_type: 'friend',
      affinity: 50,
    })

    const wrapper = mountList()
    await flushPromises()

    const card = wrapper.findComponent({ name: 'RelationshipCard' })
    card.vm.$emit('select-dweller', 'd1')

    expect(wrapper.emitted('select-dweller')).toEqual([['d1']])
  })

  it('waits for a themed confirmation and supports canceling a breakup', async () => {
    allDwellers.push({ ...dweller1 }, { ...dweller2 })
    relationships.push({
      id: 'r1',
      dweller_1_id: 'd1',
      dweller_2_id: 'd2',
      relationship_type: 'partner',
    })
    const nativeConfirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const wrapper = mountList()
    await flushPromises()
    const request = async () => {
      wrapper.findComponent({ name: 'RelationshipCard' }).vm.$emit('break-up')
      await flushPromises()
    }
    await request()
    expect(nativeConfirm).not.toHaveBeenCalled()
    expect(breakUp).not.toHaveBeenCalled()
    expect(wrapper.get('[role="dialog"]').text()).toContain('End relationship?')
    const button = (text: string) => wrapper.findAll('button').find((item) => item.text() === text)!
    await button('Cancel').trigger('click')
    await flushPromises()
    expect(breakUp).not.toHaveBeenCalled()
    await request()
    await button('End relationship').trigger('click')
    await flushPromises()
    expect(breakUp).toHaveBeenCalledExactlyOnceWith('r1')
    wrapper.unmount()
    nativeConfirm.mockRestore()
  })
})
