import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createToastMock } from '../helpers/mocks'
import axios from '@/core/plugins/axios'
import { useEquipmentStore } from '@/modules/combat/stores/equipment'

vi.mock('@/core/plugins/axios')
const toast = createToastMock()
vi.mock('@/core/composables/useToast', () => ({ useToast: () => toast }))

beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
})

for (const kind of ['weapons', 'outfits'] as const) {
  describe(`${kind} request ownership`, () => {
    it.each(['vault', 'account'] as const)(
      'ignores stale success after a %s switch',
      async (context) => {
        let finish!: (value: unknown) => void
        const pending = new Promise((resolve) => {
          finish = resolve
        })
        vi.mocked(axios.get)
          .mockReturnValueOnce(pending)
          .mockResolvedValueOnce({ data: [{ id: 'current' }] })
        const store = useEquipmentStore()
        const fetch = kind === 'weapons' ? store.fetchWeapons : store.fetchOutfits
        const old = fetch('token-a', 'vault-a')
        await fetch(
          context === 'account' ? 'token-b' : 'token-a',
          context === 'vault' ? 'vault-b' : 'vault-a'
        )
        finish({ data: [{ id: 'old' }] })
        await old
        expect(store[kind].map((item) => item.id)).toEqual(['current'])
        expect(store.error).toBeNull()
        expect(store.isLoading).toBe(false)
      }
    )

    it.each(['vault', 'account'] as const)(
      'ignores stale failure after a %s switch',
      async (context) => {
        let fail!: (reason: unknown) => void
        const pending = new Promise((_resolve, reject) => {
          fail = reject
        })
        vi.mocked(axios.get)
          .mockReturnValueOnce(pending)
          .mockResolvedValueOnce({ data: [{ id: 'current' }] })
        const store = useEquipmentStore()
        const fetch = kind === 'weapons' ? store.fetchWeapons : store.fetchOutfits
        const old = fetch('token-a', 'vault-a')
        await fetch(
          context === 'account' ? 'token-b' : 'token-a',
          context === 'vault' ? 'vault-b' : 'vault-a'
        )
        fail(new Error('old request failed'))
        await old
        expect(store[kind].map((item) => item.id)).toEqual(['current'])
        expect(store.error).toBeNull()
        expect(toast.error).not.toHaveBeenCalled()
      }
    )
  })
}
