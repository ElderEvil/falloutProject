import { afterEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import RoomTrainingSection from '@/modules/rooms/components/RoomTrainingSection.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useTrainingStore } from '@/modules/progression/stores/training'
import axios from '@/core/plugins/axios'
import type { Room } from '@/modules/rooms/models/room'

vi.mock('@/core/plugins/axios', () => ({ default: { get: vi.fn() } }))
enableAutoUnmount(afterEach)
afterEach(() => vi.useRealTimers())

it('polls the next round and refreshes the roster without retaining the old round', async () => {
  vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
  setActivePinia(createPinia())
  useAuthStore().token = 'token'
  let roundId = 'first-round'
  vi.mocked(axios.get).mockImplementation(async (url) => ({
    data: url.includes('/training/')
      ? [
          {
            id: roundId,
            room_id: 'r1',
            dweller_id: 'd1',
            status: 'active',
            stat_being_trained: 'strength',
            current_stat_value: 5,
            target_stat_value: 6,
            progress: 0,
            started_at: new Date().toISOString(),
            estimated_completion_at: new Date(Date.now() + 3600000).toISOString(),
          },
        ]
      : [],
  }))
  const wrapper = mount(RoomTrainingSection, {
    props: {
      vaultId: 'v1',
      room: { id: 'r1', size: 3, ability: 'strength' } as Room,
      assignedDwellers: [],
    },
    global: { stubs: { TrainingProgressCard: true, Icon: true } },
  })
  await flushPromises()
  const store = useTrainingStore()
  expect(store.activeTrainings.has('first-round')).toBe(true)
  roundId = 'next-round'
  await vi.advanceTimersByTimeAsync(30_000)
  await flushPromises()
  expect(store.activeTrainings.has('first-round')).toBe(false)
  expect(store.activeTrainings.has('next-round')).toBe(true)
  expect(vi.mocked(axios.get).mock.calls.some(([url]) => url.includes('/dwellers'))).toBe(true)
  wrapper.unmount()
  const callsAfterClose = vi.mocked(axios.get).mock.calls.length
  await vi.advanceTimersByTimeAsync(30_000)
  expect(axios.get).toHaveBeenCalledTimes(callsAfterClose)
})
