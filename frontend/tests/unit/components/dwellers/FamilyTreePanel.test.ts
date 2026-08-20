import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import FamilyTreePanel from '@/modules/dwellers/components/FamilyTreePanel.vue'
import { useDwellerManagementStore } from '@/modules/dwellers/stores/dwellerManagement'

vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon'],
  },
}))

const mockLineage = {
  dweller_id: 'self',
  generation: 1,
  parents: [{ id: 'p1', first_name: 'Mom', last_name: 'Dweller', generation: 0, is_dead: false, age_group: 'adult' }],
  children: [{ id: 'c1', first_name: 'Kid', last_name: 'Dweller', generation: 2, is_dead: false, age_group: 'child' }],
  siblings: [{ id: 's1', first_name: 'Sib', last_name: 'Dweller', generation: 1, is_dead: false, age_group: 'teen' }],
  partners: [
    { id: 'sp1', first_name: 'Spouse', last_name: 'Dweller', generation: 1, is_dead: false, age_group: 'adult', relationship_type: 'MARRIED', affinity: 90 },
  ],
}

describe('FamilyTreePanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  function stubStore(lineage: unknown = mockLineage, reject = false) {
    const management = useDwellerManagementStore()
    management.fetchLineage = vi.fn(() => (reject ? Promise.resolve(null) : Promise.resolve(lineage)))
    management.lineage = lineage as never
    management.isLoadingLineage = false
    return management
  }

  function mountPanel(props: Record<string, unknown> = {}) {
    return mount(FamilyTreePanel, {
      props: { dwellerId: 'self', dwellerName: 'Self Dweller', ...props },
      global: {
        stubs: {
          Icon: true,
        },
      },
    })
  }

  it('fetches lineage on mount with the dweller id', () => {
    const management = stubStore()
    mount(FamilyTreePanel, { props: { dwellerId: 'self' }, global: { stubs: { Icon: true } } })

    expect(management.fetchLineage).toHaveBeenCalledWith('self')
  })

  it('renders parents, siblings, partners, and children rows', () => {
    stubStore()
    const wrapper = mountPanel()

    expect(wrapper.text()).toContain('Mom')
    expect(wrapper.text()).toContain('Sib')
    expect(wrapper.text()).toContain('Spouse')
    expect(wrapper.text()).toContain('Kid')
    expect(wrapper.text()).toContain('Gen 1')
  })

  it('shows the partner stage badge and affinity', () => {
    stubStore()
    const wrapper = mountPanel()

    expect(wrapper.text()).toContain('MARRIED')
    expect(wrapper.text()).toContain('90')
  })

  it('applies dead styling to a dead parent', () => {
    const lineage = {
      ...mockLineage,
      parents: [{ ...mockLineage.parents[0]!, is_dead: true }],
    }
    stubStore(lineage)
    const wrapper = mountPanel()

    const deadNode = wrapper.find('.tree-node-dead')
    expect(deadNode.exists()).toBe(true)
    expect(deadNode.text()).toContain('Mom')
  })

  it('emits select with the clicked member id', async () => {
    stubStore()
    const wrapper = mountPanel()

    const nodes = wrapper.findAll('button.tree-node')
    expect(nodes.length).toBeGreaterThanOrEqual(4)

    await nodes[0]!.trigger('click')
    const emitted = wrapper.emitted('select')
    expect(emitted).toBeTruthy()
    expect((emitted as unknown[])[0][0]).toBe('p1')
  })

  it('shows an error and a retry button when the lineage fetch fails', async () => {
    stubStore(null, true)
    const wrapper = mountPanel()

    await flushPromises()
    expect(wrapper.text()).toContain('Failed to load family lineage')

    const retry = wrapper.find('.tree-retry')
    expect(retry.exists()).toBe(true)
  })

  it('shows a message when no lineage data is available', () => {
    stubStore(null)
    const wrapper = mountPanel()

    expect(wrapper.text()).toContain('No lineage data')
  })
})
