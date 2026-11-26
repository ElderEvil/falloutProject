import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import { createRouterMock } from '../../helpers/mocks'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import MarkerDetailModal from '@/modules/map/components/MarkerDetailModal.vue'
import SupplySliders from '@/modules/progression/components/party/SupplySliders.vue'
import { useMapStore } from '@/modules/map/stores/map'
import { createLocation, createVaultMarker } from '../../helpers/mapFixtures'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import type {
  ExpeditionSiteMarkerRead,
  WastelandLocationWithDwellers,
} from '@/modules/map/models/map'

// Mock vue-router
const mockPush = vi.hoisted(() => vi.fn())
vi.mock('vue-router', () =>
  createRouterMock({ params: { id: 'vault-1' }, query: {}, push: mockPush })
)

const TELEPORT = { template: '<div><slot /></div>' }

function loc(overrides: Partial<WastelandLocationWithDwellers> = {}) {
  return createLocation({
    id: 'loc-1',
    name: 'Megaton',
    normalized_name: 'megaton',
    type: 'origin',
    description: 'A town built around an unexploded atomic bomb.',
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
  })
}

function mountModal(props: Record<string, unknown> = {}) {
  return mount(MarkerDetailModal, {
    props: { modelValue: true, location: null, vaultMarker: null, ...props },
    global: { stubs: { Teleport: TELEPORT } },
  })
}

const findButton = (wrapper: ReturnType<typeof mountModal>, label: string) =>
  wrapper.findAll('button').find((b) => b.text().includes(label))

beforeEach(() => {
  setActivePinia(createPinia())
  mockPush.mockClear()
})

