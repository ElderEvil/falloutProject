import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import TrainingView from '@/modules/progression/views/TrainingView.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useVaultStore } from '@/modules/vault/stores/vault'

describe('TrainingView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('uses the standard vault shell and gives the training queue the full content width by default', async () => {
    const authStore = useAuthStore()
    const vaultStore = useVaultStore()
    authStore.token = 'test-token'
    vi.spyOn(vaultStore, 'loadVault').mockResolvedValue()

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
          PageHeader: true,
          SidePanel: { template: '<aside data-testid="side-panel" />' },
          TrainingQueuePanel: { template: '<section data-testid="training-queue" />' },
        },
      },
    })

    expect(wrapper.find('[data-testid="side-panel"]').exists()).toBe(true)
    expect(wrapper.find('.vault-layout').exists()).toBe(true)
    expect(wrapper.find('.main-content').exists()).toBe(true)
    expect(
      wrapper.find('[data-testid="training-queue"]').element.parentElement?.className
    ).toContain('w-full')
    expect(wrapper.find('.training-reference').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('About Training')

    await wrapper.find('.info-toggle').trigger('click')

    expect(wrapper.text()).toContain('About Training')
    expect(wrapper.text()).toContain('Training Duration')
  })

  it('uses the shared training-room capacity for the overall capacity progress bar', async () => {
    const authStore = useAuthStore()
    const roomStore = useRoomStore()
    const vaultStore = useVaultStore()
    authStore.token = 'test-token'
    roomStore.rooms = [
      {
        id: 'training-room-1',
        category: 'training',
        capacity: null,
        size: 3,
      },
    ] as typeof roomStore.rooms
    vi.spyOn(vaultStore, 'loadVault').mockResolvedValue()
    vi.spyOn(roomStore, 'fetchRooms').mockResolvedValue()

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
          PageHeader: true,
          SidePanel: true,
          TrainingQueuePanel: true,
          TrainingRoomCard: true,
        },
      },
    })

    expect(wrapper.text()).toContain('0 / 2')
    expect(wrapper.get('[role="progressbar"]').attributes('aria-valuenow')).toBe('0')
  })
})
