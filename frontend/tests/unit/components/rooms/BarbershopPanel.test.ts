import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { mountWithSetup } from '../../helpers/mountWithSetup'
import BarbershopPanel from '@/modules/rooms/components/BarbershopPanel.vue'
import {
  changeBarbershopAppearance,
  fetchBarbershopStatus,
} from '@/modules/rooms/services/barbershopService'
import type { BarbershopChangeResponse, BarbershopStatus } from '@/modules/rooms/models/barbershop'
import type { Room } from '@/modules/rooms/models/room'
import type { Dweller, DwellerShort } from '@/modules/dwellers/models/dweller'

vi.mock('@/modules/rooms/services/barbershopService', () => ({
  fetchBarbershopStatus: vi.fn(),
  changeBarbershopAppearance: vi.fn(),
}))

vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({ token: 'test-token' }),
}))

const store = vi.hoisted(() => ({
  filter: {
    allDwellers: [] as DwellerShort[],
    dwellers: [] as DwellerShort[],
    detailedDwellers: {} as Record<string, Dweller>,
    fetchAllDwellers: vi.fn(),
    fetchDwellerDetails: vi.fn(),
  },
  generation: {
    generateDwellerPortrait: vi.fn(),
  },
}))

vi.mock('@/modules/dwellers/stores/dweller', async () => {
  const { reactive } = await import('vue')
  store.filter = reactive(store.filter)
  return {
    useDwellerStore: () => ({ filter: store.filter, generation: store.generation }),
    isMature: (dweller: { age_group?: string | null }) =>
      dweller.age_group === 'adult' || dweller.age_group === 'elder',
    getDwellerDisplayName: (dweller: { first_name?: string | null; last_name?: string | null }) =>
      [dweller.first_name, dweller.last_name].filter(Boolean).join(' '),
    formatIdentityLabel: (value: string) =>
      value
        .split('_')
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' '),
  }
})

const ADULT_ID = '11111111-1111-4111-8111-111111111111'
const ELDER_ID = '22222222-2222-4222-8222-222222222222'
const CHILD_ID = '33333333-3333-4333-8333-333333333333'
const GHOUL_ID = '44444444-4444-4444-8444-444444444444'
const DEAD_ID = '55555555-5555-4555-8555-555555555555'

const room = (overrides: Partial<Room> = {}): Room =>
  ({
    id: 'room-1',
    name: 'Barbershop',
    category: 'misc.',
    ability: 'charisma',
    tier: 1,
    ...overrides,
  }) as Room

const dweller = (overrides: Partial<DwellerShort> = {}): DwellerShort =>
  ({
    id: ADULT_ID,
    first_name: 'Ada',
    last_name: 'Adult',
    thumbnail_url: '/static/dweller_thumbnails/FOS_Dw_Default_Human_Male.webp',
    level: 5,
    status: 'idle',
    age_group: 'adult',
    gender: 'male',
    rarity: 'common',
    is_default_portrait: true,
    visual_attributes: { race: 'human', skin_tone: 'Pale', hair_color: 'Blonde' },
    ...overrides,
  }) as DwellerShort

const status = (overrides: Partial<BarbershopStatus> = {}): BarbershopStatus => ({
  room_id: 'room-1',
  built: true,
  staffed: true,
  fee: 100,
  vault_caps: 1000,
  skin_tones: ['Pale', 'Tan', 'Brown', 'Ebony'],
  hair_colors: ['blonde', 'brunette', 'black', 'brown', 'red', 'gray'],
  ...overrides,
})

const changeResponse = (
  updated: DwellerShort,
  overrides: Partial<BarbershopChangeResponse> = {}
): BarbershopChangeResponse => ({
  dweller: updated as Dweller,
  portrait_updated: true,
  fee: 100,
  remaining_caps: 900,
  ...overrides,
})

const mountPanel = (dwellers: DwellerShort[] = [dweller()]) => {
  store.filter.allDwellers = dwellers
  return mountWithSetup(BarbershopPanel, {
    props: {
      room: room(),
      vaultId: 'vault-1',
      assignedDwellers: [],
    },
  })
}

const portraitSrc = (wrapper: ReturnType<typeof mountWithSetup>): string =>
  wrapper.get('[data-testid="barbershop-portrait"] img').attributes('src') ?? ''

