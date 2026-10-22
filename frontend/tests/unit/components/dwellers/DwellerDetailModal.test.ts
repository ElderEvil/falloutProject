import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createAxiosMock, createIconifyMock } from '../../helpers/mocks'
import { defineComponent, ref } from 'vue'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, useRoute, useRouter } from 'vue-router'
import axios from '@/core/plugins/axios'
import PageNavigation from '@/core/components/common/PageNavigation.vue'
import DwellerDetailModal from '@/modules/dwellers/components/modals/DwellerDetailModal.vue'
import DwellerDetailContainer from '@/modules/dwellers/components/DwellerDetailContainer.vue'
import { useDwellerDetailContext } from '@/modules/dwellers/components/DwellerDetailContext'
import { useRoomDwellers } from '@/modules/rooms/composables/useRoomDwellers'
import { useAuthStore } from '@/modules/auth/stores/auth'
import type { Room } from '@/modules/rooms/models/room'

vi.mock('@/core/plugins/axios', () => createAxiosMock())
vi.mock('@iconify/vue', () => createIconifyMock())
enableAutoUnmount(afterEach)

const dwellerId = '11111111-2222-3333-4444-555555555555'
let dweller = {
  id: dwellerId,
  first_name: 'Amata',
  last_name: 'Almodovar',
  status: 'working',
  is_dead: false,
  is_permanently_dead: false,
  age_group: 'adult',
  room_id: 'room-1',
}

// Probe only the presentation; loading, commands, dialogs, stores and navigation remain real.
const Pane = defineComponent({
  props: { embedded: Boolean },
  components: { PageNavigation },
  setup() {
    return { ctx: useDwellerDetailContext() }
  },
  template: `<div>
    <PageNavigation v-if="!embedded" :breadcrumbs="[]" back-label="Back" history-first
      :back-to="'/vault/' + ctx.vaultId.value + '/dwellers'" />
    <p>{{ ctx.dweller.value.first_name }}</p>
    <button @click="ctx.actions.openRenameDialog()">Rename</button>
    <button @click="ctx.actions.onBack()">Close detail</button>
    <button @click="ctx.actions.navigateToDweller('22222222-3333-4444-5555-666666666666')">View relative</button>
  </div>`,
})
const RoomHost = defineComponent({
  setup() {
    const room = ref({ id: 'room-1' } as Room)
    return { ...useRoomDwellers(room, ref(null), () => {}), dwellerId }
  },
  template:
    '<div><h2>Power Generator</h2><button @click="openDwellerDetails(dwellerId)">Inspect worker</button></div>',
})
const Shell = defineComponent({
  components: { DwellerDetailModal },
  setup() {
    return { route: useRoute(), router: useRouter() }
  },
  template: `<div><router-view />
    <DwellerDetailModal v-if="typeof route.query.dweller === 'string'"
      :key="route.query.dweller" :dweller-id="route.query.dweller" :vault-id="route.params.id"
      @close="router.replace({ query: { ...route.query, dweller: undefined } })" />
  </div>`,
})

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  const auth = useAuthStore()
  auth.token = 'test-token'
  dweller = { ...dweller, first_name: 'Amata', id: dwellerId }
  vi.mocked(axios.get).mockImplementation(async (url) => ({
    data: String(url).includes('/dwellers/') ? dweller : { locations: [] },
  }))
})
afterEach(() => vi.restoreAllMocks())

async function openWorker() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/vault/:id', component: RoomHost },
      { path: '/vault/:id/dwellers', component: RoomHost },
      {
        path: '/vault/:id/dwellers/:dwellerId',
        name: 'dwellerDetail',
        component: DwellerDetailContainer,
      },
    ],
  })
  await router.push('/vault/vault-1?tab=rooms')
  const wrapper = mount(Shell, {
    global: {
      plugins: [router],
      stubs: {
        DwellerDetailPane: Pane,
        DwellerAppearanceEditor: true,
        TrainingStartModal: true,
        ExplorationDurationModal: true,
        Dialog: {
          props: ['open'],
          emits: ['update:open'],
          template: '<div v-if="open"><slot /></div>',
        },
        DialogContent: { template: '<div><slot /></div>' },
        DialogHeader: { template: '<div><slot /></div>' },
        DialogTitle: { template: '<h2><slot /></h2>' },
        DialogFooter: { template: '<div><slot /></div>' },
      },
    },
  })
  await wrapper.get('button').trigger('click')
  await flushPromises()
  return { wrapper, router }
}

