import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { useVaultBoyFeedback } from '@/core/composables/useVaultBoyFeedback'

const feedback = useVaultBoyFeedback()
const event = {
  animation: 'empty-can' as const,
  title: 'Food low',
  message: 'Make food',
  vaultId: 'v1',
}
beforeEach(() => {
  feedback.clear()
  vi.useFakeTimers()
})
afterEach(() => {
  feedback.clear()
  vi.useRealTimers()
})

it('suppresses repeated warning keys for 30 seconds', () => {
  feedback.show({ ...event, key: 'low-food' })
  feedback.dismiss()
  feedback.show({ ...event, key: 'low-food' })
  expect(feedback.current.value).toBeNull()
  vi.advanceTimersByTime(30000)
  feedback.show({ ...event, key: 'low-food' })
  expect(feedback.current.value?.animation).toBe('empty-can')
})

it('keeps warnings isolated by vault', () => {
  feedback.show({ ...event, key: 'low-food' })
  feedback.dismiss()
  feedback.show({ ...event, vaultId: 'v2', key: 'low-food' })
  expect(feedback.current.value?.vaultId).toBe('v2')
})

it('bounds bursts while preserving the playing event and newest arrivals', () => {
  for (let i = 0; i < 7; i += 1) feedback.show({ ...event, title: String(i) })
  const played = []
  while (feedback.current.value) {
    played.push(feedback.current.value.title)
    feedback.dismiss()
  }
  expect(played).toEqual(['0', '4', '5', '6'])
})

it('clears both queued feedback and cooldowns at a session boundary', () => {
  feedback.show({ ...event, key: 'low-food' })
  feedback.show(event)
  feedback.clear()
  expect(feedback.current.value).toBeNull()
  feedback.show({ ...event, key: 'low-food' })
  expect(feedback.current.value?.title).toBe('Food low')
})
