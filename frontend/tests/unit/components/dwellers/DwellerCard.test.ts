import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import DwellerCard from '@/modules/dwellers/components/cards/DwellerCard.vue'

// Mock the happiness service
vi.mock('@/modules/dwellers/services/happinessService', () => ({
  happinessService: {
    getDwellerModifiers: vi.fn().mockResolvedValue({
      data: { positive: [], negative: [] },
    }),
  },
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
    room: null,
  } as any

  describe('Portrait Display', () => {
    it('should render portrait placeholder when no image', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      const placeholder = wrapper.find('.portrait-placeholder')
      expect(placeholder.exists()).toBe(true)
    })

    it('makes the empty portrait a direct generate action', async () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      const placeholder = wrapper.find('.portrait-placeholder')
      expect(placeholder.text()).toContain('Generate portrait')

      await placeholder.trigger('click')
      expect(wrapper.emitted('generate-portrait')).toHaveLength(1)
    })

    it('should render portrait image when imageUrl is provided', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: 'https://example.com/image.jpg',
        },
      })

      const image = wrapper.find('.portrait-image')
      expect(image.exists()).toBe(true)
      expect(image.attributes('src')).toContain('example.com/image.jpg')
    })

    it('marks a dead dweller portrait as deceased', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: { ...mockDweller, is_dead: true },
          imageUrl: 'https://example.com/image.jpg',
        },
      })

      expect(wrapper.find('.portrait-image').classes()).toContain('grayscale')
      expect(wrapper.find('.dead-portrait-marker').exists()).toBe(true)
    })
  })

  describe('Info Badges', () => {
    it('should display gender badge', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      const badges = wrapper.findAll('.dweller-badge')
      const genderBadge = badges.find((b) => b.attributes('aria-label') === 'male')
      expect(genderBadge).toBeDefined()
      expect(genderBadge!.text()).toContain('male')
    })

    it('should display rarity badge', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      const badges = wrapper.findAll('.dweller-badge')
      const rarityBadge = badges.find((b) => b.attributes('aria-label')?.toLowerCase() === 'common')
      expect(rarityBadge).toBeDefined()
      expect(rarityBadge!.text().toLowerCase()).toContain('common')
    })
  })

  describe('Stats Display', () => {
    it('should display level', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      expect(wrapper.text()).toContain('Level')
      expect(wrapper.text()).toContain('5')
    })

    it('should display health', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      expect(wrapper.text()).toContain('Health')
      expect(wrapper.text()).toContain('80 / 100')
    })

    it('should display happiness percentage', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      expect(wrapper.text()).toContain('Happiness')
      expect(wrapper.text()).toContain('75%')
    })

    it('should display health bar', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      const progressBar = wrapper.findComponent({ name: 'UProgressBar' })
      expect(progressBar.exists()).toBe(true)
      expect(progressBar.props('modelValue')).toBe(80)
    })
  })

  describe('Inventory Display', () => {
    it('lets the overseer issue one supply from the counter', async () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
          availableStimpaks: 1,
        },
      })

      await wrapper.get('[aria-label="Issue Stimpack from vault"]').trigger('click')

      expect(wrapper.emitted('issue-medical-supply')).toEqual([['stimpack']])
    })

    it('waits for vault stock before enabling supply issue', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
          availableStimpaks: 0,
        },
      })

      expect(wrapper.find('[aria-label="Issue Stimpack from vault"]').exists()).toBe(false)
    })

    it('should display stimpack count', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      expect(wrapper.text()).toContain('Stimpack')
      expect(wrapper.text()).toContain('2')
    })

    it('should display radaway count', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
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
          imageUrl: null,
        },
      })

      const chatButton = wrapper
        .findAllComponents({ name: 'UButton' })
        .find((btn) => btn.text().includes('Chat'))

      expect(chatButton).toBeDefined()
      await chatButton!.trigger('click')
      expect(wrapper.emitted('chat')).toBeTruthy()
    })

    it('should emit assign event when assign button clicked', async () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      const assignButton = wrapper
        .findAllComponents({ name: 'UButton' })
        .find((btn) => btn.text().includes('Assign to Room'))

      expect(assignButton).toBeDefined()
      await assignButton!.trigger('click')
      expect(wrapper.emitted('assign')).toBeTruthy()
    })

    it('should show recall button when dweller is exploring', async () => {
      const exploringDweller = { ...mockDweller, status: 'exploring' }
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: exploringDweller,
          imageUrl: null,
        },
      })

      const recallButton = wrapper
        .findAllComponents({ name: 'UButton' })
        .find((btn) => btn.text().includes('Recall from Wasteland'))

      expect(recallButton).toBeDefined()
    })

    it('should not show recall button when dweller is not exploring', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      const recallButton = wrapper
        .findAllComponents({ name: 'UButton' })
        .find((btn) => btn.text().includes('Recall from Wasteland'))

      expect(recallButton).toBeUndefined()
    })
  })

  describe('Item Usage', () => {
    it('should enable stimpack use button when stimpack available and health below 60%', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: { ...mockDweller, health: 40 },
          imageUrl: null,
        },
      })

      const useStimpakBtn = wrapper.find('[aria-label="Use Stimpack"]')
      expect(useStimpakBtn.exists()).toBe(true)
      expect(useStimpakBtn.attributes('disabled')).toBeUndefined()
    })

    it('should disable stimpack use button when no stimpacks', () => {
      const dwellerNoStimpack = { ...mockDweller, stimpack: 0 }
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: dwellerNoStimpack,
          imageUrl: null,
        },
      })

      const useStimpakBtn = wrapper.find('[aria-label="Use Stimpack"]')
      expect(useStimpakBtn.exists()).toBe(true)
      expect(useStimpakBtn.attributes('disabled')).toBeDefined()
    })

    it('should disable stimpack use button when radiation caps health', () => {
      const dwellerAtCap = { ...mockDweller, radiation: 20 }
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: dwellerAtCap,
          imageUrl: null,
        },
      })

      const useStimpakBtn = wrapper.find('[aria-label="Use Stimpack"]')
      expect(useStimpakBtn.exists()).toBe(true)
      expect(useStimpakBtn.attributes('disabled')).toBeDefined()
      expect(useStimpakBtn.attributes('title')).toContain('RadAway')
    })

    it('should disable radaway use button when no radiation', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      const useRadAwayBtn = wrapper.find('[aria-label="Use RadAway"]')
      expect(useRadAwayBtn.exists()).toBe(true)
      expect(useRadAwayBtn.attributes('disabled')).toBeDefined()
    })

    it('should enable radaway use button when radiation exceeds 40% of max health', () => {
      const dwellerWithRadiation = { ...mockDweller, radiation: 45 }
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: dwellerWithRadiation,
          imageUrl: null,
        },
      })

      const useRadAwayBtn = wrapper.find('[aria-label="Use RadAway"]')
      expect(useRadAwayBtn.exists()).toBe(true)
      expect(useRadAwayBtn.attributes('disabled')).toBeUndefined()
    })

    it('emits use-stimpak when the Use button is clicked', async () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: { ...mockDweller, health: 40 },
          imageUrl: null,
        },
      })

      await wrapper.find('[aria-label="Use Stimpack"]').trigger('click')
      expect(wrapper.emitted('use-stimpak')).toBeTruthy()
    })

    it('emits use-radaway when the Use button is clicked', async () => {
      const dwellerWithRadiation = { ...mockDweller, radiation: 45 }
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: dwellerWithRadiation,
          imageUrl: null,
        },
      })

      await wrapper.find('[aria-label="Use RadAway"]').trigger('click')
      expect(wrapper.emitted('use-radaway')).toBeTruthy()
    })
  })

  describe('Coming Soon Features', () => {
    it('should show locked train stats button', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      const trainButton = wrapper.find('.locked-action-button')
      expect(trainButton.exists()).toBe(true)
      expect(wrapper.text()).toContain('Train Stats')
    })

    it('should show locked assign pet button', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      expect(wrapper.text()).toContain('Assign Pet')
    })
  })

  describe('Button Tooltips', () => {
    it('should have tooltip for train stats button', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      const tooltips = wrapper.findAllComponents({ name: 'UTooltip' })
      const trainTooltip = tooltips.find((t) => t.props('text')?.includes('Train SPECIAL stats'))

      expect(trainTooltip).toBeDefined()
    })

    it('should have tooltip for assign pet button', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
        },
      })

      const tooltips = wrapper.findAllComponents({ name: 'UTooltip' })
      const petTooltip = tooltips.find((t) => t.props('text')?.includes('Assign a pet companion'))

      expect(petTooltip).toBeDefined()
    })
  })
})
