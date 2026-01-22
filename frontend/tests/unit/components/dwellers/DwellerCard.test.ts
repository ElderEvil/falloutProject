import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DwellerCard from '@/modules/dwellers/components/cards/DwellerCard.vue'

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
    radaway: 1
  } as any

  describe('Regenerate Buttons - No Image', () => {
    it('should display portrait button when no image', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      const portraitButton = wrapper.find('.portrait-button')
      expect(portraitButton.exists()).toBe(true)
    })

    it('should display full generate button when no image', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      const fullGenerateButton = wrapper.find('.full-generate-button')
      expect(fullGenerateButton.exists()).toBe(true)
    })

    it('should not display generate buttons when image exists', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: 'https://example.com/image.jpg'
        }
      })

      const portraitButton = wrapper.find('.portrait-button')
      const fullGenerateButton = wrapper.find('.full-generate-button')

      expect(portraitButton.exists()).toBe(false)
      expect(fullGenerateButton.exists()).toBe(false)
    })

    it('should emit generate-portrait event when portrait button clicked', async () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      const portraitButton = wrapper.find('.portrait-button')
      await portraitButton.trigger('click')

      expect(wrapper.emitted('generate-portrait')).toBeTruthy()
      expect(wrapper.emitted('generate-portrait')?.length).toBe(1)
    })

    it('should emit generate-ai event when full generate button clicked', async () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      const fullGenerateButton = wrapper.find('.full-generate-button')
      await fullGenerateButton.trigger('click')

      expect(wrapper.emitted('generate-ai')).toBeTruthy()
      expect(wrapper.emitted('generate-ai')?.length).toBe(1)
    })
  })

  describe('Loading States', () => {
    it('should disable portrait button when generatingPortrait is true', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
          generatingPortrait: true
        }
      })

      const portraitButton = wrapper.find('.portrait-button')
      expect(portraitButton.attributes('disabled')).toBeDefined()
    })

    it('should disable portrait button when loading is true', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
          loading: true
        }
      })

      const portraitButton = wrapper.find('.portrait-button')
      expect(portraitButton.attributes('disabled')).toBeDefined()
    })

    it('should disable full generate button when loading is true', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null,
          loading: true
        }
      })

      const fullGenerateButton = wrapper.find('.full-generate-button')
      expect(fullGenerateButton.attributes('disabled')).toBeDefined()
    })

  })

  describe('Button Tooltips', () => {
    it('should have tooltip for portrait button', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      const tooltips = wrapper.findAllComponents({ name: 'UTooltip' })
      const portraitTooltip = tooltips.find(t => t.props('text') === 'Generate AI portrait')

      expect(portraitTooltip).toBeDefined()
    })

    it('should have tooltip for full generate button', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      const tooltips = wrapper.findAllComponents({ name: 'UTooltip' })
      const fullGenerateTooltip = tooltips.find(t => t.props('text') === 'Generate portrait & biography')

      expect(fullGenerateTooltip).toBeDefined()
    })
  })

  describe('Component Structure', () => {
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

  describe('Button Positioning', () => {
    it('should position portrait button in bottom-right', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      const portraitButton = wrapper.find('.portrait-button')
      expect(portraitButton.classes()).toContain('ai-generate-button')
      expect(portraitButton.classes()).toContain('portrait-button')
    })

    it('should position full generate button in center', () => {
      const wrapper = mount(DwellerCard, {
        props: {
          dweller: mockDweller,
          imageUrl: null
        }
      })

      const fullGenerateButton = wrapper.find('.full-generate-button')
      expect(fullGenerateButton.classes()).toContain('ai-generate-button')
      expect(fullGenerateButton.classes()).toContain('full-generate-button')
    })
  })
})
