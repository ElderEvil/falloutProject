import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { createIconifyMock, createToastMock } from '../helpers/mocks'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import RelationshipsView from '@/modules/social/views/RelationshipsView.vue'
import { useRelationshipStore } from '@/modules/social/stores/relationship'
import { usePregnancyStore } from '@/modules/social/stores/pregnancy'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'

// Mock Iconify
vi.mock('@iconify/vue', () => createIconifyMock())

// Mock the components
vi.mock('@/core/components/common/SidePanel.vue', () => ({
  default: { template: '<div class="side-panel-mock"></div>' },
}))

vi.mock('@/modules/social/components/relationships/RelationshipList.vue', () => ({
  default: {
    template: '<div class="relationship-list-mock"></div>',
    props: ['vaultId', 'stageFilter'],
  },
}))

vi.mock('@/modules/social/components/pregnancy/PregnancyTracker.vue', () => ({
  default: {
    template: '<div class="pregnancy-tracker-mock"></div>',
    props: ['vaultId', 'autoRefresh'],
  },
}))

vi.mock('@/modules/social/components/relationships/ChildrenList.vue', () => ({
  default: { template: '<div class="children-list-mock"></div>', props: ['vaultId'] },
}))

vi.mock('@/core/composables/useSidePanel', () => ({
  useSidePanel: () => ({ isCollapsed: { value: false } }),
}))

const mockToast = createToastMock()
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => mockToast,
}))

