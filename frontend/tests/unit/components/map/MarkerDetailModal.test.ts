import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import MarkerDetailModal from '@/modules/map/components/MarkerDetailModal.vue'
import { useMapStore } from '@/modules/map/stores/map'
import type {
  ExpeditionSiteMarkerRead,
  WastelandLocationWithDwellers,
  VaultMarkerRead,
} from '@/modules/map/models/map'

// Mock vue-router
const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
  useRoute: () => ({ params: { id: 'vault-1' } }),
}))

function createLocation(
  overrides: Partial<WastelandLocationWithDwellers> = {}
): WastelandLocationWithDwellers {
  return {
    id: 'loc-1',
    name: 'Megaton',
    normalized_name: 'megaton',
    type: 'origin',
    coord_x: 50,
    coord_y: 50,
    description: 'A town built around an unexploded atomic bomb.',
    vault_id: 'vault-1',
    exploration_id: null,
    created_at: null,
    dwellers: [
      {
        dweller_id: 'dweller-1',
        first_name: 'John',
        last_name: 'Doe',
        relation: 'origin',
        is_unlocked: true,
      },
      {
        dweller_id: 'dweller-2',
        first_name: 'Jane',
        last_name: null,
        relation: 'visited',
        is_unlocked: true,
      },
    ],
    is_unlocked: true,
    ...overrides,
  }
}

function createVaultMarker(overrides: Partial<VaultMarkerRead> = {}): VaultMarkerRead {
  return {
    name: 'Vault 88',
    coord_x: 30,
    coord_y: 40,
    type: 'vault',
    description: 'Unexplored vault signal - raiding available in a future update.',
    ...overrides,
  }
}

beforeEach(() => {
  setActivePinia(createPinia())
  mockPush.mockClear()
})

