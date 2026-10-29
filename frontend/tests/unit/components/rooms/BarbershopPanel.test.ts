import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises } from '@vue/test-utils'
import { mountWithSetup } from '../../helpers/mountWithSetup'
import BarbershopPanel from '@/modules/rooms/components/BarbershopPanel.vue'
import { barbershopApi } from '@/modules/rooms/api/barbershop'
import type { BarbershopChangeResponse, BarbershopStatus } from '@/modules/rooms/models/barbershop'
import type { Room } from '@/modules/rooms/models/room'
import type { Dweller, DwellerShort } from '@/modules/dwellers/models/dweller'

enableAutoUnmount(afterEach)

vi.mock('@/modules/rooms/api/barbershop', () => ({
  barbershopApi: { getStatus: vi.fn(), changeAppearance: vi.fn() },
}))

vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({ token: 'test-token' }),
}))

const store = vi.hoisted(() => ({
  filter: {
    allDwellers: [] as DwellerShort[],
    dwellers: [] as DwellerShort[],
    detailedDwellers: {} as Record<string, Dweller>,
    fetchDwellerDetails: vi.fn(),
    fetchAllDwellers: vi.fn(),
  },
  management: { assignDwellerToRoom: vi.fn(), unassignDwellerFromRoom: vi.fn() },
  generation: {
    generateDwellerPortrait: vi.fn(),
  },
}))

vi.mock('@/modules/dwellers/stores/dweller', async () => {
  const { reactive } = await import('vue')
  store.filter = reactive(store.filter)
  return {
    useDwellerStore: () => ({
      filter: store.filter,
      generation: store.generation,
      management: store.management,
    }),
  }
})

const BARBER_ID = '99999999-9999-4999-8999-999999999999'
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
    size: 6,
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
    room_id: 'room-1',
    age_group: 'adult',
    gender: 'male',
    rarity: 'common',
    is_default_portrait: true,
    visual_attributes: { race: 'human', skin_tone: 'Pale', hair_color: 'Blonde' },
    ...overrides,
  }) as DwellerShort

const barberDweller = (): DwellerShort =>
  dweller({
    id: BARBER_ID,
    first_name: 'Boris',
    last_name: 'Barber',
    gender: 'female',
  })

const status = (overrides: Partial<BarbershopStatus> = {}): BarbershopStatus => ({
  room_id: 'room-1',
  built: true,
  staffed: true,
  fee: 350,
  skin_fee: 200,
  hair_fee: 150,
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
  fee: 200,
  remaining_caps: 800,
  ...overrides,
})

const mountPanel = (clients: DwellerShort[] = [dweller()], barber = barberDweller()) => {
  const assigned = [barber, ...clients]
  store.filter.allDwellers = [...assigned]
  store.filter.dwellers = [...assigned]
  return mountWithSetup(BarbershopPanel, {
    props: {
      vaultId: 'vault-1',
      room: room(),
      assignedDwellers: assigned,
    },
  })
}

const portraitSrc = (wrapper: ReturnType<typeof mountWithSetup>): string =>
  wrapper.get('[data-testid="barbershop-portrait"] img').attributes('src') ?? ''

const saveButton = (wrapper: ReturnType<typeof mountWithSetup>) =>
  wrapper.get('[data-testid="barbershop-save"]').element as HTMLButtonElement

