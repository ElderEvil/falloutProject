import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { createIconifyMock } from '../../helpers/mocks'
import { flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { ref } from 'vue'
import FamilyTreePanel from '@/modules/dwellers/components/FamilyTreePanel.vue'
import { useDwellerManagementStore } from '@/modules/dwellers/stores/dwellerManagement'
import {
  createMockDwellerDetailContext,
  mountWithDwellerContext,
} from '../../helpers/dwellerDetailContext'

vi.mock('@iconify/vue', () => createIconifyMock())

const mockLineage = {
  dweller_id: 'self',
  generation: 1,
  parents: [
    {
      id: 'p1',
      first_name: 'Mom',
      last_name: 'Dweller',
      generation: 0,
      is_dead: false,
      age_group: 'adult',
    },
  ],
  children: [
    {
      id: 'c1',
      first_name: 'Kid',
      last_name: 'Dweller',
      generation: 2,
      is_dead: false,
      age_group: 'child',
    },
  ],
  siblings: [
    {
      id: 's1',
      first_name: 'Sib',
      last_name: 'Dweller',
      generation: 1,
      is_dead: false,
      age_group: 'teen',
    },
  ],
  partners: [
    {
      id: 'sp1',
      first_name: 'Spouse',
      last_name: 'Dweller',
      generation: 1,
      is_dead: false,
      age_group: 'adult',
      relationship_type: 'MARRIED',
      affinity: 90,
    },
  ],
}

describe('FamilyTreePanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  const stubStore = (lineage: unknown = mockLineage, reject = false) => {
    const management = useDwellerManagementStore()
    management.fetchLineage = vi.fn(() => Promise.resolve(reject ? null : lineage))
    management.lineage = lineage as never
    management.isLoadingLineage = false
    return management
  }

  const mountPanel = (contextOverrides: Record<string, unknown> = {}) => {
    const ctx = createMockDwellerDetailContext({
      dweller: ref({ id: 'self', first_name: 'Self', last_name: 'Dweller' }) as never,
      dwellerId: ref('self') as never,
      ...contextOverrides,
    })
    const wrapper = mountWithDwellerContext(FamilyTreePanel, {
      context: ctx,
      global: { stubs: { Icon: true } },
    })
    return { wrapper, ctx }
  }

  const withPartner = (relationship_type: string, affinity: number) => ({
    ...mockLineage,
    partners: [{ ...mockLineage.partners[0]!, relationship_type, affinity }],
  })

  it('fetches lineage on mount with the dweller id', () => {
    const management = stubStore()
    mountPanel()

    expect(management.fetchLineage).toHaveBeenCalledWith('self')
  })

  it('renders parents, siblings, partners, and children rows', () => {
    stubStore()
    const { wrapper } = mountPanel()

    expect(wrapper.text()).toContain('Mom')
    expect(wrapper.text()).toContain('Sib')
    expect(wrapper.text()).toContain('Spouse')
    expect(wrapper.text()).toContain('Kid')
    expect(wrapper.text()).toContain('Gen 1')
    expect(wrapper.text()).toContain('MARRIED')
  })

  it.each([
    [
      'a friendly affinity',
      'MARRIED',
      90,
      '90',
      'text-success',
      ['text-danger', 'text-muted-foreground'],
    ],
    ['a rival affinity', 'RIVAL', -40, '-40', 'text-danger', ['text-success']],
    [
      'a zero affinity',
      'PARTNER',
      0,
      '0',
      'text-muted-foreground',
      ['text-success', 'text-danger'],
    ],
  ] as const)(
    'renders %s as a plain number in its tone',
    async (_name, relationship_type, affinity, text, tone, absentTones) => {
      stubStore(withPartner(relationship_type, affinity))
      const { wrapper } = mountPanel()

      const badge = wrapper.get('.bond-affinity')
      expect(badge.text()).toBe(text)
      expect(badge.text()).not.toContain('♥')
      expect(badge.text()).not.toContain('❤')
      expect(badge.get(`.${tone}`).text()).toBe(text)
      for (const absent of absentTones) {
        expect(wrapper.find(`.${absent}`).exists()).toBe(false)
      }
    }
  )

  it('renders the first name without a literal null when the surname is absent', () => {
    stubStore()
    const { wrapper } = mountPanel({
      dweller: ref({ id: 'self', first_name: 'Self', last_name: null }) as never,
    })

    expect(wrapper.find('.tree-node-self').text()).toBe('Self')
  })

  it('marks a dead parent as deceased in text, not only through the skull icon', () => {
    stubStore({ ...mockLineage, parents: [{ ...mockLineage.parents[0]!, is_dead: true }] })
    const { wrapper } = mountPanel()

    const deadNode = wrapper.find('.tree-node-dead')
    expect(deadNode.exists()).toBe(true)
    expect(deadNode.text()).toContain('Mom')
    expect(deadNode.text()).toContain('(deceased)')
  })

  it('calls navigateToDweller with the clicked member id', async () => {
    stubStore()
    const { wrapper, ctx } = mountPanel()

    const nodes = wrapper.findAll('button.tree-node')
    expect(nodes.length).toBeGreaterThanOrEqual(4)

    await nodes[0]!.trigger('click')

    expect(ctx.actions.navigateToDweller).toHaveBeenCalledWith('p1')
  })

  it('shows an error and a retry button when the lineage fetch fails', async () => {
    stubStore(null, true)
    const { wrapper } = mountPanel()

    await flushPromises()

    expect(wrapper.text()).toContain('Failed to load family lineage')
    expect(wrapper.find('.tree-retry').exists()).toBe(true)
  })

  it('shows a message when no lineage data is available', () => {
    stubStore(null)
    const { wrapper } = mountPanel()

    expect(wrapper.text()).toContain('No lineage data')
  })

  it('keeps the self member non-interactive and leads every card with the name', () => {
    stubStore()
    const { wrapper } = mountPanel()

    // Lineage is event-driven: no manual refresh control is offered.
    expect(wrapper.find('.tree-refresh').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Refresh family tree')
    expect(wrapper.find('.member-card-self').element.tagName).toBe('DIV')
    expect(wrapper.find('.tree-node-self').element.tagName).toBe('SPAN')
    expect(wrapper.findAll('button.tree-node').length).toBeGreaterThanOrEqual(4)
    expect(wrapper.find('.member-avatar').exists()).toBe(false)
    expect(wrapper.find('.tree-node .member-name').text()).toBe('Mom Dweller')
    expect(wrapper.find('.member-card-self .tree-node-self').text()).toBe('Self Dweller')
  })
})
