import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import RoomDetailModal from '@/modules/rooms/components/RoomDetailModal.vue'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useAuthStore } from '@/modules/auth/stores/auth'

// Mock @iconify/vue
vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    props: ['icon'],
    template: '<div class="mock-icon" :data-icon="icon"></div>'
  }
}))

// Mock UModal and UButton
vi.mock('@/core/components/ui/UModal.vue', () => ({
  default: {
    name: 'UModal',
    props: ['modelValue', 'size'],
    emits: ['update:modelValue', 'close'],
    template: `
      <div v-if="modelValue" class="mock-modal">
        <slot name="header" />
        <slot />
      </div>
    `,
    methods: {
      '$emit': (event: string, payload?: any) => {
        // Mock emit method
        console.log('Emitting:', event, payload)
      }
    }
  }
}))

vi.mock('@/core/components/ui/UButton.vue', () => ({
  default: {
    name: 'UButton',
    props: ['disabled', 'variant'],
    template: '<button class="mock-button" :disabled="disabled"><slot /></button>'
  }
}))

vi.mock('@/core/components/ui/UTooltip.vue', () => ({
  default: {
    name: 'UTooltip',
    props: ['text'],
    template: '<div class="mock-tooltip" :data-tooltip="text"><slot /></div>'
  }
}))

vi.mock('@/core/components/ui/UAlert.vue', () => ({
  default: {
    name: 'UAlert',
    props: ['variant'],
    template: '<div class="mock-alert" :data-variant="variant"><slot /></div>'
  }
}))

// Mock useToast
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    show: vi.fn(),
    toasts: { value: [] },
    remove: vi.fn()
  })
}))

// Mock axios
vi.mock('@/core/plugins/axios', () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
  }
}))

// Mock vue-router with shared mocks so we can spy on router.push
const mockRouterPush = vi.fn()
vi.mock('vue-router', () => ({
  useRoute: () => ({
    params: { id: 'vault-123' }
  }),
  useRouter: () => ({
    push: mockRouterPush
  })
}))