describe('MarkerDetailModal', () => {
  describe('Location marker display', () => {
    it.each([
      [true, true],
      [false, false],
    ])('renders the dialog only when modelValue=%s', (modelValue, open) => {
      expect(mountModal({ modelValue, location: loc() }).find('[role="dialog"]').exists()).toBe(
        open
      )
    })

    it('renders the place name, badge, description, coordinates and linked dwellers', () => {
      const wrapper = mountModal({ location: loc() })
      expect(wrapper.text()).toContain('Megaton')
      expect(wrapper.text()).toContain('origin')
      expect(wrapper.text()).toContain('A town built around an unexploded atomic bomb')
      expect(wrapper.text()).toContain('MAP COORDINATES')
      expect(wrapper.text()).toContain('50, 50')
      expect(wrapper.text()).toContain('KNOWN DWELLERS')
      expect(wrapper.text()).toContain('Linked Dwellers')

      const buttons = wrapper.findAll('button.dweller-entry')
      expect(buttons).toHaveLength(2)
      expect(buttons[0].text()).toContain('John Doe')
      expect(buttons[1].text()).toContain('Jane')
    })

    it('should render the site-type group when the catalog has it', () => {
      useMapStore().placeGroups = [
        {
          key: 'gas_station',
          label: 'Gas Station',
          icon: 'mdi:gas-station',
          risk: 'low',
          description: 'A roadside fuel stop.',
        },
      ]
      const wrapper = mountModal({ location: loc({ group_key: 'gas_station' }) })
      expect(wrapper.text()).toContain('Gas Station')
      expect(wrapper.text()).toContain('Low risk')
    })

    it('lists linked dwellers as keyboard-operable buttons', () => {
      const wrapper = mountModal({ location: loc() })
      const buttons = wrapper.findAll('button.dweller-entry')
      expect(buttons).toHaveLength(2)
      expect(buttons[0].text()).toContain('John Doe')
      expect(buttons[1].text()).toContain('Jane')
      expect(wrapper.text()).toContain('Linked Dwellers')
    })
  })

  describe('Vault marker display', () => {
    it('renders the vault record and explains that a signal is not a destination', () => {
      const wrapper = mountModal({
        location: null,
        vaultMarker: createVaultMarker({
          description: 'A weak carrier wave out of the north.',
        }),
      })
      expect(wrapper.text()).toContain('Vault 88')
      expect(wrapper.text()).toContain('A weak carrier wave out of the north.')
      expect(wrapper.text()).toContain('vault')
      expect(wrapper.text()).toContain('No overseer is recorded')
      expect(wrapper.text()).toContain("vault's raid board")
      expect(wrapper.text()).not.toContain('Linked Dwellers')
    })
  })

  describe('Dweller navigation', () => {
    it('closes the modal and pushes the dweller route on dweller click', async () => {
      const wrapper = mountModal({ location: loc() })
      ;(wrapper.vm as unknown as { goToDweller: (id: string) => void }).goToDweller('dweller-1')
      await wrapper.vm.$nextTick()

      expect(mockPush).toHaveBeenCalledWith('/vault/vault-1/dwellers/dweller-1')
      expect(wrapper.emitted('update:modelValue')![0][0]).toBe(false)
    })
  })

  describe('Empty/missing dwellers (failure case)', () => {
    it('should NOT render dweller section when dwellers array is empty', () => {
      expect(mountModal({ location: loc({ dwellers: [] }) }).text()).not.toContain(
        'Linked Dwellers'
      )
    })

    it('should show fallback description when location description is null', () => {
      expect(mountModal({ location: loc({ description: null }) }).text()).toContain(
        'No description available'
      )
    })
  })

  describe('Locked location placeholder', () => {
    it('should show the locked placeholder with contact-only dwellers', () => {
      const wrapper = mountModal({ location: loc({ is_unlocked: false }) })
      expect(wrapper.text()).toContain('Unknown Location')
      expect(wrapper.text()).toContain(
        'Chat with a dweller who has been here to uncover this place.'
      )
      expect(wrapper.text()).toContain('John Doe')
      expect(wrapper.findAll('button.dweller-contact')).toHaveLength(2)
      expect(wrapper.text()).not.toContain('origin')
      expect(wrapper.text()).not.toContain('Dispatch')
    })

    it('opens a linked dweller chat from a locked location', async () => {
      const wrapper = mountModal({ location: loc({ is_unlocked: false }) })
      await wrapper.find('button.dweller-contact').trigger('click')

      // Chat opens as a global modal via ?chat= on the map route; the marker
      // modal closes first so the two dialogs do not stack.
      expect(mockPush).toHaveBeenCalledWith({ query: { chat: 'dweller-1' } })
      expect(wrapper.emitted('update:modelValue')![0][0]).toBe(false)
    })

    it('should NOT show locked placeholder when location is unlocked', () => {
      const wrapper = mountModal({ location: loc({ is_unlocked: true }) })
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

    function mountWithClearState(
      clearState: unknown,
      overrides: Partial<WastelandLocationWithDwellers> = {}
    ) {
      return mountModal({ location: loc({ clear_state: clearState, ...overrides }) })
    }

    it('renders no clear status without clear_state', () => {
      const text = mountWithClearState(null).text()
      expect(text).not.toContain('CLEAR STATUS')
      expect(text).not.toContain('CLEARED')
      expect(text).not.toContain('Dispatch')
    })

    it('shows a Dispatch button for a clearable, not-yet-cleared point', () => {
      const wrapper = mountWithClearState(clearableState)
      expect(wrapper.text()).toContain('CLEAR STATUS')
      expect(wrapper.text()).toContain('UNCLAIMED')
      expect(wrapper.text()).toContain('Tier 2')
      expect(findButton(wrapper, 'Dispatch')).toBeDefined()
      expect(wrapper.text()).not.toContain('CLEARED')
    })

    it('shows the signature roll, incidental drops and base XP per survivor', () => {
      const text = mountWithClearState({
        ...clearableState,
        xp_per_survivor: 34,
        loot_preview: [
          {
            item_type: 'junk',
            rarity: 'common',
            junk_types: ['adhesive'],
            weapon_types: [],
            signature: true,
          },
          {
            item_type: 'junk',
            rarity: 'common',
            junk_types: ['steel', 'leather'],
            weapon_types: [],
            signature: false,
          },
          {
            item_type: 'outfit',
            rarity: 'common',
            junk_types: [],
            weapon_types: [],
            signature: false,
          },
        ],
      }).text()
      expect(text).toContain('Signature roll: Adhesive')
      expect(text).toContain('Also rolls: Steel / Leather, Outfit')
      expect(text).toContain('Base XP per survivor: 34')
    })

    it('hides dispatch and explains while a party is en route', () => {
      const wrapper = mountWithClearState(clearableState, { dispatch_in_progress: true })
      expect(findButton(wrapper, 'Dispatch')).toBeUndefined()
      expect(wrapper.text()).toContain('Party en route')
    })

    it('explains an en-route party at a salvage site, where clear_state is null', () => {
      const wrapper = mountWithClearState(null, { dispatch_in_progress: true, action: 'salvage' })
      expect(wrapper.text()).toContain('Party en route')
      expect(
        wrapper.findAll('button').filter((b) => /Dispatch|Search/.test(b.text()))
      ).toHaveLength(0)
    })

    it('offers Search with a one-dweller party for a salvage point', () => {
      const wrapper = mountModal({
        location: loc({ action: 'salvage' }),
        dwellers: [],
        maxPartySize: 3,
      })
      expect(wrapper.text()).toContain('SEND A SCAVENGER')
      expect(findButton(wrapper, 'Search')).toBeDefined()
      expect(wrapper.text()).not.toContain('Dispatch')
    })

    it('keeps the dispatch footer on one row like the pre-wrapper layout', () => {
      const footer = mountWithClearState(clearableState).find('[data-slot="dialog-footer"]')
      expect(footer.attributes('class')).toContain('flex-row')
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
        expect(findButton(wrapper, 'Dispatch')).toBeUndefined()

        await vi.advanceTimersByTimeAsync(5000)

        expect(wrapper.text()).not.toContain('Re-clear available')
        expect(findButton(wrapper, 'Dispatch')).toBeDefined()
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
      expect(findButton(wrapper, 'Dispatch')).toBeDefined()
    })

    it('emits dispatch when the Dispatch button is clicked', async () => {
      const wrapper = mountModal({
        location: loc({ clear_state: clearableState }),
        dwellers: [
          { id: 'dweller-1', first_name: 'Ada', last_name: null, level: 1, status: 'idle' },
        ] as DwellerShort[],
      })
      await wrapper.find('.dweller-item').trigger('click')
      await findButton(wrapper, 'Dispatch')!.trigger('click')
      expect(wrapper.emitted('dispatch')).toBeTruthy()
    })
  })

  describe('Expedition site display', () => {
    function site(overrides: Partial<ExpeditionSiteMarkerRead> = {}): ExpeditionSiteMarkerRead {
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

    const mountSite = (marker: ExpeditionSiteMarkerRead) => mountModal({ site: marker })

    it('does not render the site section when the site prop is omitted', () => {
      expect(mountModal({ location: null }).text()).not.toContain('EXPEDITION SITE')
    })

    it('renders the site name, flavor, level, room count and coordinates', () => {
      const text = mountSite(site()).text()
      expect(text).toContain('Red Rocket Gas Station')
      expect(text).toContain('A roadside fuel stop with a working pump.')
      expect(text).toContain('MIN DWELLER LEVEL')
      expect(text).toContain('ROOMS')
      expect(text).toContain('60, 70')
    })

    it.each([
      ['READY', {}, ['READY'], ['CLEARED', 'IN PROGRESS']],
      ['IN PROGRESS', { block_reason: 'open' }, ['IN PROGRESS'], []],
      [
        'CLEARED with a cooldown',
        { cleared: true, block_reason: 'cooldown', cooldown_remaining_seconds: 3600 },
        ['CLEARED', 'Cooldown: 1h 0m remaining'],
        [],
      ],
      [
        'READY for a cooldown-only site that was not cleared',
        { cleared: false, block_reason: 'cooldown', cooldown_remaining_seconds: 3600 },
        ['READY'],
        ['CLEARED', 'CLEAR STATUS'],
      ],
    ])('shows %s status', (_, overrides, present, absent) => {
      const text = mountSite(site(overrides as Partial<ExpeditionSiteMarkerRead>)).text()
      for (const value of present) expect(text).toContain(value)
      for (const value of absent) expect(text).not.toContain(value)
    })

    it('advances the site cooldown countdown while the modal stays open', async () => {
      vi.useFakeTimers()
      try {
        const wrapper = mountSite(
          site({ cleared: true, block_reason: 'cooldown', cooldown_remaining_seconds: 5 })
        )
        expect(wrapper.text()).toContain('Cooldown:')

        await vi.advanceTimersByTimeAsync(5000)

        expect(wrapper.text()).not.toContain('Cooldown:')
      } finally {
        vi.useRealTimers()
      }
    })

    it('does not offer a Dispatch or Enter action for sites', () => {
      const buttons = mountSite(site())
        .findAll('button')
        .filter((b) => /Dispatch|Enter/.test(b.text()))
      expect(buttons).toHaveLength(0)
    })
  })

  describe('Send-team section (issue 772 phase 2)', () => {
    const clearableState = {
      clearable: true,
      cleared: false,
      clear_count: 0,
      tier: 2,
      time_remaining_seconds: 0,
      loot_table: 'raider_camp_loot',
    }

    const candidates: DwellerShort[] = [
      { id: 'dweller-1', first_name: 'Ada', last_name: 'Lovelace', level: 3, status: 'idle' },
      { id: 'dweller-2', first_name: 'Max', last_name: null, level: 1, status: 'idle' },
    ] as DwellerShort[]

    function mountActionable(overrides: Record<string, unknown> = {}) {
      return mountModal({
        location: loc({ clear_state: clearableState }),
        dwellers: candidates,
        maxPartySize: 3,
        maxStimpaks: 8,
        maxRadaways: 4,
        ...overrides,
      })
    }

    it('renders the party slots, dweller list and supply sliders when actionable', () => {
      const wrapper = mountActionable()
      expect(wrapper.text()).toContain('SEND TEAM')
      expect(wrapper.find('.party-slots').exists()).toBe(true)
      expect(wrapper.find('.available-dwellers').exists()).toBe(true)
      expect(wrapper.findAllComponents(SupplySliders)).toHaveLength(1)
      expect(wrapper.find('.dweller-item').text()).toContain('Ada Lovelace')
    })

    it('pre-fills the suggested 5/5 dispatch loadout, clamped to vault stock', () => {
      // mountActionable passes maxStimpaks: 8, maxRadaways: 4.
      const sliders = mountActionable().findComponent(SupplySliders)
      expect(sliders.props('selectedStimpaks')).toBe(5)
      expect(sliders.props('selectedRadaways')).toBe(4)
    })

    it.each([
      [
        'while the re-clear cooldown runs',
        {
          location: loc({
            clear_state: {
              ...clearableState,
              cleared: true,
              clear_count: 1,
              time_remaining_seconds: 3600,
            },
          }),
        },
      ],
      ['for a non-clearable location', { location: loc() }],
    ])('hides the section and confirm %s', (_, overrides) => {
      const wrapper = mountActionable(overrides)
      expect(wrapper.find('.party-slots').exists()).toBe(false)
      expect(findButton(wrapper, 'Dispatch')).toBeUndefined()
    })

    it('emits dispatch with the selected team and supplies on confirm', async () => {
      const wrapper = mountActionable()
      await wrapper.find('.dweller-item').trigger('click')
      wrapper.findComponent(SupplySliders).vm.$emit('update:stimpaks', [3])
      wrapper.findComponent(SupplySliders).vm.$emit('update:radaways', [1])
      await wrapper.vm.$nextTick()
      await findButton(wrapper, 'Dispatch')!.trigger('click')

      expect(wrapper.emitted('dispatch')).toEqual([
        [{ dwellerIds: ['dweller-1'], supplies: { stimpaks: 3, radaways: 1 }, purpose: 'clear' }],
      ])
    })

    it('disables the confirm until a dweller is selected', async () => {
      const wrapper = mountActionable()
      expect(findButton(wrapper, 'Dispatch')!.attributes('disabled')).toBeDefined()

      await wrapper.find('.dweller-item').trigger('click')

      expect(findButton(wrapper, 'Dispatch')!.attributes('disabled')).toBeUndefined()
    })

    it('closes the modal from Cancel without dispatching', async () => {
      const wrapper = mountActionable()
      await findButton(wrapper, 'Cancel')!.trigger('click')
      expect(wrapper.emitted('dispatch')).toBeFalsy()
      expect(wrapper.emitted('update:modelValue')![0][0]).toBe(false)
    })
  })

  describe('Caravan section (issue 1493)', () => {
    const caravanState = {
      material: 'scrap',
      band: [2, 3],
      caps_cost: 150,
      party_cap: 2,
      cooldown_remaining_seconds: 0,
      cooldown_total_seconds: 86400,
      refusal_reason: null as string | null,
    }

    function mountTrade(overrides: Partial<WastelandLocationWithDwellers> = {}) {
      return mountModal({
        location: loc({ action: 'trade', caravan: caravanState, ...overrides }),
        dwellers: [
          {
            dweller_id: 'dweller-1',
            first_name: 'John',
            last_name: 'Doe',
            relation: 'visited',
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
        maxPartySize: 3,
        maxStimpaks: 8,
        maxRadaways: 4,
      })
    }

    it('shows the shipment, the flat fee and the caravan action', () => {
      const text = mountTrade().text()
      expect(text).toContain('CARAVAN')
      expect(text).toContain('Scrap')
      expect(text).toContain('150 caps')
      expect(text).toContain('SEND A CARAVAN')
      expect(text).not.toContain('SEND TEAM')
    })

    it('drops the supplies sliders a caravan cannot carry and caps the party at the payload', () => {
      const wrapper = mountTrade()
      expect(wrapper.findAllComponents(SupplySliders)).toHaveLength(0)
      expect(wrapper.text()).toContain('2')
    })

    it('emits trade as the purpose', async () => {
      const wrapper = mountTrade()
      await wrapper.find('.dweller-item').trigger('click')
      await findButton(wrapper, 'Send caravan')!.trigger('click')
      expect(wrapper.emitted('dispatch')![0][0]).toMatchObject({ purpose: 'trade' })
    })

    it('offers no party section while the settlement is cooling down, and says why', () => {
      const text = mountTrade({
        action: 'none',
        caravan: {
          ...caravanState,
          cooldown_remaining_seconds: 3600,
          refusal_reason: 'No caravan ready yet',
        },
      }).text()
      expect(text).toContain('Next caravan')
      expect(text).toContain('1h')
      expect(text).not.toContain('SEND A CARAVAN')
    })

    it('prints a readable badge instead of the raw marker type', () => {
      const text = mountTrade({ type: 'visited' }).text()
      expect(text).toContain('Visited')
      expect(text).not.toContain('home_vault')
      expect(text).not.toContain('discovery')
    })
  })
})
