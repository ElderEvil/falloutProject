import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createToastMock } from '../helpers/mocks'
import axios from '@/core/plugins/axios'
import { useEquipmentStore } from '@/modules/combat/stores/equipment'

const authState = vi.hoisted(() => ({ generation: 0 }))

vi.mock('@/core/plugins/axios')
vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({
    get sessionGeneration() {
      return authState.generation
    },
  }),
}))

const toast = createToastMock()
vi.mock('@/core/composables/useToast', () => ({ useToast: () => toast }))

beforeEach(() => {
  vi.clearAllMocks()
  authState.generation = 0
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
        const old = fetch('vault-a')
        if (context === 'account') authState.generation += 1
        await fetch(context === 'vault' ? 'vault-b' : 'vault-a')
        finish({ data: [{ id: 'old' }] })
        await old
        expect(store[kind].map((item) => item.id)).toEqual(['current'])
        expect(store.error).toBeNull()
        expect(store.isLoading).toBe(false)
      }
    )

    it('ignores a delayed success after an account switch without a follow-up fetch', async () => {
      let finish!: (value: unknown) => void
      const pending = new Promise((resolve) => {
        finish = resolve
      })
      vi.mocked(axios.get).mockReturnValueOnce(pending)
      const store = useEquipmentStore()
      const fetch = kind === 'weapons' ? store.fetchWeapons : store.fetchOutfits
      const old = fetch('vault-a')
      authState.generation += 1
      finish({ data: [{ id: 'old' }] })
      await old
      expect(store[kind]).toHaveLength(0)
      expect(store.error).toBeNull()
      expect(toast.error).not.toHaveBeenCalled()
    })

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
        const old = fetch('vault-a')
        if (context === 'account') authState.generation += 1
        await fetch(context === 'vault' ? 'vault-b' : 'vault-a')
        fail(new Error('old request failed'))
        await old
        expect(store[kind].map((item) => item.id)).toEqual(['current'])
        expect(store.error).toBeNull()
        expect(toast.error).not.toHaveBeenCalled()
      }
    )
  })
}
