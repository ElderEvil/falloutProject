import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import RelationshipsView from '@/modules/social/views/RelationshipsView.vue'
import { useRelationshipStore } from '@/modules/social/stores/relationship'
import { usePregnancyStore } from '@/modules/social/stores/pregnancy'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'

// Mock Iconify
vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon'],
  },
}))

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

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    info: vi.fn(),
    error: vi.fn(),
  }),
}))

describe('RelationshipsView', () => {
  let router: any
  let relationshipStore: any
  let pregnancyStore: any
  let dwellerStore: any
  let authStore: any

  beforeEach(async () => {
    setActivePinia(createPinia())
    relationshipStore = useRelationshipStore()
    pregnancyStore = usePregnancyStore()
    dwellerStore = useDwellerStore().filter
    authStore = useAuthStore()

    // Mock store methods
    vi.spyOn(relationshipStore, 'fetchVaultRelationships').mockResolvedValue(undefined)
    vi.spyOn(pregnancyStore, 'fetchVaultPregnancies').mockResolvedValue(undefined)
    vi.spyOn(dwellerStore, 'fetchAllDwellers').mockResolvedValue(undefined)

    // Set up mock data
    relationshipStore.relationships = []
    pregnancyStore.pregnancies = []
    relationshipStore.token = 'mock-token'
    dwellerStore.allDwellers = []
    authStore.user = { is_superuser: false } as any
    authStore.token = 'mock-token'

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/vault/:id/relationships',
          component: RelationshipsView,
          name: 'relationships',
        },
        {
          path: '/vault/:id',
          redirect: (to) => ({ name: 'relationships', params: { id: to.params.id } }),
        },
      ],
    })

    router.push('/vault/test-vault-id/relationships')
    await router.isReady()
  })

  describe('Rendering', () => {
    it('should render relationships view with header', async () => {
      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      expect(wrapper.text()).toContain('Relationships & Family')
      expect(wrapper.find('.main-content > div').classes()).toContain('max-w-[1400px]')
    })

    it('should render all four tabs', async () => {
      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      expect(wrapper.text()).toContain('Forming')
      expect(wrapper.text()).toContain('Partners')
      expect(wrapper.text()).toContain('Pregnancies')
      expect(wrapper.text()).toContain('Children')
    })

    it('should render the total relationships count in the header', async () => {
      relationshipStore.relationships = [
        { id: 'r1', dweller_1_id: 'd1', dweller_2_id: 'd2', relationship_type: 'friend', affinity: 50 },
      ]

      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      expect(wrapper.find('.total-relationships-count').text()).toBe('1')
      expect(wrapper.text()).toContain('relationship')
    })

    it('should have terminal-style tab styling', async () => {
      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      const tabs = wrapper.findAll('[role="tab"]')
      expect(tabs.length).toBe(4)

      // Check that first tab is active by default
      expect(tabs[0].attributes('aria-selected')).toBe('true')
    })
  })

  describe('Tab Switching', () => {
    it('should switch to partners tab when clicked', async () => {
      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      const tabs = wrapper.findAll('[role="tab"]')
      await tabs[1].trigger('mousedown')

      await flushPromises()

      expect(tabs[1].attributes('aria-selected')).toBe('true')
      expect(wrapper.text()).toContain('Partner Couples')
    })

    it('should switch to pregnancies tab when clicked', async () => {
      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      const tabs = wrapper.findAll('[role="tab"]')
      await tabs[2].trigger('mousedown')

      await flushPromises()

      expect(tabs[2].attributes('aria-selected')).toBe('true')
      expect(wrapper.text()).toContain('Active Pregnancies')
    })

    it('should switch to children tab when clicked', async () => {
      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      const tabs = wrapper.findAll('[role="tab"]')
      await tabs[3].trigger('mousedown')

      await flushPromises()

      expect(tabs[3].attributes('aria-selected')).toBe('true')
      expect(wrapper.text()).toContain('Growing Children')
    })

    it('should display correct content for each tab', async () => {
      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      // Forming tab (default)
      expect(wrapper.text()).toContain('Forming Relationships')

      // Switch to partners
      const tabs = wrapper.findAll('[role="tab"]')
      await tabs[1].trigger('mousedown')
      await flushPromises()
      expect(wrapper.text()).toContain('Committed partners in living quarters')
    })
  })

  describe('Tab counts', () => {
    it('should split the relationship count between the Forming and Partners tabs', async () => {
      relationshipStore.relationships = [
        { id: '1', relationship_type: 'friend' },
        { id: '2', relationship_type: 'partner' },
      ]

      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      expect(wrapper.text()).toContain('Forming (1)')
      expect(wrapper.text()).toContain('Partners (1)')
    })

    it('should display the pregnancy count in the Pregnancies tab', async () => {
      pregnancyStore.pregnancies = [{ id: '1' }, { id: '2' }]

      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      expect(wrapper.text()).toContain('Pregnancies (2)')
    })

    it('should display the children count in the Children tab', async () => {
      dwellerStore.allDwellers = [
        { id: '1', age_group: 'child' },
        { id: '2', age_group: 'adult' },
        { id: '3', age_group: 'child' },
      ]

      const wrapper = mount(RelationshipsView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      expect(wrapper.text()).toContain('Children (2)')
    })
  })

  describe('Data Loading', () => {
    it('should fetch all data on mount', async () => {
      await router.isReady()

      mount(RelationshipsView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      expect(relationshipStore.fetchVaultRelationships).toHaveBeenCalledWith('test-vault-id')
      expect(pregnancyStore.fetchVaultPregnancies).toHaveBeenCalledWith('test-vault-id')
      expect(dwellerStore.fetchAllDwellers).toHaveBeenCalledWith('test-vault-id', 'mock-token')
    })
  })
})
