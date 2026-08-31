import { describe, it, expect, beforeEach } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { ref } from 'vue'
import DwellerBio from '@/modules/dwellers/components/DwellerBio.vue'
import { createMockDwellerDetailContext, mountWithDwellerContext } from '../../helpers/dwellerDetailContext'
import type { Dweller, MapPlaceLink } from '@/modules/dwellers/models/dweller'
import type { DwellerDetailContext } from '@/modules/dwellers/components/DwellerDetailContext'

function createCtx(overrides: Partial<DwellerDetailContext> = {}) {
  const ctx = createMockDwellerDetailContext()
  ctx.dweller = ref({ first_name: 'John', bio: null } as unknown as Dweller)
  ctx.vaultId = ref('v1') as never
  ctx.placeLinks = ref<MapPlaceLink[]>([]) as never
  return Object.assign(ctx, overrides)
}

describe('DwellerBio', () => {
  let wrapper: VueWrapper
  let ctx: DwellerDetailContext

  beforeEach(() => {
    ctx = createCtx()
    wrapper = mountWithDwellerContext(DwellerBio, { context: ctx })
  })

  describe('generate button', () => {
    it('should render generate button when no bio', () => {
      expect(wrapper.find('.generate-button').exists()).toBe(true)
    })

    it('should render generate button when bio is empty string', () => {
      ctx.dweller = ref({ first_name: 'John', bio: '' } as unknown as Dweller)
      wrapper = mountWithDwellerContext(DwellerBio, { context: ctx })
      expect(wrapper.find('.generate-button').exists()).toBe(true)
    })

    it('should describe biography generation when no bio exists', () => {
      expect(wrapper.find('.generate-button').text()).toContain('Generate biography')
    })

    it('should describe biography regeneration when bio exists', () => {
      ctx.dweller = ref({ first_name: 'John', bio: 'John is a vault dweller.' } as unknown as Dweller)
      wrapper = mountWithDwellerContext(DwellerBio, { context: ctx })
      expect(wrapper.find('.generate-button').text()).toContain('Regenerate biography')
    })

    it('offers biography extension only when a biography exists', () => {
      ctx.dweller = ref({ first_name: 'John', bio: 'John is a vault dweller.' } as unknown as Dweller)
      wrapper = mountWithDwellerContext(DwellerBio, { context: ctx })

      expect(wrapper.find('.extend-bio-button').text()).toContain('Extend biography')
    })

    it('should call the generateBio action when button clicked', async () => {
      await wrapper.find('.generate-button').trigger('click')
      expect(ctx.actions.generateBio).toHaveBeenCalledOnce()
    })

    it('should call the generateAll action when complete dossier clicked', async () => {
      await wrapper.find('.complete-dossier-button').trigger('click')
      expect(ctx.actions.generateAll).toHaveBeenCalledOnce()
    })

    it('should disable button when isAnyGenerating is true', () => {
      ctx.isAnyGenerating = ref(true) as never
      wrapper = mountWithDwellerContext(DwellerBio, { context: ctx })
      expect(wrapper.find('.generate-button').attributes('disabled')).toBeDefined()
    })

    it('should not disable when isAnyGenerating is false', () => {
      ctx.isAnyGenerating = ref(false) as never
      wrapper = mountWithDwellerContext(DwellerBio, { context: ctx })
      expect(wrapper.find('.generate-button').attributes('disabled')).toBeUndefined()
    })

    it('should apply animate-spin class to icon when generating', () => {
      ctx.generatingBio = ref(true) as never
      wrapper = mountWithDwellerContext(DwellerBio, { context: ctx })
      const svg = wrapper.find('.generate-button svg')
      expect(svg.exists()).toBe(true)
      expect(svg.classes()).toContain('animate-spin')
    })

    it('should render a tooltip on the generate button', () => {
      const tooltip = wrapper
        .findAllComponents({ name: 'UTooltip' })
        .find((item) => item.props('text') === "Creates or replaces this dweller's biography")
      expect(tooltip).toBeDefined()
    })
  })

  describe('bio content', () => {
    it('should display bio text when bio exists', () => {
      ctx.dweller = ref({ first_name: 'John', bio: 'John is a vault dweller.' } as unknown as Dweller)
      wrapper = mountWithDwellerContext(DwellerBio, { context: ctx })
      expect(wrapper.text()).toContain('John is a vault dweller.')
    })

    it('should show placeholder when no bio', () => {
      expect(wrapper.text()).toContain('No biography available for John yet')
    })

    it('should show personalized placeholder with dweller first name', () => {
      ctx.dweller = ref({ first_name: 'Sarah', bio: null } as unknown as Dweller)
      wrapper = mountWithDwellerContext(DwellerBio, { context: ctx })
      expect(wrapper.text()).toContain('No biography available for Sarah yet')
    })

    it('should show hint text in placeholder', () => {
      expect(wrapper.text()).toContain('Click "Generate" to create a unique backstory!')
    })

    it('should display bio content in a styled container', () => {
      ctx.dweller = ref({ first_name: 'John', bio: 'John is a vault dweller.' } as unknown as Dweller)
      wrapper = mountWithDwellerContext(DwellerBio, { context: ctx })
      expect(wrapper.find('.bio-content').exists()).toBe(true)
      expect(wrapper.find('.bio-text').exists()).toBe(true)
    })

    it('should render a bio header', () => {
      expect(wrapper.find('.bio-header').exists()).toBe(true)
      expect(wrapper.find('.bio-title').text()).toBe('Biography')
    })
  })

  describe('place links', () => {
    const links: MapPlaceLink[] = [
      { name: 'Living Quarters', locationId: 'loc1' },
      { name: 'Reactor', locationId: 'loc2' },
    ]
    const bioWithPlaces = 'John sleeps in the Living Quarters and works at the Reactor.'

    it('should NOT render place links when placeLinks is empty', () => {
      ctx.dweller = ref({ first_name: 'John', bio: bioWithPlaces } as unknown as Dweller) as never
      ctx.vaultId = ref('v1') as never
      ctx.placeLinks = ref([]) as never
      wrapper = mountWithDwellerContext(DwellerBio, { context: ctx })
      expect(wrapper.find('.bio-place-link').exists()).toBe(false)
    })

    it('should NOT render place links when vaultId is missing', () => {
      ctx.dweller = ref({ first_name: 'John', bio: bioWithPlaces } as unknown as Dweller) as never
      ctx.vaultId = ref('') as never
      ctx.placeLinks = ref(links) as never
      wrapper = mountWithDwellerContext(DwellerBio, { context: ctx })
      expect(wrapper.find('.bio-place-link').exists()).toBe(false)
    })

    it('should render a link for each place with correct href', () => {
      ctx.dweller = ref({ first_name: 'John', bio: bioWithPlaces } as unknown as Dweller) as never
      ctx.vaultId = ref('v1') as never
      ctx.placeLinks = ref(links) as never
      wrapper = mountWithDwellerContext(DwellerBio, { context: ctx })
      const anchors = wrapper.findAll('.bio-place-link')
      expect(anchors).toHaveLength(2)
      expect(anchors[0].attributes('href')).toBe('/vault/v1/map?place=loc1')
      expect(anchors[1].attributes('href')).toBe('/vault/v1/map?place=loc2')
    })

    it('should render the place name as link text', () => {
      ctx.dweller = ref({ first_name: 'John', bio: bioWithPlaces } as unknown as Dweller) as never
      ctx.vaultId = ref('v1') as never
      ctx.placeLinks = ref(links) as never
      wrapper = mountWithDwellerContext(DwellerBio, { context: ctx })
      expect(wrapper.find('.bio-place-link').text()).toContain('Living Quarters')
    })
  })
})
