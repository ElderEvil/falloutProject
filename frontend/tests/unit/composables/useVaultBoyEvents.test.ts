import { afterEach, beforeEach, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { effectScope, nextTick, ref } from 'vue'
import { useVaultBoyEvents } from '@/modules/vault/composables/useVaultBoyEvents'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useStorageStore } from '@/modules/storage/stores/storage'
import { useVaultBoyFeedback } from '@/core/composables/useVaultBoyFeedback'

const feedback = useVaultBoyFeedback()
let scope = effectScope()
beforeEach(() => {
  setActivePinia(createPinia())
  feedback.clear()
  scope = effectScope()
})
afterEach(() => {
  scope.stop()
  feedback.clear()
})

it('animates low happiness on entry, without replaying for every tick', async () => {
  const vault = useVaultStore()
  vault.$patch({ activeVaultId: 'v1', loadedVaults: { v1: { happiness: 45 } } })
  scope.run(() => useVaultBoyEvents(ref('v1')))
  expect(feedback.current.value?.animation).toBe('happiness-low')
  feedback.dismiss()
  vault.loadedVaults.v1!.happiness = 40
  await nextTick()
  expect(feedback.current.value).toBeNull()
})

it('animates a full storage transition only for the viewed vault', async () => {
  const storage = useStorageStore()
  scope.run(() => useVaultBoyEvents(ref('v1')))
  storage.$patch({ vaultId: 'v2', space: { max_space: 10, available_space: 0 } })
  await nextTick()
  expect(feedback.current.value).toBeNull()
  storage.vaultId = 'v1'
  await nextTick()
  expect(feedback.current.value?.animation).toBe('storage')
  feedback.dismiss()
  storage.space!.used_space = 12
  await nextTick()
  expect(feedback.current.value).toBeNull()
})
