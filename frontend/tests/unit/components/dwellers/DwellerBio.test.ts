import { describe, it, expect } from 'vite-plus/test'
import { ref } from 'vue'
import DwellerBio from '@/modules/dwellers/components/DwellerBio.vue'
import {
  createMockDwellerDetailContext,
  mountWithDwellerContext,
} from '../../helpers/dwellerDetailContext'
import type { Dweller, MapPlaceLink } from '@/modules/dwellers/models/dweller'
import type { DwellerDetailContext } from '@/modules/dwellers/components/DwellerDetailContext'

const BIO = 'John is a vault dweller.'

type BioOptions = {
  vaultId?: string
  placeLinks?: MapPlaceLink[]
  context?: Partial<DwellerDetailContext>
}

const mountBio = (
  dweller: Partial<Dweller> = { first_name: 'John', bio: null },
  opts: BioOptions = {}
) => {
  const ctx = Object.assign(createMockDwellerDetailContext(), opts.context ?? {})
  ctx.dweller = ref({ ...dweller } as unknown as Dweller)
  ctx.vaultId = ref(opts.vaultId ?? 'v1') as never
  ctx.placeLinks = ref<MapPlaceLink[]>(opts.placeLinks ?? []) as never
  return { wrapper: mountWithDwellerContext(DwellerBio, { context: ctx }), ctx }
}

