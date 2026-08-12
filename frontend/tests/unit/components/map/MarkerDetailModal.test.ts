import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import MarkerDetailModal from '@/modules/map/components/MarkerDetailModal.vue'
import type { WastelandLocationWithDwellers, VaultMarkerRead } from '@/modules/map/models/map'

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
    it('should render the place name in the modal title', () => {
      const wrapper = mount(MarkerDetailModal, {
        props: {
          modelValue: true,
          location: createLocation(),
          vaultMarker: null,
        },
        global: {
          stubs: {
            teleport: true,
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
          stubs: { teleport: true },
        },
      })

      expect(wrapper.text()).toContain('origin')
    })

    it('should render the description', () => {
      const wrapper = mount(MarkerDetailModal, {
        props: {
          modelValue: true,
          location: createLocation(),
          vaultMarker: null,
        },
        global: {
          stubs: { teleport: true },
        },
      })

      expect(wrapper.text()).toContain('A town built around an unexploded atomic bomb')
    })

    it('should list linked dwellers', () => {
      const wrapper = mount(MarkerDetailModal, {
        props: {
          modelValue: true,
          location: createLocation(),
          vaultMarker: null,
        },
        global: {
          stubs: { teleport: true },
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
          stubs: { teleport: true },
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
          stubs: { teleport: true },
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
          stubs: { teleport: true },
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
          stubs: { teleport: true },
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
          stubs: { teleport: true },
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
          stubs: { teleport: true },
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
          stubs: { teleport: true },
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
          stubs: { teleport: true },
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
          stubs: { teleport: true },
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
          stubs: { teleport: true },
        },
      })

      expect(wrapper.text()).toContain('Unknown Location')
      expect(wrapper.text()).toContain('Chat with a dweller who has been here to uncover this place.')
      expect(wrapper.text()).not.toContain('origin')
    })

    it('should NOT show locked placeholder when location is unlocked', () => {
      const wrapper = mount(MarkerDetailModal, {
        props: {
          modelValue: true,
          location: createLocation({ is_unlocked: true }),
          vaultMarker: null,
        },
        global: {
          stubs: { teleport: true },
        },
      })

      expect(wrapper.text()).not.toContain('Unknown Location')
      expect(wrapper.text()).toContain('origin')
    })
  })
})