describe('BarbershopPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    store.management.assignDwellerToRoom.mockReset()
    store.management.unassignDwellerFromRoom.mockReset()
    store.filter.allDwellers = []
    store.filter.dwellers = []
    store.filter.detailedDwellers = {}
    store.filter.fetchDwellerDetails.mockResolvedValue(null)
    store.filter.fetchAllDwellers.mockImplementation(async () => {
      store.filter.allDwellers = [...store.filter.dwellers]
    })
    store.generation.generateDwellerPortrait.mockResolvedValue(null)
    vi.mocked(barbershopApi.getStatus).mockResolvedValue(status())
  })

  it('shows worker and client slots even when the room is empty', async () => {
    vi.mocked(barbershopApi.getStatus).mockResolvedValue(status({ staffed: false }))
    const wrapper = mountWithSetup(BarbershopPanel, {
      props: { vaultId: 'vault-1', room: room(), assignedDwellers: [] },
    })
    await flushPromises()
    expect(wrapper.get('button[aria-label^="Choose worker"]').text()).toContain('Add worker')
    expect(wrapper.get('button[aria-label^="Choose client"]').text()).toContain('Add client')
  })

  it('assigns a client directly from its slot without also filling the worker slot', async () => {
    const client = dweller({ room_id: null })
    store.filter.dwellers = [client]
    store.management.assignDwellerToRoom.mockResolvedValue({ ...client, room_id: 'room-1' })
    const wrapper = mountWithSetup(BarbershopPanel, {
      props: { vaultId: 'vault-1', room: room(), assignedDwellers: [] },
    })
    await flushPromises()
    await wrapper.get('button[aria-label^="Choose client"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="barbershop-client-option"]').trigger('click')
    await flushPromises()
    expect(store.management.assignDwellerToRoom).toHaveBeenCalledWith(
      ADULT_ID,
      'room-1',
      'test-token'
    )
    expect(wrapper.get('[aria-label="Client slot"]').text()).toContain('Ada')
    expect(wrapper.get('button[aria-label^="Choose worker"]').text()).toContain('Add worker')
    expect(wrapper.emitted('changed')).toHaveLength(1)
  })

  it('keeps an empty slot and the picker open when assignment fails', async () => {
    store.filter.dwellers = [dweller({ room_id: null })]
    store.management.assignDwellerToRoom.mockRejectedValueOnce(new Error('Room is full'))
    const wrapper = mountWithSetup(BarbershopPanel, {
      props: { vaultId: 'vault-1', room: room(), assignedDwellers: [] },
    })
    await flushPromises()
    await wrapper.get('button[aria-label^="Choose worker"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="barbershop-barber-option"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('button[aria-label^="Choose worker"]').text()).toContain('Add worker')
    expect(wrapper.get('[role="alert"]').text()).toContain('Room is full')
    expect(wrapper.find('[data-testid="barbershop-barber-option"]').exists()).toBe(true)
    expect(wrapper.emitted('changed')).toBeUndefined()
  })

  it('ignores an assignment completion after switching rooms', async () => {
    const client = dweller({ room_id: null })
    store.filter.dwellers = [client]
    let finish!: (value: Dweller) => void
    store.management.assignDwellerToRoom.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve
        })
    )
    const wrapper = mountWithSetup(BarbershopPanel, {
      props: { vaultId: 'vault-1', room: room(), assignedDwellers: [] },
    })
    await flushPromises()
    await wrapper.get('button[aria-label^="Choose client"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="barbershop-client-option"]').trigger('click')
    await wrapper.setProps({ room: room({ id: 'room-2' }), assignedDwellers: [] })
    finish({ ...client, room_id: 'room-1' } as Dweller)
    await flushPromises()
    expect(wrapper.get('button[aria-label^="Choose client"]').text()).toContain('Add client')
    expect(wrapper.get('button[aria-label^="Choose worker"]').text()).toContain('Add worker')
    expect(wrapper.emitted('changed')).toBeUndefined()
  })

  it('ignores old status after switching rooms', async () => {
    let finish!: (value: BarbershopStatus) => void
    vi.mocked(barbershopApi.getStatus).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve
        })
    )
    const wrapper = mountPanel()
    vi.mocked(barbershopApi.getStatus).mockResolvedValue(
      status({ room_id: 'room-2', vault_caps: 250 })
    )
    await wrapper.setProps({ room: room({ id: 'room-2' }), assignedDwellers: [] })
    await flushPromises()
    finish(status({ vault_caps: 9999 }))
    await flushPromises()
    expect(wrapper.get('[data-testid="barbershop-caps"]').text()).toBe('250')
  })

  it('unassigns a worker without putting the client into the worker slot', async () => {
    store.management.unassignDwellerFromRoom.mockResolvedValue({})
    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.get('button[aria-label="Unassign Boris Barber from Barbershop"]').trigger('click')
    await flushPromises()
    expect(store.management.unassignDwellerFromRoom).toHaveBeenCalledWith(BARBER_ID, 'test-token')
    expect(wrapper.get('button[aria-label^="Choose worker"]').text()).toContain('Add worker')
    expect(wrapper.get('[aria-label="Client slot"]').text()).toContain('Ada')
  })

  it('shows roster-load errors with a retry instead of an empty-picker message', async () => {
    const wrapper = mountPanel()
    await flushPromises()
    store.filter.fetchAllDwellers.mockRejectedValueOnce(new Error('Roster unavailable'))
    await wrapper.get('button[aria-label^="Choose worker"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('Roster unavailable')
    const retry = wrapper.findAll('button').find((button) => button.text() === 'Retry dwellers')!
    await retry.trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.findAll('[data-testid="barbershop-barber-option"]')).toHaveLength(2)
  })

  it('keeps a worker outside the sidebar filter when the visible client is assigned', async () => {
    const worker = barberDweller()
    const client = dweller({ room_id: null })
    store.filter.dwellers = [client]
    store.filter.fetchAllDwellers.mockImplementation(async () => {
      store.filter.allDwellers = [worker, client]
    })
    const wrapper = mountWithSetup(BarbershopPanel, {
      props: { vaultId: 'vault-1', room: room(), assignedDwellers: [] },
    })
    await flushPromises()
    await wrapper.get('button[aria-label^="Choose worker"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="barbershop-barber-option"]').trigger('click')
    await flushPromises()
    await wrapper.setProps({ assignedDwellers: [{ ...client, room_id: 'room-1' }] })
    expect(wrapper.get('[aria-label="Worker slot"]').text()).toContain('Boris')
  })

  it('keeps the worker selected when unassignment is rejected', async () => {
    store.management.unassignDwellerFromRoom.mockRejectedValueOnce(new Error('Worker is busy'))
    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.get('button[aria-label="Unassign Boris Barber from Barbershop"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('Worker is busy')
    expect(wrapper.get('[aria-label="Worker slot"]').text()).toContain('Boris')
    expect(wrapper.emitted('changed')).toBeUndefined()
  })

  it('shows neutral status placeholders until the Barbershop status loads', async () => {
    vi.mocked(barbershopApi.getStatus).mockReturnValue(new Promise<BarbershopStatus>(() => {}))

    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.get('[data-testid="barbershop-staffing"]').text()).toBe('—')
    expect(wrapper.get('[data-testid="barbershop-chair"]').text()).toBe('—')
  })

  it('shows the assignment hint and disables saving while unstaffed', async () => {
    vi.mocked(barbershopApi.getStatus).mockResolvedValue(status({ staffed: false }))

    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.get('[data-testid="barbershop-unstaffed"]').text()).toContain(
      'Assign at least one dweller to the Barbershop first.'
    )
    expect(saveButton(wrapper).disabled).toBe(true)
  })

  it('puts the barber and customer in exclusive chairs and leaves everyone else waiting', async () => {
    const wrapper = mountPanel([
      dweller({ id: ADULT_ID, first_name: 'Ada' }),
      dweller({
        id: ELDER_ID,
        first_name: 'Eve',
        last_name: 'Elder',
        age_group: 'elder',
        gender: 'female',
      }),
    ])
    await flushPromises()

    expect(wrapper.get('[aria-label="Worker slot"]').text()).toContain('Boris')
    expect(wrapper.get('[aria-label="Client slot"]').text()).toContain('Ada')
    expect(wrapper.get('[data-testid="barbershop-waiting-row"]').text()).toContain('Eve Elder')
    expect(
      wrapper
        .find(`[data-testid="barbershop-waiting-row"][data-dweller-id="${BARBER_ID}"]`)
        .exists()
    ).toBe(false)
    expect(
      wrapper.find(`[data-testid="barbershop-waiting-row"][data-dweller-id="${ADULT_ID}"]`).exists()
    ).toBe(false)
  })

  it('never offers the barber as a customer in the waiting room', async () => {
    const wrapper = mountPanel([
      dweller({ id: ADULT_ID, first_name: 'Ada' }),
      dweller({
        id: ELDER_ID,
        first_name: 'Eve',
        last_name: 'Elder',
        age_group: 'elder',
        gender: 'female',
      }),
    ])
    await flushPromises()

    await wrapper.get('button[aria-label^="Choose worker"]').trigger('click')
    await flushPromises()
    await wrapper
      .get(`[data-testid="barbershop-barber-option"][data-dweller-id="${ADULT_ID}"]`)
      .trigger('click')
    await flushPromises()

    expect(wrapper.get('[aria-label="Worker slot"]').text()).toContain('Ada')
    expect(wrapper.get('[aria-label="Client slot"]').text()).toContain('Eve')
    expect(wrapper.get('[data-testid="barbershop-waiting-row"]').text()).toContain('Boris Barber')
    expect(
      wrapper.find(`[data-testid="barbershop-waiting-row"][data-dweller-id="${ADULT_ID}"]`).exists()
    ).toBe(false)
  })

  it('does not allow children, non-humans or the dead into customer chairs', async () => {
    const wrapper = mountPanel([
      dweller({ id: ADULT_ID, first_name: 'Ada' }),
      dweller({ id: CHILD_ID, first_name: 'Kid', age_group: 'child' }),
      dweller({
        id: GHOUL_ID,
        first_name: 'Ghoul',
        visual_attributes: { race: 'ghoul', skin_tone: 'Pale', hair_color: 'Blonde' },
      }),
      dweller({ id: DEAD_ID, first_name: 'Gone', status: 'dead' }),
    ])
    await flushPromises()

    const waitingIds = wrapper
      .findAll('[data-testid="barbershop-waiting-row"]')
      .map((row) => row.attributes('data-dweller-id'))
    expect(waitingIds).not.toContain(CHILD_ID)
    expect(waitingIds).not.toContain(GHOUL_ID)
    expect(waitingIds).not.toContain(DEAD_ID)

    await wrapper.get('button[aria-label^="Choose worker"]').trigger('click')
    await flushPromises()
    const barberIds = wrapper
      .findAll('[data-testid="barbershop-barber-option"]')
      .map((row) => row.attributes('data-dweller-id'))
    expect(barberIds).toContain(GHOUL_ID)
    expect(barberIds).not.toContain(CHILD_ID)
    expect(barberIds).not.toContain(DEAD_ID)
  })

  it('keeps saving disabled until an appearance value actually changes', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    expect(saveButton(wrapper).disabled).toBe(true)
    expect(wrapper.get('[data-testid="barbershop-change-fee"]').text()).toBe('0 caps')
    expect(wrapper.get('[data-testid="barbershop-save"]').text()).toContain('No changes to save')

    await wrapper.get('[data-testid="barbershop-skin-swatch"][data-value="Tan"]').trigger('click')

    expect(saveButton(wrapper).disabled).toBe(false)
    expect(wrapper.get('[data-testid="barbershop-change-fee"]').text()).toBe('200 caps')
    expect(wrapper.get('[data-testid="barbershop-save"]').text()).toContain(
      'Save appearance (200 caps)'
    )
  })

  it('charges hair and combined changes at their separate prices', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    await wrapper.get('[data-testid="barbershop-hair-swatch"][data-value="Black"]').trigger('click')
    expect(wrapper.get('[data-testid="barbershop-change-fee"]').text()).toBe('150 caps')

    await wrapper.get('[data-testid="barbershop-skin-swatch"][data-value="Brown"]').trigger('click')
    expect(wrapper.get('[data-testid="barbershop-change-fee"]').text()).toBe('350 caps')
    expect(wrapper.get('[data-testid="barbershop-save"]').text()).toContain(
      'Save appearance (350 caps)'
    )
  })

  it('saves only the changed skin tone and disables saving afterwards', async () => {
    const updated = dweller({
      visual_attributes: { race: 'human', skin_tone: 'Tan', hair_color: 'Blonde' },
      thumbnail_url:
        '/static/dweller_thumbnails/variants/adult/FOS_Dw_Default_Human_Male_SkinTan_HairBlonde.webp',
    })
    vi.mocked(barbershopApi.changeAppearance).mockResolvedValue(
      changeResponse(updated, { fee: 200, remaining_caps: 800 })
    )

    const wrapper = mountPanel()
    await flushPromises()

    await wrapper.get('[data-testid="barbershop-skin-swatch"][data-value="Tan"]').trigger('click')
    await wrapper.get('[data-testid="barbershop-save"]').trigger('click')
    await flushPromises()

    expect(barbershopApi.changeAppearance).toHaveBeenCalledWith('room-1', ADULT_ID, {
      skin_tone: 'Tan',
      hair_color: 'Blonde',
    })
    expect(wrapper.get('[data-testid="barbershop-caps"]').text()).toBe('800')
    expect(wrapper.get('[data-testid="barbershop-change-fee"]').text()).toBe('0 caps')
    expect(saveButton(wrapper).disabled).toBe(true)
    expect(wrapper.emitted('changed')).toHaveLength(1)
  })

  it('preserves custom art and reports it after a real change', async () => {
    const custom = dweller({
      is_default_portrait: false,
      thumbnail_url: '/static/dweller_images/custom/ada.webp',
    })
    const updated = dweller({
      is_default_portrait: false,
      thumbnail_url: '/static/dweller_images/custom/ada-new.webp',
      visual_attributes: { race: 'human', skin_tone: 'Ebony', hair_color: 'Black' },
    })
    vi.mocked(barbershopApi.changeAppearance).mockResolvedValue(
      changeResponse(updated, { portrait_updated: false, remaining_caps: 650 })
    )

    const wrapper = mountPanel([custom])
    await flushPromises()

    expect(wrapper.text()).toContain('Custom portrait preserved when saving.')

    await wrapper.get('[data-testid="barbershop-skin-swatch"][data-value="Ebony"]').trigger('click')
    await wrapper.get('[data-testid="barbershop-hair-swatch"][data-value="Black"]').trigger('click')
    await wrapper.get('[data-testid="barbershop-save"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="barbershop-caps"]').text()).toBe('650')
    expect(wrapper.emitted('changed')).toHaveLength(1)
    expect(store.filter.allDwellers.find((entry) => entry.id === ADULT_ID)?.thumbnail_url).toBe(
      '/static/dweller_images/custom/ada-new.webp'
    )
    expect(store.filter.detailedDwellers[ADULT_ID]).toEqual(updated)
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
    expect(
      store.filter.allDwellers.find((entry) => entry.id === ADULT_ID)?.is_default_portrait
    ).toBe(false)
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
    expect(store.filter.allDwellers.find((entry) => entry.id === ADULT_ID)?.thumbnail_url).toBe(
      '/static/dweller_images/custom/ada-fresh.webp'
    )
    expect(wrapper.emitted('changed')).toHaveLength(1)
  })
})
