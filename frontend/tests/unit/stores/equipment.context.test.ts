import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createToastMock } from '../helpers/mocks'
import axios from '@/core/plugins/axios'
import { useEquipmentStore } from '@/modules/combat/stores/equipment'
import type { Weapon, Outfit } from '@/modules/combat/models/equipment'
import { useVaultStore } from '@/modules/vault/stores/vault'

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

for (const action of ['equipWeapon', 'unequipWeapon', 'equipOutfit', 'unequipOutfit'] as const) {
  it.each(['session', 'vault', 'active-vault'] as const)(
    `${action} ignores a late success after a %s switch`,
    async (change) => {
      const { promise, resolve } = Promise.withResolvers<{ data: Weapon | Outfit }>()
      vi.mocked(axios.post).mockReturnValueOnce(promise)
      vi.mocked(axios.get).mockResolvedValue({ data: [{ id: 'item', dweller_id: null }] })
      const store = useEquipmentStore()
      const kind = action.endsWith('Weapon') ? 'weapons' : 'outfits'
      const fetch = kind === 'weapons' ? store.fetchWeapons : store.fetchOutfits
      await fetch('vault-a')
      const pending = action.startsWith('unequip')
        ? store[action as 'unequipWeapon' | 'unequipOutfit']('item')
        : store[action as 'equipWeapon' | 'equipOutfit']('dweller', 'item')
      expect(vi.mocked(axios.post).mock.calls.at(-1)?.[2]).toEqual({ _skipErrorNotification: true })
      if (change === 'session') authState.generation++
      if (change === 'active-vault') useVaultStore().activeVaultId = 'vault-b'
      else await fetch(change === 'vault' ? 'vault-b' : 'vault-a')
      resolve({ data: { id: 'item', dweller_id: 'old' } as Weapon })
      expect(await pending).toBeNull()
      if (change === 'active-vault') expect(store[kind]).toEqual([])
      else expect(store[kind][0]?.dweller_id).toBeNull()
      expect(toast.success).not.toHaveBeenCalled()
    }
  )

  it(`${action} ignores a late failure after a session switch`, async () => {
    const { promise, reject } = Promise.withResolvers<never>()
    vi.mocked(axios.post).mockReturnValueOnce(promise)
    const store = useEquipmentStore()
    const pending = action.startsWith('unequip')
      ? store[action as 'unequipWeapon' | 'unequipOutfit']('item')
      : store[action as 'equipWeapon' | 'equipOutfit']('dweller', 'item')
    authState.generation++
    reject(new Error('Old failure'))
    expect(await pending).toBeNull()
    expect(toast.error).not.toHaveBeenCalled()
  })
}

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