it('opens worker details without leaving the room and closes back to the room', async () => {
  const { wrapper, router } = await openWorker()
  expect(router.currentRoute.value.path).toBe('/vault/vault-1')
  expect(router.currentRoute.value.query).toEqual({
    tab: 'rooms',
    roomId: 'room-1',
    dweller: dwellerId,
  })
  expect(wrapper.text()).toContain('Amata')
  expect(wrapper.text()).toContain('Power Generator')
  expect(axios.get).toHaveBeenCalledWith(`/api/v1/dwellers/${dwellerId}`, expect.any(Object))
  await wrapper
    .findAll('button')
    .find((button) => button.text() === 'Close detail')!
    .trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.query.dweller).toBeUndefined()
  expect(router.currentRoute.value.query.roomId).toBe('room-1')
  expect(wrapper.findComponent(DwellerDetailModal).exists()).toBe(false)
})

it('expands to the existing detail page and Back restores the room and dweller selection', async () => {
  const { wrapper, router } = await openWorker()
  const origin = router.currentRoute.value.fullPath
  await wrapper.get('[aria-label="Open full page"]').trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.path).toBe(`/vault/vault-1/dwellers/${dwellerId}`)
  expect(router.currentRoute.value.query).toEqual({})
  expect(wrapper.findComponent(DwellerDetailModal).exists()).toBe(false)
  vi.spyOn(window.history, 'length', 'get').mockReturnValue(3)
  vi.spyOn(window.history, 'state', 'get').mockReturnValue({ back: origin })
  await wrapper.get('[aria-label="Back"]').trigger('click')
  await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe(origin))
  await flushPromises()
  expect(wrapper.findComponent(DwellerDetailModal).exists()).toBe(true)
  expect(wrapper.text()).toContain('Amata')
})

it('browser Back closes the overlay without leaving the original room view', async () => {
  const { wrapper, router } = await openWorker()
  router.back()
  await vi.waitFor(() => expect(router.currentRoute.value.query.dweller).toBeUndefined())
  await flushPromises()
  expect(router.currentRoute.value.fullPath).toBe('/vault/vault-1?tab=rooms')
  expect(wrapper.findComponent(DwellerDetailModal).exists()).toBe(false)
  expect(wrapper.text()).toContain('Power Generator')
})

it('uses the shared rename action from the embedded detail', async () => {
  const { wrapper, router } = await openWorker()
  vi.mocked(axios.patch).mockImplementation(async () => {
    dweller = { ...dweller, first_name: 'Lucy' }
    return { data: dweller }
  })
  await wrapper
    .findAll('button')
    .find((button) => button.text() === 'Rename')!
    .trigger('click')
  await wrapper.get('#rename-dweller').setValue('Lucy')
  await wrapper
    .findAll('button')
    .find((button) => button.text() === 'Save')!
    .trigger('click')
  await flushPromises()
  expect(axios.patch).toHaveBeenCalledWith(
    `/api/v1/dwellers/${dwellerId}/rename`,
    { first_name: 'Lucy', last_name: 'Almodovar' },
    expect.any(Object)
  )
  expect(wrapper.text()).toContain('Lucy')
  expect(router.currentRoute.value.path).toBe('/vault/vault-1')
})

it('keeps relative navigation inside the modal', async () => {
  const { wrapper, router } = await openWorker()
  await wrapper
    .findAll('button')
    .find((button) => button.text() === 'View relative')!
    .trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.path).toBe('/vault/vault-1')
  expect(router.currentRoute.value.query.dweller).toBe('22222222-3333-4444-5555-666666666666')
  expect(router.currentRoute.value.query.roomId).toBe('room-1')
})