describe('BarbershopPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    store.filter.allDwellers = []
    store.filter.dwellers = []
    store.filter.detailedDwellers = {}
    store.filter.fetchAllDwellers.mockResolvedValue(undefined)
    store.filter.fetchDwellerDetails.mockResolvedValue(null)
    store.generation.generateDwellerPortrait.mockResolvedValue(null)
    vi.mocked(fetchBarbershopStatus).mockResolvedValue(status())
  })

  it('lists only mature human dwellers and excludes children, non-humans and the dead', async () => {
    const wrapper = mountPanel([
      dweller(),
      dweller({
        id: ELDER_ID,
        first_name: 'Eve',
        last_name: 'Elder',
        age_group: 'elder',
        gender: 'female',
      }),
      dweller({ id: CHILD_ID, first_name: 'Kid', age_group: 'child' }),
      dweller({
        id: GHOUL_ID,
        first_name: 'Ghoul',
        visual_attributes: { race: 'ghoul', skin_tone: 'Pale', hair_color: 'Blonde' },
      }),
      dweller({ id: DEAD_ID, first_name: 'Gone', status: 'dead' }),
    ])
    await flushPromises()

    expect(store.filter.fetchAllDwellers).toHaveBeenCalledWith('vault-1', 'test-token')
    const rows = wrapper.findAll('[data-testid="barbershop-dweller-row"]')
    expect(rows).toHaveLength(2)
    expect(wrapper.text()).toContain('Ada Adult')
    expect(wrapper.text()).toContain('Eve Elder')
    expect(wrapper.text()).not.toContain('Kid')
    expect(wrapper.text()).not.toContain('Ghoul')
    expect(wrapper.text()).not.toContain('Gone')
  })

  it('updates the preview from swatches and saves the exact preset payload', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    expect(portraitSrc(wrapper)).toContain('FOS_Dw_Default_Human_Male_SkinPale_HairBlonde.webp')

    await wrapper.get('[data-testid="barbershop-skin-swatch"][data-value="Tan"]').trigger('click')
    await wrapper.get('[data-testid="barbershop-hair-swatch"][data-value="Black"]').trigger('click')

    expect(portraitSrc(wrapper)).toContain('FOS_Dw_Default_Human_Male_SkinTan_HairBlack.webp')

    vi.mocked(changeBarbershopAppearance).mockResolvedValue(
      changeResponse(
        dweller({
          thumbnail_url:
            '/static/dweller_thumbnails/variants/adult/FOS_Dw_Default_Human_Male_SkinTan_HairBlack.webp',
        })
      )
    )

    await wrapper.get('[data-testid="barbershop-save"]').trigger('click')
    await flushPromises()

    expect(changeBarbershopAppearance).toHaveBeenCalledWith(
      'room-1',
      ADULT_ID,
      { skin_tone: 'Tan', hair_color: 'Black' },
      'test-token'
    )
  })

  it('updates caps, emits changed and reports preserved custom art after a save', async () => {
    const custom = dweller({
      is_default_portrait: false,
      thumbnail_url: '/static/dweller_images/custom/ada.webp',
    })
    const updated = dweller({
      is_default_portrait: false,
      thumbnail_url: '/static/dweller_images/custom/ada-new.webp',
    })
    vi.mocked(fetchBarbershopStatus).mockResolvedValue(status({ vault_caps: 500 }))
    vi.mocked(changeBarbershopAppearance).mockResolvedValue(
      changeResponse(updated, { portrait_updated: false, remaining_caps: 400 })
    )

    const wrapper = mountPanel([custom])
    await flushPromises()

    expect(wrapper.text()).toContain('Custom portrait preserved when saving.')

    await wrapper.get('[data-testid="barbershop-save"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="barbershop-caps"]').text()).toBe('400')
    expect(wrapper.emitted('changed')).toHaveLength(1)
    expect(store.filter.allDwellers[0]?.thumbnail_url).toBe(
      '/static/dweller_images/custom/ada-new.webp'
    )
    expect(store.filter.detailedDwellers[ADULT_ID]).toEqual(updated)
  })

  it('shows the assignment hint and disables saving while unstaffed', async () => {
    vi.mocked(fetchBarbershopStatus).mockResolvedValue(status({ staffed: false }))

    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.get('[data-testid="barbershop-unstaffed"]').text()).toContain(
      'Assign at least one dweller to the Barbershop first.'
    )
    expect(
      (wrapper.get('[data-testid="barbershop-save"]').element as HTMLButtonElement).disabled
    ).toBe(true)
  })

  it('generates a custom portrait for a curated dweller and switches the preview to it', async () => {
    const curated = dweller()
    const generated = {
      ...curated,
      thumbnail_url: '/static/dweller_images/custom/ada-gen.webp',
      is_default_portrait: false,
    } as Dweller
    const refreshed = {
      ...curated,
      thumbnail_url: '/static/dweller_images/custom/ada-fresh.webp',
      is_default_portrait: false,
    } as Dweller

    store.generation.generateDwellerPortrait.mockResolvedValue(generated)
    store.filter.fetchDwellerDetails.mockResolvedValue(refreshed)

    const wrapper = mountPanel([curated])
    await flushPromises()

    const action = wrapper.get('[data-testid="barbershop-regenerate"]')
    expect(action.text()).toContain('Generate custom portrait')

    await action.trigger('click')
    await flushPromises()

    expect(portraitSrc(wrapper)).toContain('ada-fresh.webp?v=1')
    expect(store.filter.allDwellers[0]?.is_default_portrait).toBe(false)
    expect(wrapper.emitted('changed')).toHaveLength(1)
  })

  it('regenerates a custom portrait, refreshes details and cache-busts the preview', async () => {
    const custom = dweller({
      is_default_portrait: false,
      thumbnail_url: '/static/dweller_images/custom/ada.webp',
    })
    const generated = {
      ...custom,
      thumbnail_url: '/static/dweller_images/custom/ada-gen.webp',
    } as Dweller
    const refreshed = {
      ...custom,
      thumbnail_url: '/static/dweller_images/custom/ada-fresh.webp',
    } as Dweller

    store.generation.generateDwellerPortrait.mockResolvedValue(generated)
    store.filter.fetchDwellerDetails.mockImplementation(async (id: string) => {
      store.filter.detailedDwellers[id] = refreshed
      return refreshed
    })

    const wrapper = mountPanel([custom])
    await flushPromises()

    await wrapper.get('[data-testid="barbershop-regenerate"]').trigger('click')
    await flushPromises()

    expect(store.generation.generateDwellerPortrait).toHaveBeenCalledWith(ADULT_ID, 'test-token')
    expect(store.filter.fetchDwellerDetails).toHaveBeenCalledWith(ADULT_ID, 'test-token', true)
    expect(portraitSrc(wrapper)).toContain('ada-fresh.webp?v=1')
    expect(store.filter.allDwellers[0]?.thumbnail_url).toBe(
      '/static/dweller_images/custom/ada-fresh.webp'
    )
    expect(wrapper.emitted('changed')).toHaveLength(1)
  })
})