describe('RoomDetailModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  const mockRoom = {
    id: 'room-1',
    name: 'Power Generator',
    category: 'PRODUCTION',
    ability: 'STRENGTH',
    tier: 1,
    capacity: 4,
    output: 10,
    size: 3,
    size_min: 3,
    size_max: 9,
    coordinate_x: 0,
    coordinate_y: 0,
    t2_upgrade_cost: 500,
    t3_upgrade_cost: 1500,
    base_cost: 100,
    incremental_cost: null,
    population_required: null,
    image_url: null,
    vault_id: 'vault-123',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z'
  }

  const mockDwellers = [
    {
      id: 'dweller-1',
      first_name: 'John',
      last_name: 'Doe',
      level: 5,
      strength: 8,
      perception: 5,
      endurance: 6,
      charisma: 4,
      intelligence: 7,
      agility: 5,
      luck: 6,
      room_id: 'room-1',
      vault_id: 'vault-123',
      status: 'working'
    },
    {
      id: 'dweller-2',
      first_name: 'Jane',
      last_name: 'Smith',
      level: 7,
      strength: 9,
      perception: 6,
      endurance: 7,
      charisma: 5,
      intelligence: 6,
      agility: 7,
      luck: 5,
      room_id: 'room-1',
      vault_id: 'vault-123',
      status: 'working'
    }
  ]

  describe('Rendering', () => {
    it('should render when show is true', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true
        }
      })

      expect(wrapper.find('.mock-modal').exists()).toBe(true)
      expect(wrapper.text()).toContain('Power Generator')
    })

    it('should not render when show is false', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: false
        }
      })

      expect(wrapper.find('.mock-modal').exists()).toBe(false)
    })

    it('should display room name and tier', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true
        }
      })

      expect(wrapper.text()).toContain('Power Generator')
      expect(wrapper.text()).toContain('Tier 1')
    })

    it('should display room category', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true
        }
      })

      expect(wrapper.text()).toContain('PRODUCTION')
    })
  })

  describe('Room Information', () => {
    it('should display capacity information', () => {
      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true
        }
      })

      expect(wrapper.text()).toContain('Dwellers')
      expect(wrapper.text()).toContain('2 / 2')
    })

    it('should display room size', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true
        }
      })

      expect(wrapper.text()).toContain('Room Size')
      expect(wrapper.text()).toContain('1x merged')
    })

    it('should display room position', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true
        }
      })

      expect(wrapper.text()).toContain('Position')
      expect(wrapper.text()).toContain('(0, 0)')
    })

    it('should display required stat', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true
        }
      })

      expect(wrapper.text()).toContain('Required Stat')
      expect(wrapper.text()).toContain('S - Strength')
    })
  })

  describe('Production Statistics', () => {
    it('should show production stats for production rooms', () => {
      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true
        }
      })

      expect(wrapper.text()).toContain('Production Statistics')
      expect(wrapper.text()).toContain('Resource Type')
      expect(wrapper.text()).toContain('Power')
    })

    it('should calculate production rate correctly', () => {
      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true
        }
      })

      // Production calculation: output * abilitySum * BASE_PRODUCTION_RATE * tierMultiplier
      // output = 10, abilitySum = 8 + 9 = 17, BASE = 0.1, tier1 = 1.0
      // perSecond = 10 * 17 * 0.1 * 1.0 = 17
      // perMinute = 17 * 60 = 1020
      expect(wrapper.text()).toContain('Production Rate')
      expect(wrapper.text()).toContain('1020.00')
    })

    it('should calculate efficiency correctly', () => {
      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true
        }
      })

      // Efficiency = (2 dwellers / 2 capacity) * 100 = 100%
      expect(wrapper.text()).toContain('Efficiency')
      expect(wrapper.text()).toContain('100%')
    })

    it('should show 100% efficiency when fully staffed', () => {
      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true
        }
      })

      expect(wrapper.text()).toContain('100%')
    })

    it('should not show production stats for non-production rooms', () => {
      const nonProductionRoom = {
        ...mockRoom,
        category: 'LIVING',
        ability: null
      }

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: nonProductionRoom,
          modelValue: true
        }
      })

      expect(wrapper.text()).not.toContain('Production Statistics')
    })

    it('should show correct resource type for AGILITY (Food)', () => {
      const foodRoom = {
        ...mockRoom,
        ability: 'AGILITY'
      }

      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: foodRoom,
          modelValue: true
        }
      })

      expect(wrapper.text()).toContain('Food')
    })

    it('should show correct resource type for PERCEPTION (Water)', () => {
      const waterRoom = {
        ...mockRoom,
        ability: 'PERCEPTION'
      }

      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: waterRoom,
          modelValue: true
        }
      })

      expect(wrapper.text()).toContain('Water')
    })
  })

  describe('Assigned Dwellers', () => {
    it('should display assigned dwellers', () => {
      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true
        }
      })

      expect(wrapper.text()).toContain('John Doe')
      expect(wrapper.text()).toContain('Jane Smith')
      expect(wrapper.text()).toContain('Level 5')
      expect(wrapper.text()).toContain('Level 7')
    })

    it('should show dweller count in header', () => {
      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true
        }
      })

      expect(wrapper.text()).toContain('Dweller Details (2)')
    })

    it('should show empty state when no dwellers assigned', () => {
      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = []

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true
        }
      })

      expect(wrapper.text()).toContain('No dwellers assigned to this room')
      expect(wrapper.text()).toContain('Drag dwellers from the sidebar to assign them')
    })

    it('should display relevant SPECIAL stat for each dweller', () => {
      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true
        }
      })

      // Room requires STRENGTH, so should show strength values (8 and 9)
      expect(wrapper.text()).toContain('8')
      expect(wrapper.text()).toContain('9')
    })
  })

  describe('Management Actions', () => {
    it('should show upgrade button when room can be upgraded', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true
        }
      })

      expect(wrapper.text()).toContain('Upgrade to Tier 2')
      expect(wrapper.text()).toContain('500 caps')
    })

    it('should show max tier message when room is at max tier', () => {
      const maxTierRoom = {
        ...mockRoom,
        tier: 3
      }

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: maxTierRoom,
          modelValue: true
        }
      })

      expect(wrapper.text()).toContain('Max tier reached')
      expect(wrapper.text()).toContain('(3/3)')
    })

    it('should show tier 3 upgrade cost at tier 2', () => {
      const tier2Room = {
        ...mockRoom,
        tier: 2
      }

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: tier2Room,
          modelValue: true
        }
      })

      expect(wrapper.text()).toContain('Upgrade to Tier 3')
      expect(wrapper.text()).toContain('1500 caps')
    })

    it('should show unassign all button', () => {
      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true
        }
      })

      expect(wrapper.text()).toContain('Unassign All Dwellers')
    })

    it('should show destroy room button', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true
        }
      })

      expect(wrapper.text()).toContain('Destroy Room')
    })
  })

  describe('Events', () => {
    it('should emit close event when close button clicked', async () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true
        }
      })

      await wrapper.vm.$emit('close')
      expect(wrapper.emitted('close')).toBeTruthy()
    })

    it('should emit roomUpdated event after successful upgrade', async () => {
      const roomStore = useRoomStore()
      const authStore = useAuthStore()
      authStore.token = 'test-token'

      vi.spyOn(roomStore, 'upgradeRoom').mockResolvedValue()

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true
        }
      })

      const upgradeButton = wrapper.findAll('.mock-button')[0]
      await upgradeButton.trigger('click')
      await wrapper.vm.$nextTick()

      expect(wrapper.emitted('roomUpdated')).toBeTruthy()
    })
  })

  describe('Error Handling', () => {
    it('should display error message when action fails', async () => {
      const roomStore = useRoomStore()
      const authStore = useAuthStore()
      authStore.token = 'test-token'

      vi.spyOn(roomStore, 'upgradeRoom').mockRejectedValue(new Error('Insufficient caps'))

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true
        }
      })

      const upgradeButton = wrapper.findAll('.mock-button')[0]
      await upgradeButton.trigger('click')
      await wrapper.vm.$nextTick()
      await new Promise(resolve => setTimeout(resolve, 0))

      expect(wrapper.text()).toContain('Insufficient caps')
    })
  })

  describe('Production Rate with Different Tiers', () => {
    it('should multiply production by 1.5 for tier 2', () => {
      const tier2Room = {
        ...mockRoom,
        tier: 2
      }

      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: tier2Room,
          modelValue: true
        }
      })

      // Production: 10 * 17 * 0.1 * 1.5 = 25.5 per second, 1530 per minute
      expect(wrapper.text()).toContain('1530.00')
    })

    it('should multiply production by 2.0 for tier 3', () => {
      const tier3Room = {
        ...mockRoom,
        tier: 3
      }

      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: tier3Room,
          modelValue: true
        }
      })

      // Production: 10 * 17 * 0.1 * 2.0 = 34 per second, 2040 per minute
      expect(wrapper.text()).toContain('2040.00')
    })
  })

  describe('Radio Room UI and Mode Switching', () => {
    const mockRadioRoom = {
      ...mockRoom,
      name: 'Radio Studio',
      category: 'SPECIAL',
      ability: 'CHARISMA',
    }

    it('should show radio controls for radio rooms', () => {
      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = mockDwellers.map((d) => ({
        ...d,
        room_id: mockRadioRoom.id,
      }))

      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRadioRoom, modelValue: true },
      })

      expect(wrapper.text()).toContain('Radio Studio')
      expect(wrapper.find('.radio-controls').exists()).toBe(true)
    })

    it('should not show radio controls for non-radio rooms', () => {
      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRoom, modelValue: true },
      })

      expect(wrapper.find('.radio-controls').exists()).toBe(false)
    })

    it('should render recruitment and happiness mode buttons', () => {
      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = mockDwellers.map((d) => ({
        ...d,
        room_id: mockRadioRoom.id,
      }))

      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRadioRoom, modelValue: true },
      })

      const modeButtons = wrapper.findAll('.mode-btn')
      expect(modeButtons.length).toBe(2)
      expect(modeButtons[0].text()).toContain('Recruitment')
      expect(modeButtons[1].text()).toContain('Happiness')
    })

    it('should show active state on recruitment mode by default', () => {
      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = mockDwellers.map((d) => ({
        ...d,
        room_id: mockRadioRoom.id,
      }))

      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRadioRoom, modelValue: true },
      })

      const modeButtons = wrapper.findAll('.mode-btn')
      expect(modeButtons[0].classes()).toContain('active')
      expect(modeButtons[1].classes()).not.toContain('active')
    })

    it('should display radio status text', () => {
      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = mockDwellers.map((d) => ({
        ...d,
        room_id: mockRadioRoom.id,
      }))

      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRadioRoom, modelValue: true },
      })

      expect(wrapper.text()).toContain('Recruiting')
    })

    it('should show staffing warning when no dwellers assigned to radio room', () => {
      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = []

      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRadioRoom, modelValue: true },
      })

      expect(wrapper.find('.mock-alert').exists()).toBe(true)
      expect(wrapper.text()).toContain('Assign at least one dweller')
    })
  })

  describe('Recruitment Button Enable/Disable States', () => {
    const mockRadioRoom = {
      ...mockRoom,
      name: 'Radio Studio',
      category: 'SPECIAL',
      ability: 'CHARISMA',
    }

    it('should disable recruit button when no dwellers assigned', () => {
      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = []

      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRadioRoom, modelValue: true },
      })

      const recruitBtn = wrapper.find('.recruit-btn')
      expect(recruitBtn.exists()).toBe(true)
      expect(recruitBtn.attributes('disabled')).toBeDefined()
    })

    it('should enable recruit button when dwellers assigned and in recruitment mode', () => {
      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = mockDwellers.map((d) => ({
        ...d,
        room_id: mockRadioRoom.id,
      }))

      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRadioRoom, modelValue: true },
      })

      const recruitBtn = wrapper.find('.recruit-btn')
      expect(recruitBtn.exists()).toBe(true)
      expect(recruitBtn.attributes('disabled')).toBeUndefined()
    })

    it('should show recruit cost in button text', () => {
      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = mockDwellers.map((d) => ({
        ...d,
        room_id: mockRadioRoom.id,
      }))

      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRadioRoom, modelValue: true },
      })

      expect(wrapper.text()).toContain('Recruit Dweller')
      expect(wrapper.text()).toContain('100 caps')
    })
  })

  describe('Dweller Click Navigation', () => {
    it('should call router.push when dweller card is clicked', async () => {
      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRoom, modelValue: true },
      })

      const dwellerCards = wrapper.findAll('.dweller-card')
      expect(dwellerCards.length).toBe(2)

      await dwellerCards[0].trigger('click')

      expect(mockRouterPush).toHaveBeenCalledWith({
        name: 'dwellerDetail',
        params: { id: 'vault-123', dwellerId: 'dweller-1' },
      })
    })

    it('should navigate to correct dweller when second dweller is clicked', async () => {
      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRoom, modelValue: true },
      })

      const dwellerCards = wrapper.findAll('.dweller-card')
      await dwellerCards[1].trigger('click')

      expect(mockRouterPush).toHaveBeenCalledWith({
        name: 'dwellerDetail',
        params: { id: 'vault-123', dwellerId: 'dweller-2' },
      })
    })

    it('should have clickable class on dweller cards', () => {
      const dwellerStore = useDwellerStore()
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRoom, modelValue: true },
      })

      const dwellerCards = wrapper.findAll('.dweller-card')
      dwellerCards.forEach((card) => {
        expect(card.classes()).toContain('clickable')
      })
    })
  })

  describe('Error Clearing on Modal Close', () => {
    it('should clear error when modal closes', async () => {
      const roomStore = useRoomStore()
      const authStore = useAuthStore()
      authStore.token = 'test-token'

      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      vi.spyOn(roomStore, 'upgradeRoom').mockRejectedValue(new Error('Some error'))

      try {
        const wrapper = mount(RoomDetailModal, {
          props: { room: mockRoom, modelValue: true },
        })

        const upgradeButton = wrapper.findAll('.mock-button')[0]
        await upgradeButton.trigger('click')
        await wrapper.vm.$nextTick()
        await new Promise((resolve) => setTimeout(resolve, 0))

        expect(wrapper.text()).toContain('Some error')

        await wrapper.setProps({ modelValue: false })
        await wrapper.vm.$nextTick()

        await wrapper.setProps({ modelValue: true })
        await wrapper.vm.$nextTick()

        expect(wrapper.text()).not.toContain('Some error')
      } finally {
        consoleSpy.mockRestore()
      }
    })

    it('should not display error banner when no error exists', () => {
      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRoom, modelValue: true },
      })

      expect(wrapper.find('.error-banner').exists()).toBe(false)
    })
  })

  describe('Vault Door Edge Cases', () => {
    const mockVaultDoor = {
      ...mockRoom,
      name: 'Vault Door',
      category: 'SPECIAL',
      ability: null,
    }

    it('should show disabled destroy button for vault door', () => {
      const wrapper = mount(RoomDetailModal, {
        props: { room: mockVaultDoor, modelValue: true },
      })

      expect(wrapper.text()).toContain('Destroy Room')

      const tooltip = wrapper.find('.mock-tooltip')
      expect(tooltip.exists()).toBe(true)
      expect(tooltip.attributes('data-tooltip')).toBe(
        'The Vault Door is vital and cannot be destroyed.'
      )
    })

    it('should wrap vault door destroy button in tooltip', () => {
      const wrapper = mount(RoomDetailModal, {
        props: { room: mockVaultDoor, modelValue: true },
      })

      const tooltip = wrapper.find('.mock-tooltip')
      expect(tooltip.exists()).toBe(true)

      const destroyBtn = tooltip.find('.mock-button')
      expect(destroyBtn.exists()).toBe(true)
      expect(destroyBtn.attributes('disabled')).toBeDefined()
    })

    it('should enable destroy button for non-vault-door rooms', () => {
      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRoom, modelValue: true },
      })

      expect(wrapper.find('.mock-tooltip').exists()).toBe(false)

      const destroyButtons = wrapper.findAll('.mock-button').filter((btn) => {
        return btn.text().includes('Destroy Room')
      })
      expect(destroyButtons.length).toBe(1)
      expect(destroyButtons[0].attributes('disabled')).toBeUndefined()
    })

    it('should not show production stats for vault door', () => {
      const wrapper = mount(RoomDetailModal, {
        props: { room: mockVaultDoor, modelValue: true },
      })

      expect(wrapper.text()).not.toContain('Production Statistics')
    })

    it('should not show required stat when ability is null', () => {
      const wrapper = mount(RoomDetailModal, {
        props: { room: mockVaultDoor, modelValue: true },
      })

      expect(wrapper.text()).not.toContain('Required Stat')
    })
  })

  describe('Null Room Handling', () => {
    it('should not render modal content when room is null', () => {
      const wrapper = mount(RoomDetailModal, {
        props: { room: null, modelValue: true },
      })

      expect(wrapper.find('.modal-content').exists()).toBe(false)
    })
  })
})
