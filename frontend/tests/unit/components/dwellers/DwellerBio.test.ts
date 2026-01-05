import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DwellerBio from '@/components/dwellers/DwellerBio.vue'

describe('DwellerBio', () => {
  describe('Generate Bio Button', () => {
    it('should render generate button when no bio exists', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: null
        }
      })

      const generateButton = wrapper.find('.generate-bio-button')
      expect(generateButton.exists()).toBe(true)
    })

    it('should render generate button when bio is empty string', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: ''
        }
      })

      const generateButton = wrapper.find('.generate-bio-button')
      expect(generateButton.exists()).toBe(true)
    })

    it('should show "Generate" text when no bio exists', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: null
        }
      })

      const generateButton = wrapper.find('.generate-bio-button')
      expect(generateButton.text()).toContain('Generate')
      expect(generateButton.text()).not.toContain('Regenerate')
    })

    it('should show "Regenerate" text when bio exists', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: 'John is a brave vault dweller who loves to explore.'
        }
      })

      const generateButton = wrapper.find('.generate-bio-button')
      expect(generateButton.text()).toContain('Regenerate')
    })

    it('should emit generate-bio event when button clicked', async () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: null
        }
      })

      const generateButton = wrapper.find('.generate-bio-button')
      await generateButton.trigger('click')

      expect(wrapper.emitted('generate-bio')).toBeTruthy()
      expect(wrapper.emitted('generate-bio')?.length).toBe(1)
    })
  })

  describe('Loading State', () => {
    it('should disable button when generatingBio is true', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: null,
          generatingBio: true
        }
      })

      const generateButton = wrapper.find('.generate-bio-button')
      expect(generateButton.attributes('disabled')).toBeDefined()
    })

    it('should not disable button when generatingBio is false', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: null,
          generatingBio: false
        }
      })

      const generateButton = wrapper.find('.generate-bio-button')
      expect(generateButton.attributes('disabled')).toBeUndefined()
    })

    it('should have animate-spin class when generating', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: null,
          generatingBio: true
        }
      })

      const icon = wrapper.find('.generate-bio-button svg')
      expect(icon.classes()).toContain('animate-spin')
    })
  })

  describe('Biography Display', () => {
    it('should display bio text when bio exists', () => {
      const bioText = 'John is a brave vault dweller who loves to explore the wasteland.'

      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: bioText
        }
      })

      expect(wrapper.text()).toContain(bioText)
    })

    it('should show placeholder when no bio exists', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: null
        }
      })

      const placeholder = wrapper.find('.bio-placeholder')
      expect(placeholder.exists()).toBe(true)
      expect(placeholder.text()).toContain('No biography available for John yet')
    })

    it('should display bio content in styled container', () => {
      const bioText = 'John is a brave vault dweller.'

      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: bioText
        }
      })

      const bioContent = wrapper.find('.bio-content')
      expect(bioContent.exists()).toBe(true)

      const bioTextElement = wrapper.find('.bio-text')
      expect(bioTextElement.exists()).toBe(true)
      expect(bioTextElement.text()).toBe(bioText)
    })
  })

  describe('Component Structure', () => {
    it('should render bio header with title and button', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: null
        }
      })

      const bioHeader = wrapper.find('.bio-header')
      expect(bioHeader.exists()).toBe(true)

      const bioTitle = wrapper.find('.bio-title')
      expect(bioTitle.exists()).toBe(true)
      expect(bioTitle.text()).toBe('Biography')
    })

    it('should have tooltip for generate button', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: null
        }
      })

      const tooltip = wrapper.findComponent({ name: 'UTooltip' })
      expect(tooltip.exists()).toBe(true)
      expect(tooltip.props('text')).toBe('Generate biography with AI')
    })
  })

  describe('Placeholder Messages', () => {
    it('should show personalized placeholder message with dweller name', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'Sarah',
          bio: null
        }
      })

      const placeholderText = wrapper.find('.placeholder-text')
      expect(placeholderText.exists()).toBe(true)
      expect(placeholderText.text()).toContain('Sarah')
    })

    it('should show hint text in placeholder', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: null
        }
      })

      const placeholderHint = wrapper.find('.placeholder-hint')
      expect(placeholderHint.exists()).toBe(true)
      expect(placeholderHint.text()).toContain('Click "Generate" to create a unique backstory')
    })
  })

})
