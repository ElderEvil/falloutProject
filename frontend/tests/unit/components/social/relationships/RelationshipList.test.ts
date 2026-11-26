import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
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

const relationship = (overrides: Record<string, unknown> = {}) => ({
  id: 'r1',
  dweller_1_id: 'd1',
  dweller_2_id: 'd2',
  relationship_type: 'friend',
  affinity: 50,
  ...overrides,
})

function mountList(props: Record<string, unknown> = {}) {
  return mount(RelationshipList, {
    props: { vaultId: 'v1', ...props },
    global: {
      stubs: {
        Teleport: { template: '<div><slot /></div>' },
        TerminalEmptyState: { template: '<div class="empty-stub" />' },
      },
    },
  })
}

const cards = (wrapper: ReturnType<typeof mount>) =>
  wrapper.findAllComponents({ name: 'RelationshipCard' })

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
    relationships.push(relationship())

    const wrapper = mountList()
    await flushPromises()

    expect(cards(wrapper)).toHaveLength(1)
    expect(cards(wrapper)[0].props('dweller1')).toEqual(dweller1)
    expect(cards(wrapper)[0].props('dweller2')).toEqual(dweller2)
    expect(wrapper.text()).not.toContain('Refresh')
  })

  it.each([
    ['neither dweller has loaded', []],
    ['only one dweller resolved', [{ ...dweller1 }]],
  ])('omits a relationship when %s', async (_name, loaded) => {
    allDwellers.push(...loaded)
    relationships.push(relationship())

    const wrapper = mountList()
    await flushPromises()

    expect(cards(wrapper)).toHaveLength(0)
  })

  it('shows only rival pairs in the tensions filter', async () => {
    allDwellers.push(dweller1, dweller2, { id: 'd3', first_name: 'Cara' }, { id: 'd4' })
    relationships.push(
      relationship({ relationship_type: 'rival', affinity: -30 }),
      relationship({
        id: 'r2',
        dweller_1_id: 'd3',
        dweller_2_id: 'd4',
        affinity: 20,
      })
    )

    const wrapper = mountList({ stageFilter: 'tensions' })
    await flushPromises()

    expect(cards(wrapper)).toHaveLength(1)
    expect(cards(wrapper)[0].props('relationship')).toMatchObject({
      id: 'r1',
      relationship_type: 'rival',
      affinity: -30,
    })
  })

  it('forwards select-dweller events from the card', async () => {
    allDwellers.push(dweller1, dweller2)
    relationships.push(relationship())

    const wrapper = mountList()
    await flushPromises()

    cards(wrapper)[0].vm.$emit('select-dweller', 'd1')

    expect(wrapper.emitted('select-dweller')).toEqual([['d1']])
  })

  it('waits for a themed confirmation and supports canceling a breakup', async () => {
    allDwellers.push(dweller1, dweller2)
    relationships.push(relationship({ relationship_type: 'partner' }))
    const nativeConfirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const wrapper = mountList()
    await flushPromises()

    const request = async () => {
      cards(wrapper)[0].vm.$emit('break-up')
      await flushPromises()
    }
    const button = (text: string) => wrapper.findAll('button').find((item) => item.text() === text)!

    await request()
    expect(nativeConfirm).not.toHaveBeenCalled()
    expect(breakUp).not.toHaveBeenCalled()
    expect(wrapper.get('[role="dialog"]').text()).toContain('End relationship?')

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