describe('RelationshipsView', () => {
  let router: ReturnType<typeof createRouter>
  let relationshipStore: ReturnType<typeof useRelationshipStore>
  let pregnancyStore: ReturnType<typeof usePregnancyStore>
  let dwellerStore: ReturnType<typeof useDwellerStore>['filter']
  let authStore: ReturnType<typeof useAuthStore>

  const mountView = async (attachTo?: HTMLElement) => {
    const wrapper = mount(RelationshipsView, {
      ...(attachTo ? { attachTo } : {}),
      global: {
        plugins: [router],
        ...(attachTo ? { stubs: { Teleport: { template: '<div><slot /></div>' } } } : {}),
      },
    })
    await flushPromises()
    return wrapper
  }

  beforeEach(async () => {
    setActivePinia(createPinia())
    relationshipStore = useRelationshipStore()
    pregnancyStore = usePregnancyStore()
    dwellerStore = useDwellerStore().filter
    authStore = useAuthStore()

    vi.spyOn(relationshipStore, 'fetchVaultRelationships').mockResolvedValue(undefined)
    vi.spyOn(pregnancyStore, 'fetchVaultPregnancies').mockResolvedValue(undefined)
    vi.spyOn(dwellerStore, 'fetchAllDwellers').mockResolvedValue(undefined)
    vi.spyOn(useVaultStore(), 'ensureVaultLoaded').mockResolvedValue(undefined)

    relationshipStore.relationships = []
    pregnancyStore.pregnancies = []
    relationshipStore.token = 'mock-token'
    dwellerStore.allDwellers = []
    authStore.user = { is_superuser: false } as never
    authStore.token = 'mock-token'

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/vault/:id/relationships', component: RelationshipsView, name: 'relationships' },
        {
          path: '/vault/:id',
          redirect: (to) => ({ name: 'relationships', params: { id: to.params.id } }),
        },
      ],
    })

    router.push('/vault/test-vault-id/relationships')
    await router.isReady()
  })

  it('explains family stages through optional page help without switching tabs', async () => {
    const wrapper = await mountView(document.body)

    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    await vi.waitFor(() =>
      expect(wrapper.find('button[aria-label="About Relationships & Family"]').exists()).toBe(true)
    )
    await wrapper.find('button[aria-label="About Relationships & Family"]').trigger('click')
    await flushPromises()

    const help = wrapper.find('[role="dialog"]')
    expect(help.text()).toContain('sharing Living Quarters')
    expect(help.text()).toContain('conception is not guaranteed')
    expect(help.text()).toContain('youth stages before adulthood')

    await help.find('button').trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="tab"][aria-selected="true"]').text()).toContain('Forming')
    wrapper.unmount()
  })

  it('skips family reads when the session changes during vault adoption', async () => {
    let resolveVault!: () => void
    vi.spyOn(useVaultStore(), 'ensureVaultLoaded').mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveVault = resolve
        })
    )

    const wrapper = await mountView()
    expect(relationshipStore.fetchVaultRelationships).not.toHaveBeenCalled()

    authStore.sessionGeneration++
    resolveVault()
    await flushPromises()

    expect(relationshipStore.fetchVaultRelationships).not.toHaveBeenCalled()
    expect(pregnancyStore.fetchVaultPregnancies).not.toHaveBeenCalled()
    expect(dwellerStore.fetchAllDwellers).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('renders the family header with every tab', async () => {
    const wrapper = await mountView()

    expect(wrapper.text()).toContain('Relationships & Family')
    expect(wrapper.findAll('[role="tab"]')).toHaveLength(5)
    for (const label of ['Forming', 'Tensions', 'Partners', 'Pregnancies', 'Children']) {
      expect(wrapper.text()).toContain(label)
    }
  })

  it('renders the total relationships count in the header', async () => {
    relationshipStore.relationships = [
      {
        id: 'r1',
        dweller_1_id: 'd1',
        dweller_2_id: 'd2',
        relationship_type: 'friend',
        affinity: 50,
      },
    ]

    const wrapper = await mountView()

    expect(wrapper.find('.total-relationships-count .page-header-metric-value').text()).toBe('1')
    expect(wrapper.text()).toContain('relationship')
  })

  describe('Tab switching', () => {
    it.each([
      ['Forming', 0, 'Forming Relationships'],
      ['Tensions', 1, 'Rivals lose production and happiness'],
      ['Partners', 2, 'Committed partners in living quarters'],
      ['Pregnancies', 3, 'Active Pregnancies'],
      ['Children', 4, 'Growing Children'],
    ])('opens the %s panel when its tab is selected', async (label, index, panel) => {
      const wrapper = await mountView()
      const tabs = wrapper.findAll('[role="tab"]')

      if (index > 0) {
        await tabs[index]!.trigger('mousedown')
        await flushPromises()
      }

      expect(tabs[index]!.text()).toContain(label)
      expect(tabs[index]!.attributes('aria-selected')).toBe('true')
      expect(wrapper.text()).toContain(panel)
    })

    it('labels the active panel with its tab', async () => {
      const wrapper = await mountView()
      const tabs = wrapper.findAll('[role="tab"]')

      expect(wrapper.get('[role="tabpanel"]').attributes('aria-labelledby')).toBe(
        tabs[0]!.attributes('id')
      )
    })
  })

  describe('Tab counts', () => {
    it('splits the relationship count between the Forming and Partners tabs', async () => {
      relationshipStore.relationships = [
        { id: '1', relationship_type: 'friend' },
        { id: '2', relationship_type: 'partner' },
        { id: '3', relationship_type: 'rival' },
      ]

      const wrapper = await mountView()

      expect(wrapper.text()).toContain('Forming (1)')
      expect(wrapper.text()).toContain('Tensions (1)')
      expect(wrapper.text()).toContain('Partners (1)')
    })

    it('shows the pregnancy count in the Pregnancies tab', async () => {
      pregnancyStore.pregnancies = [{ id: '1' }, { id: '2' }]

      const wrapper = await mountView()

      expect(wrapper.text()).toContain('Pregnancies (2)')
    })

    it('shows the children count in the Children tab', async () => {
      dwellerStore.allDwellers = [
        { id: '1', age_group: 'child' },
        { id: '2', age_group: 'adult' },
        { id: '3', age_group: 'child' },
      ]

      const wrapper = await mountView()

      expect(wrapper.text()).toContain('Children (2)')
    })
  })

  describe('Data loading', () => {
    it('fetches family data for the routed vault on mount', async () => {
      await mountView()

      expect(relationshipStore.fetchVaultRelationships).toHaveBeenCalledWith('test-vault-id')
      expect(pregnancyStore.fetchVaultPregnancies).toHaveBeenCalledWith('test-vault-id')
      expect(dwellerStore.fetchAllDwellers).toHaveBeenCalledWith('test-vault-id')
    })
  })
})
