import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, reactive } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { useRoomDestroy } from '@/modules/rooms/composables/useRoomDestroy'

const { destroyRoom, auth, route } = vi.hoisted(() => ({
  destroyRoom: vi.fn(),
  auth: { token: 'token' },
  route: { params: { id: 'vault' } },
}))
vi.mock('vue-router', () => ({ useRoute: () => reactive(route) }))
vi.mock('@/modules/auth/stores/auth', () => ({ useAuthStore: () => reactive(auth) }))
vi.mock('@/modules/rooms/stores/room', () => ({
  useRoomStore: () => ({
    destroyRoom,
    rooms: [
      { id: 'room', name: 'Weight Room', coordinate_x: 0, coordinate_y: 0, size: 3, size_min: 3 },
    ],
  }),
}))
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}))

function mountActions() {
  let actions!: ReturnType<typeof useRoomDestroy>
  const wrapper = mount(
    defineComponent({
      setup() {
        actions = useRoomDestroy()
        return () => null
      },
    })
  )
  return { actions, wrapper }
}

describe('room destruction confirmation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    auth.token = 'token'
    route.params.id = 'vault'
    destroyRoom.mockResolvedValue(undefined)
  })

  it('requires explicit confirmation and ignores duplicate requests', async () => {
    const native = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { actions, wrapper } = mountActions()
    const canceled = actions.destroyRoom('room')
    await actions.destroyRoom('room')
    expect(actions.showDestroyConfirmation.value).toBe(true)
    expect(actions.destroyTitle.value).toBe('Destroy Weight Room?')
    expect(destroyRoom).not.toHaveBeenCalled()
    actions.cancelDestroy()
    await canceled
    expect(destroyRoom).not.toHaveBeenCalled()
    const onSuccess = vi.fn()
    const confirmed = actions.destroyRoom('room', { onSuccess })
    actions.confirmDestroy()
    await confirmed
    expect(destroyRoom).toHaveBeenCalledExactlyOnceWith('room', 'vault')
    expect(onSuccess).toHaveBeenCalledOnce()
    expect(native).not.toHaveBeenCalled()
    wrapper.unmount()
    native.mockRestore()
  })

  it.each(['unmount', 'route', 'login'])(
    'cancels a pending destruction on %s change',
    async (change) => {
      const { actions, wrapper } = mountActions()
      const pending = actions.destroyRoom('room')
      if (change === 'unmount') wrapper.unmount()
      if (change === 'route') reactive(route).params.id = 'other-vault'
      if (change === 'login') reactive(auth).token = 'different-token'
      await flushPromises()
      await pending
      expect(destroyRoom).not.toHaveBeenCalled()
      if (change !== 'unmount') wrapper.unmount()
    }
  )
})
