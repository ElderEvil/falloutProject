import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DwellerBio from '@/modules/dwellers/components/DwellerBio.vue'

describe('DwellerBio', () => {
  describe('Generate Bio Button', () => {
    it('should render generate button when no bio exists', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: null,
        },
      })

      const generateButton = wrapper.find('.generate-button')
      expect(generateButton.exists()).toBe(true)
    })

    it('should render generate button when bio is empty string', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: '',
        },
      })

      const generateButton = wrapper.find('.generate-button')
      expect(generateButton.exists()).toBe(true)
    })

    it('should describe biography generation when no bio exists', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: null,
        },
      })

      const generateButton = wrapper.find('.generate-button')
      expect(generateButton.text()).toContain('Generate biography')
    })

    it('should describe biography regeneration when bio exists', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: 'John is a brave vault dweller who loves to explore.',
        },
      })

      const generateButton = wrapper.find('.generate-button')
      expect(generateButton.text()).toContain('Regenerate biography')
    })

    it('should emit generate-bio event when button clicked', async () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: null,
        },
      })

      const generateButton = wrapper.find('.generate-button')
      await generateButton.trigger('click')

      expect(wrapper.emitted('generate-bio')).toBeTruthy()
      expect(wrapper.emitted('generate-bio')?.length).toBe(1)
    })
  })

  describe('Loading State', () => {
    it('should disable button when isAnyGenerating is true', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: null,
          isAnyGenerating: true,
        },
      })

      const generateButton = wrapper.find('.generate-button')
      expect(generateButton.attributes('disabled')).toBeDefined()
    })

    it('should not disable button when isAnyGenerating is false', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: null,
          isAnyGenerating: false,
        },
      })

      const generateButton = wrapper.find('.generate-button')
      expect(generateButton.attributes('disabled')).toBeUndefined()
    })

    it('should have animate-spin class when generating', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: null,
          generatingBio: true,
        },
      })

      const icon = wrapper.find('.generate-button svg')
      expect(icon.classes()).toContain('animate-spin')
    })
  })

  describe('Biography Display', () => {
    it('should display bio text when bio exists', () => {
      const bioText = 'John is a brave vault dweller who loves to explore the wasteland.'

      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: bioText,
        },
      })

      expect(wrapper.text()).toContain(bioText)
    })

    it('should show placeholder when no bio exists', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: null,
        },
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
          bio: bioText,
        },
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
          bio: null,
        },
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
          bio: null,
        },
      })

      const tooltip = wrapper.findComponent({ name: 'UTooltip' })
      expect(tooltip.exists()).toBe(true)
      expect(tooltip.props('text')).toBe("Creates or replaces this dweller's biography")
    })
  })

  describe('Placeholder Messages', () => {
    it('should show personalized placeholder message with dweller name', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'Sarah',
          bio: null,
        },
      })

      const placeholderText = wrapper.find('.placeholder-text')
      expect(placeholderText.exists()).toBe(true)
      expect(placeholderText.text()).toContain('Sarah')
    })

    it('should show hint text in placeholder', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: null,
        },
      })

      const placeholderHint = wrapper.find('.placeholder-hint')
      expect(placeholderHint.exists()).toBe(true)
      expect(placeholderHint.text()).toContain('Click "Generate" to create a unique backstory')
    })
  })

  describe('Place Links', () => {
    it('should render anchor for matching place name', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: 'John grew up in Megaton before wandering the wasteland.',
          vaultId: 'v1',
          placeLinks: [{ name: 'Megaton', locationId: 'loc1' }],
        },
      })

      const link = wrapper.find('a.bio-place-link')
      expect(link.exists()).toBe(true)
      expect(link.attributes('href')).toBe('/vault/v1/map?place=loc1')
      expect(link.text()).toBe('Megaton')
    })

    it('should NOT render anchor when placeLinks is absent', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: 'John grew up in Megaton.',
        },
      })

      expect(wrapper.find('a.bio-place-link').exists()).toBe(false)
      expect(wrapper.text()).toContain('Megaton')
    })

    it('should NOT render anchor when vaultId is absent', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: 'John grew up in Megaton.',
          placeLinks: [{ name: 'Megaton', locationId: 'loc1' }],
        },
      })

      expect(wrapper.find('a.bio-place-link').exists()).toBe(false)
    })

    it('should NOT render anchor when placeLinks is empty', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: 'John grew up in Megaton.',
          vaultId: 'v1',
          placeLinks: [],
        },
      })

      expect(wrapper.find('a.bio-place-link').exists()).toBe(false)
    })

    it('should escape special characters in place names', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: 'John visited R&D Labs in the ruins.',
          vaultId: 'v1',
          placeLinks: [{ name: 'R&D Labs', locationId: 'loc2' }],
        },
      })

      const link = wrapper.find('a.bio-place-link')
      expect(link.exists()).toBe(true)
      expect(link.text()).toBe('R&D Labs')
      expect(wrapper.html()).toContain('R&amp;D Labs')
    })

    it('should linkify place names inside entity-encoded text (e.g. R&amp;D Labs)', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: 'John visited R&amp;D Labs in the ruins.',
          vaultId: 'v1',
          placeLinks: [{ name: 'R&D Labs', locationId: 'loc2' }],
        },
      })

      const link = wrapper.find('a.bio-place-link')
      expect(link.exists()).toBe(true)
      expect(link.text()).toBe('R&D Labs')
      expect(link.attributes('href')).toBe('/vault/v1/map?place=loc2')
    })

    it('should sanitize XSS attempts in bio text', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: '<img src=x onerror=alert(1)>John lived in Megaton.',
          vaultId: 'v1',
          placeLinks: [{ name: 'Megaton', locationId: 'loc1' }],
        },
      })

      expect(wrapper.html()).not.toContain('<img')
      expect(wrapper.find('a.bio-place-link').exists()).toBe(true)
    })

    it('should linkify multiple places', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: 'John traveled from Megaton to Rivet City.',
          vaultId: 'v1',
          placeLinks: [
            { name: 'Megaton', locationId: 'loc1' },
            { name: 'Rivet City', locationId: 'loc2' },
          ],
        },
      })

      const links = wrapper.findAll('a.bio-place-link')
      expect(links).toHaveLength(2)
      expect(links[0].text()).toBe('Megaton')
      expect(links[0].attributes('href')).toBe('/vault/v1/map?place=loc1')
      expect(links[1].text()).toBe('Rivet City')
      expect(links[1].attributes('href')).toBe('/vault/v1/map?place=loc2')
    })

    it('should match longest name first to avoid partial matches', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: 'John visited Rivet City and the old City ruins.',
          vaultId: 'v1',
          placeLinks: [
            { name: 'City', locationId: 'loc-city' },
            { name: 'Rivet City', locationId: 'loc-rivet' },
          ],
        },
      })

      const links = wrapper.findAll('a.bio-place-link')
      expect(links).toHaveLength(2)
      expect(links[0].text()).toBe('Rivet City')
      expect(links[0].attributes('href')).toBe('/vault/v1/map?place=loc-rivet')
      expect(links[1].text()).toBe('City')
      expect(links[1].attributes('href')).toBe('/vault/v1/map?place=loc-city')
    })

    it('should preserve original bio casing in link text', () => {
      const wrapper = mount(DwellerBio, {
        props: {
          firstName: 'John',
          bio: 'John lived in MEGATON for years.',
          vaultId: 'v1',
          placeLinks: [{ name: 'Megaton', locationId: 'loc1' }],
        },
      })

      const link = wrapper.find('a.bio-place-link')
      expect(link.exists()).toBe(true)
      expect(link.text()).toBe('MEGATON')
    })
  })
})
