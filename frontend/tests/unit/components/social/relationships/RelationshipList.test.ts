import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import RelationshipList from '@/modules/social/components/relationships/RelationshipList.vue'

vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon'],
  },
}))

const { relationships, pregnancies, fetchVaultRelationships } = vi.hoisted(() => ({
  relationships: [] as Record<string, unknown>[],
  pregnancies: [] as Record<string, unknown>[],
  fetchVaultRelationships: vi.fn(),
}))

vi.mock('@/modules/social/stores/relationship', () => ({
  useRelationshipStore: () => ({
    relationships,
    pregnancies,
    isLoading: false,
    fetchVaultRelationships,
    initiateRomance: vi.fn(),
    makePartners: vi.fn(),
    marry: vi.fn(),
    breakUp: vi.fn(),
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
    props: ['relationship', 'dweller1', 'dweller2', 'children', 'pregnancy', 'generation', 'viewMode'],
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
        UButton: { template: '<button class="ubutton-stub"><slot /></button>' },
        UCard: { template: '<div class="ucard-stub"><slot /></div>' },
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
})