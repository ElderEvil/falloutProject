import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import axios from '@/core/plugins/axios'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import RoomAssignmentModal from '@/modules/dwellers/components/modals/RoomAssignmentModal.vue'
import type { Dweller } from '@/modules/dwellers/models/dweller'

vi.mock('@/core/plugins/axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }))
vi.mock('@/core/audio/audioManager', () => ({ audioManager: { play: vi.fn() } }))
const dweller = {
  id: 'dweller-1',
  first_name: 'Martha',
  last_name: 'Dewey',
  room: null,
  status: 'idle',
  age_group: 'adult',
  is_dead: false,
  S: 3,
  P: 4,
  E: 3,
  C: 5,
  I: 8,
  A: 2,
  L: 4,
  outfit: null,
  pet: null,
  identity_modifiers: {},
} as Dweller
const room = (id: string, name: string, ability = 'intelligence') => ({
  id,
  name,
  ability,
  category: 'production',
  tier: 1,
  size: 3,
  size_min: 3,
})
let rooms = [room('lab', 'Science Lab'), room('power', 'Power Generator', 'strength')]
let residents: unknown[] = []
const mountPicker = async (changes: Partial<Dweller> = {}) => {
  const wrapper = mount(RoomAssignmentModal, {
    props: { open: true, vaultId: 'vault-1', dweller: { ...dweller, ...changes } },
    global: {
      stubs: {
        TerminalModal: {
          name: 'TerminalModal',
          template: '<section><slot /><slot name="footer" /></section>',
        },
      },
    },
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  setActivePinia(createPinia())
  useAuthStore().token = 'test-token'
  rooms = [room('lab', 'Science Lab'), room('power', 'Power Generator', 'strength')]
  residents = []
  vi.mocked(axios.get)
    .mockReset()
    .mockImplementation(async (url) => ({
      data: String(url).includes('/rooms/') ? rooms : residents,
    }))
  vi.mocked(axios.post)
    .mockReset()
    .mockResolvedValue({ data: { ...dweller, room: rooms[0] } })
})

const choiceButtons = (wrapper: Awaited<ReturnType<typeof mountPicker>>) =>
  wrapper.findAll('button[aria-label*=", tier "]')

describe('dweller-first room assignment', () => {
  it('compares effective SPECIAL and requires explicit confirmation before posting', async () => {
    const wrapper = await mountPicker({ outfit: { strength: 7 } as Dweller['outfit'] })
    const choices = choiceButtons(wrapper)
    expect(choices[0].text()).toContain('Power Generator')
    expect(choices[0].text()).toContain('Strength 10')
    expect(choices[0].attributes('aria-pressed')).toBe('false')
    await choices[0].trigger('click')
    expect(choices[0].attributes('aria-pressed')).toBe('true')
    expect(wrapper.text()).toContain('contributes to this room')
    expect(axios.post).not.toHaveBeenCalled()
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'Confirm assignment')!
      .trigger('click')
    await flushPromises()
    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/dwellers/dweller-1/move_to/power',
      null,
      expect.any(Object)
    )
    expect(wrapper.emitted('assigned')).toHaveLength(1)
    expect(wrapper.emitted('update:open')).toEqual([[false]])
  })

  it('explains occupied worker slots without posting', async () => {
    residents = [{ room_id: 'lab' }, { room_id: 'lab' }]
    const wrapper = await mountPicker()
    const lab = choiceButtons(wrapper).find((button) => button.text().includes('Science Lab'))!
    expect(lab.attributes('disabled')).toBeDefined()
    expect(wrapper.find(`#${lab.attributes('aria-describedby')}`).text()).toContain(
      'All worker slots are occupied'
    )
    expect(wrapper.text()).toContain('All worker slots are occupied')
    expect(axios.post).not.toHaveBeenCalled()
  })

  it('offers a youth apprentice slot even when worker slots are full, but blocks a second apprentice', async () => {
    residents = [
      { room_id: 'lab' },
      { room_id: 'lab' },
      { room_id: 'power', apprentice_stat: 'strength' },
    ]
    const wrapper = await mountPicker({ age_group: 'teen' })
    const lab = choiceButtons(wrapper).find((button) => button.text().includes('Science Lab'))!
    expect(lab.attributes('disabled')).toBeUndefined()
    expect(wrapper.text()).toContain('This room already has an apprentice')
    await lab.trigger('click')
    expect(wrapper.text()).toContain('also trains Intelligence')
  })

  it('reports loading failure separately from an empty vault and allows retry', async () => {
    vi.mocked(axios.get).mockRejectedValueOnce(new Error('Network unavailable'))
    const wrapper = await mountPicker()
    expect(wrapper.find('[role="alert"]').text()).toContain('Network unavailable')
    expect(wrapper.text()).not.toContain('No production rooms yet')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'Try again')!
      .trigger('click')
    await flushPromises()
    expect(choiceButtons(wrapper)).toHaveLength(2)
  })

  it('keeps the selected room and specific server restriction after an assignment error', async () => {
    vi.mocked(axios.post).mockRejectedValueOnce({
      response: { data: { detail: 'Not enough population space' } },
    })
    const wrapper = await mountPicker()
    await choiceButtons(wrapper)[0].trigger('click')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'Confirm assignment')!
      .trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toContain('Not enough population space')
    expect(choiceButtons(wrapper)[0].attributes('aria-pressed')).toBe('true')
    expect(wrapper.emitted('assigned')).toBeUndefined()
  })

  it('explains an empty vault and blocks away dwellers', async () => {
    rooms = []
    const empty = await mountPicker()
    expect(empty.text()).toContain('Build one in the vault')
    rooms = [room('lab', 'Science Lab')]
    const away = await mountPicker({ status: 'exploring' })
    expect(away.text()).toContain('away from the vault')
    expect(choiceButtons(away)[0].attributes('disabled')).toBeDefined()
  })
  it.each(['rooms', 'dwellers'])(
    'does not show choices after a superseded %s fetch',
    async (source) => {
      let resolveFirst!: (value: { data: unknown[] }) => void
      let held = false
      vi.mocked(axios.get).mockImplementation(async (url) => {
        const isRooms = String(url).includes('/rooms/')
        if (!held && (source === 'rooms' ? isRooms : !isRooms)) {
          held = true
          return new Promise((resolve) => {
            resolveFirst = resolve
          })
        }
        return { data: isRooms ? rooms : residents }
      })
      const wrapper = await mountPicker()
      if (source === 'rooms') await useRoomStore().fetchRooms('vault-2', 'test-token')
      else await useDwellerStore().filter.fetchAllDwellers('vault-2', 'test-token')
      resolveFirst({ data: source === 'rooms' ? rooms : residents })
      await flushPromises()
      expect(wrapper.find('[role="alert"]').exists()).toBe(true)
      expect(choiceButtons(wrapper)).toHaveLength(0)
    }
  )

  it('blocks shell dismissal while an assignment is pending', async () => {
    let finish!: (value: unknown) => void
    vi.mocked(axios.post).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve
        })
    )
    const wrapper = await mountPicker()
    await choiceButtons(wrapper)[0].trigger('click')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'Confirm assignment')!
      .trigger('click')
    wrapper.findComponent({ name: 'TerminalModal' }).vm.$emit('update:open', false)
    await flushPromises()
    expect(wrapper.emitted('update:open')).toBeUndefined()
    finish({ data: dweller })
    await flushPromises()
    expect(wrapper.emitted('update:open')).toEqual([[false]])
  })
})

it('offers adult storage protection while keeping youth in production', async () => {
  rooms.push({ ...room('storage', 'Storage Room', 'endurance'), category: 'capacity' })
  const adult = await mountPicker()
  const storage = choiceButtons(adult).find((button) => button.text().includes('Storage Room'))!
  expect(storage.text()).toContain('Protection')
  await storage.trigger('click')
  expect(adult.text()).toContain('vault-wide weapon protection')
  expect(adult.text()).toContain('housing space')
  adult.unmount()
  const youth = await mountPicker({ age_group: 'teen' })
  expect(choiceButtons(youth).some((button) => button.text().includes('Storage Room'))).toBe(false)
  youth.unmount()
})
