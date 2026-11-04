import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { createPinia, setActivePinia } from 'pinia'
import axios from '@/core/plugins/axios'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerPerksStore } from '@/modules/dwellers/stores/perks'
import type { DwellerPerks } from '@/modules/dwellers/services/dwellerService'

vi.mock('@/core/plugins/axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }))

function perks(id: string, selected: DwellerPerks['selected_perk'] = null): DwellerPerks {
  return {
    dweller_id: id,
    selected_perk: selected,
    options: [
      {
        id: 'hacker',
        name: 'Hacker',
        description: 'Access terminals.',
        stat: 'intelligence',
        minimum_stat: 4,
        minimum_level: 5,
        eligible: !selected,
        unavailable_reason: null,
      },
    ],
  }
}

describe('explorer perk state', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()
    useAuthStore().token = 'account-a'
  })

  it('ignores a delayed response after another vault/dweller is loaded', async () => {
    let finish!: (response: { data: DwellerPerks }) => void
    vi.mocked(axios.get)
      .mockReturnValueOnce(
        new Promise((resolve) => {
          finish = resolve
        })
      )
      .mockResolvedValueOnce({ data: perks('dweller-b') })
    const store = useDwellerPerksStore()
    const first = store.load('vault-a', 'dweller-a')
    await store.load('vault-b', 'dweller-b')
    finish({ data: perks('dweller-a') })
    await first
    expect(store.data?.dweller_id).toBe('dweller-b')
  })

  it('ignores a delayed selection after an account switch', async () => {
    vi.mocked(axios.get).mockResolvedValue({ data: perks('dweller-a') })
    let finish!: (response: { data: DwellerPerks }) => void
    vi.mocked(axios.post).mockReturnValueOnce(
      new Promise((resolve) => {
        finish = resolve
      })
    )
    const store = useDwellerPerksStore()
    await store.load('vault-a', 'dweller-a')
    const selection = store.choose('hacker')
    useAuthStore().token = 'account-b'
    finish({ data: perks('dweller-a', 'hacker') })
    await selection
    expect(store.data).toBeNull()
    expect(store.selecting).toBe(false)
  })

  it('submits once while choosing and retains the committed result', async () => {
    vi.mocked(axios.get).mockResolvedValue({ data: perks('dweller-a') })
    vi.mocked(axios.post).mockResolvedValue({ data: perks('dweller-a', 'hacker') })
    const store = useDwellerPerksStore()
    await store.load('vault-a', 'dweller-a')
    await Promise.all([store.choose('hacker'), store.choose('hacker')])
    expect(axios.post).toHaveBeenCalledTimes(1)
    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/dwellers/dweller-a/perks',
      { perk: 'hacker' },
      {
        headers: { Authorization: 'Bearer account-a' },
      }
    )
    expect(store.data?.selected_perk).toBe('hacker')
  })
})
