import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createAxiosMock } from '../../helpers/mocks'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { defineComponent, nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import RoomDwellers from '@/modules/dwellers/components/RoomDwellers.vue'
import { useDwellerFilterStore } from '@/modules/dwellers/stores/dwellerFilter'
import { makeDweller } from '../../helpers/dwellerFixtures'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { TooltipProvider } from '@/core/components/ui/tooltip'
import axios from '@/core/plugins/axios'

vi.mock('@/core/plugins/axios', () => createAxiosMock())

vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    props: ['icon'],
    template: '<span :data-icon="icon" />',
  },
}))

enableAutoUnmount(afterEach)

const alice = makeDweller({
  id: 'd1',
  room_id: 'r1',
  first_name: 'Alice',
  last_name: 'Smith',
  level: 3,
  apprentice_stat: null,
})

const bob = {
  ...alice,
  id: 'd2',
  room_id: 'r2',
  first_name: 'Bob',
  last_name: 'Jones',
}

function setFilteredDwellers(dwellers: Array<Record<string, unknown>>) {
  useDwellerFilterStore().dwellers = dwellers as never
}

const mountDwellers = () =>
  mount(
    defineComponent({
      components: { RoomDwellers, TooltipProvider },
      template:
        '<TooltipProvider :delay-duration="0"><RoomDwellers room-id="r1" /></TooltipProvider>',
    }),
    { attachTo: document.body }
  )

beforeEach(() => {
  setActivePinia(createPinia())
  setFilteredDwellers([alice])
})

it('shows dweller details in an app tooltip on keyboard focus without a browser title', async () => {
  const wrapper = mountDwellers()
  const avatar = wrapper.get('.dweller-avatar')
  expect(avatar.attributes('title')).toBeUndefined()
  await avatar.trigger('focus')
  await vi.waitFor(() =>
    expect(document.querySelector('[role="tooltip"]')?.textContent).toContain('Alice Smith (Lv3)')
  )
  expect(avatar.attributes('draggable')).toBe('true')
})

it.each([
  ['an equipped pet with an image', '/static/pets/dogmeat.webp'],
  ['an equipped pet without an image', null],
] as const)('marks %s on the avatar and in the tooltip', async (_name, image_url) => {
  setFilteredDwellers([{ ...alice, pet: { id: 'pet-1', name: 'Dogmeat', image_url } }])

  const wrapper = mountDwellers()
  const avatar = wrapper.get('.dweller-avatar')
  expect(avatar.attributes('role')).toBe('group')
  expect(avatar.attributes('aria-label')).toBe('Alice Smith (Lv3), pet Dogmeat')
  expect(avatar.find('.dweller-pet-fallback').exists()).toBe(image_url === null)
  expect(avatar.find('.dweller-pet img').exists()).toBe(image_url !== null)
  if (image_url !== null) {
    expect(avatar.get('.dweller-pet img').attributes('src')).toContain('dogmeat.webp')
  }

  await avatar.trigger('focus')
  await vi.waitFor(() =>
    expect(document.querySelector('[role="tooltip"]')?.textContent).toContain('Pet Dogmeat')
  )
})

it('orders workers before apprentices and marks the apprentice avatar', () => {
  setFilteredDwellers([
    {
      ...alice,
      id: 'a1',
      first_name: 'Ash',
      last_name: 'Apprentice',
      level: 2,
      apprentice_stat: 'strength',
    },
    alice,
  ])

  const wrapper = mountDwellers()
  const avatars = wrapper.findAll('.dweller-avatar')

  expect(avatars[0].attributes('aria-label')).toContain('Alice Smith (Lv3)')
  expect(avatars[1].attributes('aria-label')).toContain(
    'Ash Apprentice (Lv2), apprentice in Strength'
  )
  expect(avatars[0].attributes('class')).not.toContain('dweller-avatar--apprentice')
  expect(avatars[1].attributes('class')).toContain('dweller-avatar--apprentice')
  expect(avatars[0].find('.apprentice-badge').exists()).toBe(false)
  expect(avatars[1].find('.apprentice-badge').exists()).toBe(true)
})

it('carries the drag-source anchor only on a dweller that can depart', () => {
  setFilteredDwellers([
    { ...alice, id: 'kid', first_name: 'Kid', age_group: 'child' },
    { ...alice, id: 'hurt', first_name: 'Hurt', health: 0 },
    { ...alice, id: 'away', first_name: 'Away', status: 'exploring' },
    { ...alice, id: 'elder', first_name: 'Elder', age_group: 'elder' },
  ])

  const wrapper = mountDwellers()
  const anchorFor = (name: string) =>
    wrapper
      .findAll('.dweller-avatar')
      .find((avatar) => avatar.attributes('aria-label')?.startsWith(name))
      ?.attributes('data-onboarding')

  // The guide asks for a healthy adult, so the spotlight must not land on a child,
  // a wounded dweller or one already away.
  expect(anchorFor('Kid')).toBeUndefined()
  expect(anchorFor('Hurt')).toBeUndefined()
  expect(anchorFor('Away')).toBeUndefined()
  expect(anchorFor('Elder')).toBe('dweller-drag-source')
})

it('keeps the worker visible while a build refresh reloads the filtered page', async () => {
  const filter = useDwellerFilterStore()
  const roomStore = useRoomStore()
  useVaultStore().activeVaultId = 'vault-1'
  useAuthStore().token = 'test-token'
  filter.allDwellers = []
  filter.allDwellersLoadedVaultId = null
  setFilteredDwellers([alice])

  const wrapper = mountDwellers()
  expect(wrapper.findAll('.dweller-avatar')).toHaveLength(1)

  let resolveRoster!: () => void
  const rosterSpy = vi.spyOn(filter, 'fetchAllDwellers').mockReturnValueOnce(
    new Promise<void>((resolve) => {
      resolveRoster = resolve
    })
  )
  const filteredSpy = vi.spyOn(filter, 'fetchWithCurrentFilters').mockImplementation(async () => {
    setFilteredDwellers([bob])
  })
  vi.mocked(axios.post).mockResolvedValueOnce({ data: [] })
  // Preload the dweller barrel: the room store reaches it through a lazy import.
  await import('@/modules/dwellers/stores/dweller')

  const refresh = roomStore.remodelRoom('r1')
  await flushPromises()
  expect(rosterSpy).toHaveBeenCalledWith('vault-1', false, true)
  expect(filteredSpy).not.toHaveBeenCalled()
  expect(wrapper.findAll('.dweller-avatar')).toHaveLength(1)
  expect(wrapper.get('.dweller-avatar').attributes('aria-label')).toContain('Alice Smith')

  filter.allDwellers = [alice, bob] as never
  filter.allDwellersLoadedVaultId = 'vault-1'
  resolveRoster()
  await refresh
  await nextTick()

  expect(filteredSpy).toHaveBeenCalledWith('vault-1')
  expect(wrapper.findAll('.dweller-avatar')).toHaveLength(1)
  expect(wrapper.get('.dweller-avatar').attributes('aria-label')).toContain('Alice Smith')
})

it('ignores a roster loaded for a different vault', () => {
  const filter = useDwellerFilterStore()
  filter.allDwellers = [alice] as never
  filter.allDwellersLoadedVaultId = 'vault-1'
  useVaultStore().activeVaultId = 'vault-2'
  setFilteredDwellers([])

  const wrapper = mountDwellers()

  expect(wrapper.find('.dweller-avatar').exists()).toBe(false)
})
