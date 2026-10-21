import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import TrainingView from '@/modules/progression/views/TrainingView.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useVaultStore } from '@/modules/vault/stores/vault'

vi.mock('@/core/plugins/axios', () => ({
  default: { get: vi.fn().mockResolvedValue({ data: [] }) },
}))

describe('TrainingView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders the real training queue without a page-level tooltip provider', async () => {
    useAuthStore().token = 'test-token'
    vi.spyOn(useVaultStore(), 'ensureVaultLoaded').mockResolvedValue()
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/vault/:id/training', component: TrainingView }],
    })
    await router.push('/vault/vault-1/training')
    await router.isReady()
    const wrapper = mount(TrainingView, {
      global: { plugins: [router], stubs: { SidePanel: true, Icon: true } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Training Center')
    expect(wrapper.text()).toContain('Training Queue')
    expect(wrapper.text().indexOf('Training Queue')).toBeLessThan(
      wrapper.text().indexOf('Apprentices')
    )
    expect(wrapper.get('button[aria-label="Repeat training"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('uses the standard vault shell and gives the training queue the full content width by default', async () => {
    const authStore = useAuthStore()
    const vaultStore = useVaultStore()
    authStore.token = 'test-token'
    vi.spyOn(vaultStore, 'ensureVaultLoaded').mockResolvedValue()

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/vault/:id/training', component: TrainingView }],
    })
    await router.push('/vault/vault-1/training')
    await router.isReady()

    const wrapper = mount(TrainingView, {
      global: {
        plugins: [router],
        stubs: {
          Icon: true,
          Teleport: { template: '<div><slot /></div>' },
          SidePanel: { template: '<aside data-testid="side-panel" />' },
          TrainingQueuePanel: { template: '<section data-testid="training-queue" />' },
        },
      },
    })

    expect(wrapper.find('[data-testid="side-panel"]').exists()).toBe(true)
    expect(wrapper.find('.vault-layout').exists()).toBe(true)
    expect(wrapper.find('.main-content').exists()).toBe(true)
    expect(wrapper.find('.main-content > div').classes()).toContain('max-w-[1400px]')
    expect(
      wrapper.find('[data-testid="training-queue"]').element.parentElement?.className
    ).toContain('w-full')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    await vi.waitFor(() =>
      expect(wrapper.find('button[aria-label="About Training Center"]').exists()).toBe(true)
    )
    await wrapper.find('button[aria-label="About Training Center"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('About Training Center')
    expect(wrapper.text()).toContain('Training Duration')
  })

  it('groups rooms by SPECIAL stat and keeps the shared overall capacity', async () => {
    const authStore = useAuthStore()
    const roomStore = useRoomStore()
    const vaultStore = useVaultStore()
    authStore.token = 'test-token'
    roomStore.rooms = [
      { id: 'agility-room', ability: 'agility', category: 'training', capacity: null, size: 3 },
      { id: 'strength-room-2', ability: 'strength', category: 'training', capacity: null, size: 3 },
      { id: 'production-room', ability: 'strength', category: 'production', capacity: 2, size: 3 },
      {
        id: 'training-room-1',
        ability: 'strength',
        category: 'training',
        capacity: null,
        size: 3,
      },
    ] as typeof roomStore.rooms
    vi.spyOn(vaultStore, 'ensureVaultLoaded').mockResolvedValue()
    vi.spyOn(roomStore, 'fetchRooms').mockResolvedValue('loaded')

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/vault/:id/training', component: TrainingView }],
    })
    await router.push('/vault/vault-1/training')
    await router.isReady()

    const wrapper = mount(TrainingView, {
      global: {
        plugins: [router],
        stubs: {
          Icon: true,
          SidePanel: true,
          TrainingQueuePanel: true,
          TrainingRoomCard: true,
        },
      },
    })

    expect(wrapper.text()).toContain('0 / 6')
    expect(wrapper.findAll('.page-header-metric-value').map((metric) => metric.text())).toEqual([
      '0',
      '0 / 3',
    ])
    const capacity = wrapper.get('[role="group"][aria-label="Overall training capacity"]')
    expect(capacity.text()).toContain('0 / 6')
    expect(capacity.find('[role="progressbar"]').exists()).toBe(false)
    const rows = wrapper.findAll('section[aria-label$="training rooms"]')
    expect(rows.map((row) => row.attributes('aria-label'))).toEqual([
      'Strength training rooms',
      'Agility training rooms',
    ])
    expect(rows[0].findAll('training-room-card-stub')).toHaveLength(2)
    expect(rows[1].findAll('training-room-card-stub')).toHaveLength(1)
  })
})