describe('DwellerBio', () => {
  describe('generate button', () => {
    it.each([
      ['a missing bio', null],
      ['an empty bio', ''],
    ])('renders exactly one generate action for %s', (name, bio) => {
      const { wrapper } = mountBio({ first_name: 'John', bio })

      expect(wrapper.findAll('.generate-button')).toHaveLength(1)
      expect(wrapper.find('.generate-button').text()).toContain('Generate biography')
      expect(wrapper.find('.extend-bio-button').exists()).toBe(false)
    })

    it('regenerates or extends an existing bio through the shared actions', async () => {
      const { wrapper, ctx } = mountBio({ first_name: 'John', bio: BIO })

      expect(wrapper.find('.generate-button').text()).toContain('Regenerate biography')
      expect(wrapper.find('.extend-bio-button').text()).toContain('Extend biography')
      await wrapper.find('.generate-button').trigger('click')

      expect(ctx.actions.generateBio).toHaveBeenCalledOnce()
    })

    it.each([true, false])('reflects isAnyGenerating=%s on the button', (generating) => {
      const { wrapper } = mountBio(undefined, {
        context: { isAnyGenerating: ref(generating) as never },
      })

      expect(wrapper.find('.generate-button').attributes('disabled') !== undefined).toBe(generating)
    })

    it('spins the icon while the bio is generating', () => {
      const { wrapper } = mountBio(undefined, { context: { generatingBio: ref(true) as never } })

      const svg = wrapper.find('.generate-button svg')
      expect(svg.exists()).toBe(true)
      expect(svg.classes()).toContain('animate-spin')
    })

    it('explains what the generate button does', () => {
      // Reka renders TooltipContent only when open and teleported; stub it inline so the
      // tooltip text (the behavioral contract) is assertable without hover timers.
      const ctx = createMockDwellerDetailContext()
      ctx.dweller = ref({ first_name: 'John', bio: null } as unknown as Dweller)
      const wrapper = mountWithDwellerContext(DwellerBio, {
        context: ctx,
        global: { stubs: { TooltipContent: { template: '<div><slot /></div>' } } },
      })

      expect(wrapper.text()).toContain("Creates or replaces this dweller's biography")
    })
  })

  describe('bio content', () => {
    it('renders an existing bio inside the bios block', () => {
      const { wrapper } = mountBio({ first_name: 'John', bio: BIO })

      expect(wrapper.text()).toContain(BIO)
      expect(wrapper.find('.bio-content').exists()).toBe(true)
      expect(wrapper.find('.bio-text').exists()).toBe(true)
      expect(wrapper.find('.bio-header').exists()).toBe(true)
      expect(wrapper.find('.panel-title').exists()).toBe(false)
    })

    it.each(['John', 'Sarah'])('personalizes the empty state for %s', (firstName) => {
      const { wrapper } = mountBio({ first_name: firstName, bio: null })

      expect(wrapper.text()).toContain(`No biography available for ${firstName} yet`)
      expect(wrapper.text()).toContain('Click "Generate" to create a unique backstory!')
    })
  })

  describe('sectioned formatting', () => {
    it('falls back to a single expanded origin section when only bio text exists', () => {
      const { wrapper } = mountBio({ first_name: 'John', bio: BIO })

      const sections = wrapper.findAll('.bio-section')
      expect(sections).toHaveLength(1)
      expect(sections[0].classes()).toContain('bio-section-origin')
      expect(sections[0].text()).toContain('ORIGIN')
      expect(wrapper.find('.bio-section-dashes').exists()).toBe(true)
      expect(wrapper.find('details.bio-section-origin').exists()).toBe(false)
    })

    it('groups structured entries into labelled sections', () => {
      const { wrapper } = mountBio({
        first_name: 'John',
        bio: 'Born in Megaton.',
        bio_entries: [
          { source: 'template', text: 'Born in Megaton.' },
          { source: 'exploration', text: 'Visited Rivet City.' },
          { source: 'family', text: 'Married Jane.' },
        ],
      } as Partial<Dweller>)

      expect(wrapper.findAll('.bio-section').map((s) => s.classes()[1])).toEqual([
        'bio-section-origin',
        'bio-section-exploration',
        'bio-section-family',
      ])
      expect(wrapper.text()).toContain('ORIGIN')
      expect(wrapper.text()).toContain('FIELD LOG')
      expect(wrapper.text()).toContain('FAMILY RECORD')
    })

    it('keeps entry order within a section', () => {
      const { wrapper } = mountBio({
        first_name: 'John',
        bio: 'Born in Megaton.',
        bio_entries: [
          { source: 'exploration', text: 'Visited Rivet City.' },
          { source: 'exploration', text: 'Visited Diamond City.' },
        ],
      } as Partial<Dweller>)

      expect(wrapper.findAll('.bio-entry-text').map((node) => node.text())).toEqual([
        'Visited Rivet City.',
        'Visited Diamond City.',
      ])
    })

    it.each([
      [2, '2 entries', ['Visited Rivet City.', 'Visited Diamond City.'], null],
      [1, '1 entry', ['Visited Rivet City.'], '1 entries'],
    ] as const)(
      'folds a %i-entry field log behind a count summary',
      (_count, summary, entries, badPlural) => {
        const { wrapper } = mountBio({
          first_name: 'John',
          bio: 'Born in Megaton.',
          bio_entries: [
            { source: 'template', text: 'Born in Megaton.' },
            ...entries.map((text) => ({ source: 'exploration', text })),
          ],
        } as Partial<Dweller>)

        const fieldLog = wrapper.find('details.bio-section-exploration')
        expect(fieldLog.find('summary').text()).toContain('FIELD LOG')
        expect(fieldLog.find('summary').text()).toContain(summary)
        if (badPlural) expect(fieldLog.find('summary').text()).not.toContain(badPlural)
        expect(fieldLog.attributes('open')).toBeUndefined()

        // Entries stay mounted behind the fold, so expanding needs no refetch.
        expect(fieldLog.findAll('.bio-entry-text').map((node) => node.text())).toEqual([...entries])
      }
    )

    it('skips empty entries and sections', () => {
      const { wrapper } = mountBio({
        first_name: 'John',
        bio: 'Born in Megaton.',
        bio_entries: [
          { source: 'template', text: 'Born in Megaton.' },
          { source: 'dialogue', text: '   ' },
        ],
      } as Partial<Dweller>)

      expect(wrapper.findAll('.bio-section')).toHaveLength(1)
      expect(wrapper.text()).not.toContain('TRANSMISSION LOG')
    })

    it('shows unknown sources under a fallback section instead of dropping them', () => {
      const { wrapper } = mountBio({
        first_name: 'John',
        bio: 'Born in Megaton.',
        bio_entries: [
          { source: 'template', text: 'Born in Megaton.' },
          { source: 'trading', text: 'Sold a weapon at the Trading Post.' },
        ],
      } as Partial<Dweller>)

      expect(wrapper.text()).toContain('RECORD')
      expect(wrapper.text()).toContain('Sold a weapon at the Trading Post.')
    })

    it('gives earned team service its own collapsible section', () => {
      const { wrapper } = mountBio({
        first_name: 'John',
        bio: 'Born in Megaton.',
        bio_entries: [
          { source: 'template', text: 'Born in Megaton.' },
          { source: 'hazard', text: "Took a place on the vault's fire team after 3 callouts." },
        ],
      } as Partial<Dweller>)

      const service = wrapper.find('details.bio-section-service')
      expect(service.exists()).toBe(true)
      expect(service.text()).toContain('SERVICE RECORD')
      expect(service.text()).toContain('fire team')
      expect(wrapper.find('.bio-section-other').exists()).toBe(false)
    })

    it('linkifies places inside entries', () => {
      const { wrapper } = mountBio(
        {
          first_name: 'John',
          bio: 'Born in Megaton.',
          bio_entries: [{ source: 'exploration', text: 'Visited Rivet City.' }],
        } as Partial<Dweller>,
        { placeLinks: [{ name: 'Rivet City', locationId: 'loc9' }] }
      )

      const anchor = wrapper.find('.bio-place-link')
      expect(anchor.text()).toBe('Rivet City')
      expect(anchor.attributes('href')).toBe('/vault/v1/map?place=loc9')
    })
  })

  it('renders backend-authored dweller family links', () => {
    const { wrapper } = mountBio({
      first_name: 'Lucy',
      bio: 'Searching for <a href="/vault/v1/dwellers/h1" class="dweller-link">Hank</a>.',
      bio_entries: [
        {
          source: 'template',
          text: 'Searching for <a href="/vault/v1/dwellers/h1" class="dweller-link">Hank</a>.',
        },
      ],
    } as Partial<Dweller>)

    const anchor = wrapper.find('.dweller-link')
    expect(anchor.text()).toBe('Hank')
    expect(anchor.attributes('href')).toBe('/vault/v1/dwellers/h1')
  })

  describe('place links', () => {
    const links: MapPlaceLink[] = [
      { name: 'Living Quarters', locationId: 'loc1' },
      { name: 'Reactor', locationId: 'loc2' },
    ]
    const bioWithPlaces = 'John sleeps in the Living Quarters and works at the Reactor.'

    it.each([
      ['no place links are known', { placeLinks: [] }],
      ['the vault id is missing', { placeLinks: links, vaultId: '' }],
    ] as const)('renders no place link when %s', (_name, opts) => {
      const { wrapper } = mountBio({ first_name: 'John', bio: bioWithPlaces }, opts as BioOptions)

      expect(wrapper.find('.bio-place-link').exists()).toBe(false)
    })

    it('links each known place with its name and map href', () => {
      const { wrapper } = mountBio(
        { first_name: 'John', bio: bioWithPlaces },
        { placeLinks: links }
      )

      const anchors = wrapper.findAll('.bio-place-link')
      expect(anchors).toHaveLength(2)
      expect(anchors[0].text()).toContain('Living Quarters')
      expect(anchors[0].attributes('href')).toBe('/vault/v1/map?place=loc1')
      expect(anchors[1].attributes('href')).toBe('/vault/v1/map?place=loc2')
    })
  })
})