describe('MarkerDetailModal', () => {
  describe('Location marker display', () => {
    it('renders a dialog when open', () => {
      const wrapper = mount(MarkerDetailModal, {
        props: { modelValue: true, location: createLocation(), vaultMarker: null },
        global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
      })

      expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    })

    it('should render the place name in the modal title', () => {
      const wrapper = mount(MarkerDetailModal, {
        props: {
          modelValue: true,
          location: createLocation(),
          vaultMarker: null,
        },
        global: {
          stubs: {
            Teleport: { template: '<div><slot /></div>' },
          },
        },
      })

      expect(wrapper.text()).toContain('Megaton')
    })

    it('should render the type badge', () => {
      const wrapper = mount(MarkerDetailModal, {
        props: {
          modelValue: true,
          location: createLocation(),
          vaultMarker: null,
        },
        global: {
          stubs: { Teleport: { template: '<div><slot /></div>' } },
        },
      })

      expect(wrapper.text()).toContain('origin')
    })

    it('should render the site-type group when the catalog has it', () => {
      const store = useMapStore()
      store.placeGroups = [
        {
          key: 'gas_station',
          label: 'Gas Station',
          icon: 'mdi:gas-station',
          risk: 'low',
          description: 'A roadside fuel stop.',
        },
      ]
      const wrapper = mount(MarkerDetailModal, {
        props: {
          modelValue: true,
          location: createLocation({ group_key: 'gas_station' }),
          vaultMarker: null,
        },
        global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
      })

      expect(wrapper.text()).toContain('Gas Station')
    })

    it('should render the description', () => {
      const wrapper = mount(MarkerDetailModal, {
        props: {
          modelValue: true,
          location: createLocation(),
          vaultMarker: null,
        },
        global: {
          stubs: { Teleport: { template: '<div><slot /></div>' } },
        },
      })

      expect(wrapper.text()).toContain('A town built around an unexploded atomic bomb')
      expect(wrapper.text()).toContain('MAP COORDINATES')
      expect(wrapper.text()).toContain('50, 50')
      expect(wrapper.text()).toContain('KNOWN DWELLERS')
    })

    it('should list linked dwellers', () => {
      const wrapper = mount(MarkerDetailModal, {
        props: {
          modelValue: true,
          location: createLocation(),
          vaultMarker: null,
        },
        global: {
          stubs: { Teleport: { template: '<div><slot /></div>' } },
        },
      })

      expect(wrapper.text()).toContain('John Doe')
      expect(wrapper.text()).toContain('Jane')
      expect(wrapper.text()).toContain('Linked Dwellers')
    })

    it('should render dweller entries as buttons for keyboard accessibility', () => {
      const wrapper = mount(MarkerDetailModal, {
        props: {
          modelValue: true,
          location: createLocation(),
          vaultMarker: null,
        },
        global: {
          stubs: { Teleport: { template: '<div><slot /></div>' } },
        },
      })

      const buttons = wrapper.findAll('button.dweller-entry')
      expect(buttons).toHaveLength(2)
      expect(buttons[0].text()).toContain('John Doe')
      expect(buttons[1].text()).toContain('Jane')
    })
  })

  describe('Vault marker display', () => {
    it('should render vault marker name and description', () => {
      const wrapper = mount(MarkerDetailModal, {
        props: {
          modelValue: true,
          location: null,
          vaultMarker: createVaultMarker(),
        },
        global: {
          stubs: { Teleport: { template: '<div><slot /></div>' } },
        },
      })

      expect(wrapper.text()).toContain('Vault 88')
      expect(wrapper.text()).toContain('Unexplored vault signal')
    })

    it('should NOT render the dweller section for vault markers', () => {
      const wrapper = mount(MarkerDetailModal, {
        props: {
          modelValue: true,
          location: null,
          vaultMarker: createVaultMarker(),
        },
        global: {
          stubs: { Teleport: { template: '<div><slot /></div>' } },
        },
      })

      expect(wrapper.text()).not.toContain('Linked Dwellers')
    })

    it('should show vault type badge', () => {
      const wrapper = mount(MarkerDetailModal, {
        props: {
          modelValue: true,
          location: null,
          vaultMarker: createVaultMarker(),
        },
        global: {
          stubs: { Teleport: { template: '<div><slot /></div>' } },
        },
      })

      expect(wrapper.text()).toContain('vault')
    })
  })

  describe('Dweller navigation', () => {
    it('should call router.push with correct path on dweller click', async () => {
      const wrapper = mount(MarkerDetailModal, {
        props: {
          modelValue: true,
          location: createLocation(),
          vaultMarker: null,
        },
        global: {
          stubs: { Teleport: { template: '<div><slot /></div>' } },
        },
      })

      const vm = wrapper.vm as any
      vm.goToDweller('dweller-1')
      await wrapper.vm.$nextTick()

      expect(mockPush).toHaveBeenCalledWith('/vault/vault-1/dwellers/dweller-1')
    })

    it('should close modal before navigating', async () => {
      const wrapper = mount(MarkerDetailModal, {
        props: {
          modelValue: true,
          location: createLocation(),
          vaultMarker: null,
        },
        global: {
          stubs: { Teleport: { template: '<div><slot /></div>' } },
        },
      })

      const vm = wrapper.vm as any
      vm.goToDweller('dweller-1')
      await wrapper.vm.$nextTick()

      expect(wrapper.emitted('update:modelValue')).toBeTruthy()
      expect(wrapper.emitted('update:modelValue')![0][0]).toBe(false)
    })
  })

  describe('Empty/missing dwellers (failure case)', () => {
    it('should NOT render dweller section when dwellers array is empty', () => {
      const location = createLocation({ dwellers: [] })
      const wrapper = mount(MarkerDetailModal, {
        props: {
          modelValue: true,
          location,
          vaultMarker: null,
        },
        global: {
          stubs: { Teleport: { template: '<div><slot /></div>' } },
        },
      })

      expect(wrapper.text()).not.toContain('Linked Dwellers')
    })

    it('should show fallback description when location description is null', () => {
      const location = createLocation({ description: null })
      const wrapper = mount(MarkerDetailModal, {
        props: {
          modelValue: true,
          location,
          vaultMarker: null,
        },
        global: {
          stubs: { Teleport: { template: '<div><slot /></div>' } },
        },
      })

      expect(wrapper.text()).toContain('No description available')
    })
  })

  describe('Modal visibility', () => {
    it('should not render content when modelValue is false', () => {
      const wrapper = mount(MarkerDetailModal, {
        props: {
          modelValue: false,
          location: createLocation(),
          vaultMarker: null,
        },
        global: {
          stubs: { Teleport: { template: '<div><slot /></div>' } },
        },
      })

      expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    })
  })

  describe('Locked location placeholder', () => {
    it('should show locked placeholder when location is not unlocked', () => {
      const wrapper = mount(MarkerDetailModal, {
        props: {
          modelValue: true,
          location: createLocation({ is_unlocked: false }),
          vaultMarker: null,
        },
        global: {
          stubs: { Teleport: { template: '<div><slot /></div>' } },
        },
      })

      expect(wrapper.text()).toContain('Unknown Location')
      expect(wrapper.text()).toContain('Chat with a dweller who has been here to uncover this place.')
      expect(wrapper.text()).toContain('John Doe')
      expect(wrapper.findAll('button.dweller-contact')).toHaveLength(2)
      expect(wrapper.text()).not.toContain('origin')
    })

    it('opens a linked dweller chat from a locked location', async () => {
      const wrapper = mount(MarkerDetailModal, {
        props: {
          modelValue: true,
          location: createLocation({ is_unlocked: false }),
          vaultMarker: null,
        },
        global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
      })

      await wrapper.find('button.dweller-contact').trigger('click')

      expect(mockPush).toHaveBeenCalledWith('/dweller/dweller-1/chat')
    })

    it('should NOT show locked placeholder when location is unlocked', () => {
      const wrapper = mount(MarkerDetailModal, {
        props: {
          modelValue: true,
          location: createLocation({ is_unlocked: true }),
          vaultMarker: null,
        },
        global: {
          stubs: { Teleport: { template: '<div><slot /></div>' } },
        },
      })

      expect(wrapper.text()).not.toContain('Unknown Location')
      expect(wrapper.text()).toContain('origin')
    })
  })

  describe('Clear state (issue 772)', () => {
    const clearableState = {
      clearable: true,
      cleared: false,
      clear_count: 0,
      tier: 2,
      time_remaining_seconds: 0,
      loot_table: 'raider_camp_loot',
    }

    function mountWithClearState(clearState: unknown) {
      return mount(MarkerDetailModal, {
        props: {
          modelValue: true,
          location: createLocation({ clear_state: clearState }),
          vaultMarker: null,
        },
        global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
      })
    }

    it('renders nothing when clear_state is null', () => {
      const wrapper = mountWithClearState(null)

      expect(wrapper.text()).not.toContain('CLEAR STATUS')
      expect(wrapper.text()).not.toContain('CLEARED')
      expect(wrapper.text()).not.toContain('Dispatch')
    })

    it('shows a Dispatch button for a clearable, not-yet-cleared point', () => {
      const wrapper = mountWithClearState(clearableState)

      expect(wrapper.text()).toContain('CLEAR STATUS')
      expect(wrapper.text()).toContain('UNCLAIMED')
      expect(wrapper.text()).toContain('Tier 2')
      const dispatchButtons = wrapper
        .findAll('button')
        .filter((b) => b.text().includes('Dispatch'))
      expect(dispatchButtons).toHaveLength(1)
      expect(wrapper.text()).not.toContain('CLEARED')
    })

    it('shows a CLEARED badge with the clear count and a reclear countdown while cooling down', () => {
      const wrapper = mountWithClearState({
        ...clearableState,
        cleared: true,
        clear_count: 3,
        time_remaining_seconds: 3600,
      })

      expect(wrapper.text()).toContain('CLEARED ×3')
      expect(wrapper.text()).toContain('Re-clear available: 1h 0m remaining')
      expect(wrapper.text()).not.toContain('Dispatch')
    })

    it('advances the reclear countdown while the modal stays open', async () => {
      vi.useFakeTimers()
      try {
        const wrapper = mountWithClearState({
          ...clearableState,
          cleared: true,
          clear_count: 3,
          time_remaining_seconds: 5,
        })
        expect(wrapper.text()).toContain('Re-clear available')
        expect(wrapper.text()).not.toContain('Dispatch')

        await vi.advanceTimersByTimeAsync(5000)

        expect(wrapper.text()).not.toContain('Re-clear available')
        const dispatchButtons = wrapper
          .findAll('button')
          .filter((b) => b.text().includes('Dispatch'))
        expect(dispatchButtons).toHaveLength(1)
      } finally {
        vi.useRealTimers()
      }
    })

    it('shows a Dispatch button again once the reclear window has elapsed', () => {
      const wrapper = mountWithClearState({
        ...clearableState,
        cleared: true,
        clear_count: 3,
        time_remaining_seconds: 0,
      })

      expect(wrapper.text()).toContain('CLEARED ×3')
      expect(wrapper.text()).not.toContain('Re-clear available')
      const dispatchButtons = wrapper
        .findAll('button')
        .filter((b) => b.text().includes('Dispatch'))
      expect(dispatchButtons).toHaveLength(1)
    })

    it('emits dispatch when the Dispatch button is clicked', async () => {
      const wrapper = mountWithClearState(clearableState)

      const dispatchButton = wrapper
        .findAll('button')
        .find((b) => b.text().includes('Dispatch'))
      await dispatchButton!.trigger('click')

      expect(wrapper.emitted('dispatch')).toBeTruthy()
    })
  })

  describe('Expedition site display', () => {
    function createSite(
      overrides: Partial<ExpeditionSiteMarkerRead> = {}
    ): ExpeditionSiteMarkerRead {
      return {
        id: 'site-1',
        name: 'Red Rocket Gas Station',
        flavor: 'A roadside fuel stop with a working pump.',
        coord_x: 60,
        coord_y: 70,
        min_dweller_level: 5,
        room_total: 3,
        cleared: false,
        cooldown_remaining_seconds: 0,
        block_reason: null,
        ...overrides,
      }
    }

    function mountWithSite(site: ExpeditionSiteMarkerRead) {
      return mount(MarkerDetailModal, {
        props: { modelValue: true, location: null, vaultMarker: null, site },
        global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
      })
    }

    it('does not render the site section when the site prop is omitted', () => {
      const wrapper = mount(MarkerDetailModal, {
        props: { modelValue: true, location: null, vaultMarker: null },
        global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
      })

      expect(wrapper.text()).not.toContain('EXPEDITION SITE')
    })

    it('renders the site name, flavor, level and room count', () => {
      const wrapper = mountWithSite(createSite())

      expect(wrapper.text()).toContain('Red Rocket Gas Station')
      expect(wrapper.text()).toContain('A roadside fuel stop with a working pump.')
      expect(wrapper.text()).toContain('MIN DWELLER LEVEL')
      expect(wrapper.text()).toContain('ROOMS')
      expect(wrapper.text()).toContain('60, 70')
    })

    it('shows READY status for a ready site', () => {
      const wrapper = mountWithSite(createSite())

      expect(wrapper.text()).toContain('READY')
      expect(wrapper.text()).not.toContain('CLEARED')
      expect(wrapper.text()).not.toContain('IN PROGRESS')
    })

    it('shows IN PROGRESS status while a run is open', () => {
      const wrapper = mountWithSite(createSite({ block_reason: 'open' }))

      expect(wrapper.text()).toContain('IN PROGRESS')
    })

    it('shows CLEARED status with the cooldown for a cooling-down site', () => {
      const wrapper = mountWithSite(
        createSite({ cleared: true, block_reason: 'cooldown', cooldown_remaining_seconds: 3600 })
      )

      expect(wrapper.text()).toContain('CLEARED')
      expect(wrapper.text()).toContain('Cooldown: 1h 0m remaining')
    })

    it('advances the site cooldown countdown while the modal stays open', async () => {
      vi.useFakeTimers()
      try {
        const wrapper = mountWithSite(
          createSite({ cleared: true, block_reason: 'cooldown', cooldown_remaining_seconds: 5 })
        )
        expect(wrapper.text()).toContain('Cooldown:')

        await vi.advanceTimersByTimeAsync(5000)

        expect(wrapper.text()).not.toContain('Cooldown:')
      } finally {
        vi.useRealTimers()
      }
    })

    it('does not offer a Dispatch or Enter action for sites', () => {
      const wrapper = mountWithSite(createSite())

      const buttons = wrapper.findAll('button').filter((b) => {
        const text = b.text()
        return text.includes('Dispatch') || text.includes('Enter')
      })
      expect(buttons).toHaveLength(0)
    })
  })
})
