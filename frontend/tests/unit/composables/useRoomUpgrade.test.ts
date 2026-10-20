import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'
import { useRoomUpgrade } from '@/modules/rooms/composables/useRoomUpgrade'
import type { Room } from '@/modules/rooms/models/room'

const { remodelRoom } = vi.hoisted(() => ({ remodelRoom: vi.fn().mockResolvedValue(undefined) }))
vi.mock('vue-router', () => ({ useRoute: () => ({ params: { id: 'vault' } }) }))
vi.mock('@/modules/rooms/stores/room', () => ({ useRoomStore: () => ({ remodelRoom }) }))
vi.mock('@/modules/auth/stores/auth', () => ({ useAuthStore: () => ({ token: 'token' }) }))
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}))
vi.mock('@/modules/rooms/composables/useRoomDestroy', () => ({ useRoomDestroy: () => ({}) }))

describe('room remodel confirmation', () => {
  it.each(['selection', 'unmount'])(
    'abandons a pending remodel after %s changes',
    async (change) => {
      remodelRoom.mockClear()
      let actions!: ReturnType<typeof useRoomUpgrade>
      const room = ref({ id: 'room', name: 'Living Room' } as Room)
      const wrapper = mount(
        defineComponent({
          setup() {
            actions = useRoomUpgrade(room, ref(null), vi.fn(), vi.fn())
            return () => null
          },
        })
      )
      const pending = actions.handleRemodel()
      await actions.handleRemodel('neighbor')
      if (change === 'selection') {
        room.value = { ...room.value, id: 'different-room' }
        actions.confirmRemodel()
      } else {
        wrapper.unmount()
      }
      await pending
      expect(remodelRoom).not.toHaveBeenCalled()
      if (change === 'selection') wrapper.unmount()
    }
  )

  it.each([undefined, 'neighbor'])(
    'requires confirmation before remodeling with neighbor %s',
    async (neighbor) => {
      remodelRoom.mockClear()
      const nativeConfirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
      let actions!: ReturnType<typeof useRoomUpgrade>
      const room = ref({ id: 'room', name: 'Living Room' } as Room)
      const wrapper = mount(
        defineComponent({
          setup() {
            actions = useRoomUpgrade(room, ref(null), vi.fn(), vi.fn())
            return () => null
          },
        })
      )
      const canceled = actions.handleRemodel(neighbor)
      expect(nativeConfirm).not.toHaveBeenCalled()
      expect(actions.showRemodelConfirmation.value).toBe(true)
      expect(remodelRoom).not.toHaveBeenCalled()
      actions.cancelRemodel()
      await canceled
      expect(remodelRoom).not.toHaveBeenCalled()
      const confirmed = actions.handleRemodel(neighbor)
      actions.confirmRemodel()
      await confirmed
      await flushPromises()
      expect(remodelRoom).toHaveBeenCalledExactlyOnceWith('room', 'token', neighbor)
      wrapper.unmount()
      nativeConfirm.mockRestore()
    }
  )
})
