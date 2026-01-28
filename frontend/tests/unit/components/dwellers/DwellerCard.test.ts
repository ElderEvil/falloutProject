import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import DwellerCard from '@/modules/dwellers/components/cards/DwellerCard.vue'

// Mock the happiness service
vi.mock('@/modules/dwellers/services/happinessService', () => ({
  happinessService: {
    getDwellerModifiers: vi.fn().mockResolvedValue({
      data: { positive: [], negative: [] }
    })
  }
}))

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('DwellerCard', () => {
  const mockDweller = {
    id: '123',
    first_name: 'John',
    last_name: 'Doe',
    level: 5,
    health: 80,
    max_health: 100,
    happiness: 75,
    strength: 8,
    perception: 6,
    endurance: 7,
    charisma: 5,
    intelligence: 4,
    agility: 6,
    luck: 7,
    gender: 'male',
    rarity: 'common',
    experience: 450,
    radiation: 0,
    stimpack: 2,
    radaway: 1,
    status: 'idle',
    room: null
  } as any

  describe('Portrait Display', () => {
    it('should render portrait placeholder when no image', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      const placeholder = wrapper.find('.portrait-placeholder')
      expect(placeholder.exists()).toBe(true)
    })

    it('should show hint text to generate portrait in Appearance tab', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      const hint = wrapper.find('.placeholder-hint')
      expect(hint.exists()).toBe(true)
      expect(hint.text()).toContain('Generate portrait in Appearance tab')
    })

    it('should render portrait image when imageUrl is provided', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: 'https://example.com/image.jpg'
        }
      })

      const image = wrapper.find('.portrait-image')
      expect(image.exists()).toBe(true)
      expect(image.attributes('src')).toContain('example.com/image.jpg')
    })
  })

  describe('Info Badges', () => {
    it('should display gender badge', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      const genderBadge = wrapper.find('.gender-badge')
      expect(genderBadge.exists()).toBe(true)
      expect(genderBadge.text()).toContain('male')
    })

    it('should display rarity badge', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      const rarityBadge = wrapper.find('.rarity-badge')
      expect(rarityBadge.exists()).toBe(true)
      expect(rarityBadge.text().toLowerCase()).toContain('common')
    })
  })

  describe('Stats Display', () => {
    it('should display level', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      expect(wrapper.text()).toContain('Level')
      expect(wrapper.text()).toContain('5')
    })

    it('should display health', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      expect(wrapper.text()).toContain('Health')
      expect(wrapper.text()).toContain('80 / 100')
    })

    it('should display happiness percentage', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      expect(wrapper.text()).toContain('Happiness')
      expect(wrapper.text()).toContain('75%')
    })

    it('should display health bar', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      const healthBar = wrapper.find('.health-bar')
      expect(healthBar.exists()).toBe(true)

      const healthFill = wrapper.find('.health-fill')
      expect(healthFill.exists()).toBe(true)
      expect(healthFill.attributes('style')).toContain('width: 80%')
    })
  })

  describe('Inventory Display', () => {
    it('should display stimpack count', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      expect(wrapper.text()).toContain('Stimpack')
      expect(wrapper.text()).toContain('2')
    })

    it('should display radaway count', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      expect(wrapper.text()).toContain('RadAway')
      expect(wrapper.text()).toContain('1')
    })
  })

  describe('Action Buttons', () => {
    it('should emit chat event when chat button clicked', async () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      const chatButton = wrapper.findAllComponents({ name: 'UButton' })
        .find(btn => btn.text().includes('Chat'))

      expect(chatButton).toBeDefined()
      await chatButton!.trigger('click')
      expect(wrapper.emitted('chat')).toBeTruthy()
    })

    it('should emit assign event when assign button clicked', async () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      const assignButton = wrapper.findAllComponents({ name: 'UButton' })
        .find(btn => btn.text().includes('Assign to Room'))

      expect(assignButton).toBeDefined()
      await assignButton!.trigger('click')
      expect(wrapper.emitted('assign')).toBeTruthy()
    })

    it('should show recall button when dweller is exploring', async () => {
      const exploringDweller = { ...mockDweller, status: 'exploring' }
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: exploringDweller,
          imageUrl: null
        }
      })

      const recallButton = wrapper.findAllComponents({ name: 'UButton' })
        .find(btn => btn.text().includes('Recall from Wasteland'))

      expect(recallButton).toBeDefined()
    })

    it('should not show recall button when dweller is not exploring', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      const recallButton = wrapper.findAllComponents({ name: 'UButton' })
        .find(btn => btn.text().includes('Recall from Wasteland'))

      expect(recallButton).toBeUndefined()
    })
  })

  describe('Item Usage', () => {
    it('should enable stimpack button when stimpack available and health not full', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      const stimpPackButton = wrapper.findAllComponents({ name: 'UButton' })
        .find(btn => btn.text().includes('Use Stimpack'))

      expect(stimpPackButton).toBeDefined()
      expect(stimpPackButton!.attributes('disabled')).toBeUndefined()
    })

    it('should disable stimpack button when no stimpacks', () => {
      const dwellerNoStimpack = { ...mockDweller, stimpack: 0 }
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: dwellerNoStimpack,
          imageUrl: null
        }
      })

      const stimpPackButton = wrapper.findAllComponents({ name: 'UButton' })
        .find(btn => btn.text().includes('Use Stimpack'))

      expect(stimpPackButton).toBeDefined()
      expect(stimpPackButton!.attributes('disabled')).toBeDefined()
    })

    it('should disable radaway button when no radiation', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      const radawayButton = wrapper.findAllComponents({ name: 'UButton' })
        .find(btn => btn.text().includes('Use RadAway'))

      expect(radawayButton).toBeDefined()
      expect(radawayButton!.attributes('disabled')).toBeDefined()
    })

    it('should enable radaway button when radiation exists', () => {
      const dwellerWithRadiation = { ...mockDweller, radiation: 10 }
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: dwellerWithRadiation,
          imageUrl: null
        }
      })

      const radawayButton = wrapper.findAllComponents({ name: 'UButton' })
        .find(btn => btn.text().includes('Use RadAway'))

      expect(radawayButton).toBeDefined()
      expect(radawayButton!.attributes('disabled')).toBeUndefined()
    })
  })

  describe('Coming Soon Features', () => {
    it('should show locked train stats button', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      const trainButton = wrapper.find('.locked-action-button')
      expect(trainButton.exists()).toBe(true)
      expect(wrapper.text()).toContain('Train Stats')
    })

    it('should show locked assign pet button', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      expect(wrapper.text()).toContain('Assign Pet')
    })
  })

  describe('Button Tooltips', () => {
    it('should have tooltip for train stats button', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      const tooltips = wrapper.findAllComponents({ name: 'UTooltip' })
      const trainTooltip = tooltips.find(t =>
        t.props('text')?.includes('Train SPECIAL stats')
      )

      expect(trainTooltip).toBeDefined()
    })

    it('should have tooltip for assign pet button', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      const tooltips = wrapper.findAllComponents({ name: 'UTooltip' })
      const petTooltip = tooltips.find(t =>
        t.props('text')?.includes('Assign a pet companion')
      )

      expect(petTooltip).toBeDefined()
    })
  })
})
