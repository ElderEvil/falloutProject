import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { mountWithSetup } from '../../helpers/mountWithSetup'
import VaultList from '@/modules/vault/components/VaultList.vue'
import { useVaultStore } from '@/modules/vault/stores/vault'
import axios from '@/core/plugins/axios'

vi.mock('@/core/plugins/axios')

const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
}))

// The auth store auto-fetches the user when a token exists; resolve it so the
// store keeps the token instead of logging out on the real (unavailable) API.
vi.mock('@/modules/auth/services/authService', () => ({
  authService: {
    getCurrentUser: vi.fn().mockResolvedValue({
      data: { id: 'user-1', username: 'overseer', is_superuser: true },
    }),
    logout: vi.fn().mockResolvedValue({}),
    refreshToken: vi.fn(),
    login: vi.fn(),
    register: vi.fn(),
  },
}))

const vault = {
  id: 'vault-1',
  number: 101,
  bottle_caps: 1000,
  happiness: 75,
  power: 50,
  power_max: 100,
  food: 60,
  food_max: 100,
  water: 70,
  water_max: 100,
  room_count: 5,
  dweller_count: 10,
  updated_at: new Date().toISOString(),
}

describe('VaultList', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'test-token')
    vi.mocked(axios.get).mockResolvedValue({ data: [] })
    vi.mocked(axios.delete).mockResolvedValue({ data: {} })
    pushMock.mockClear()
  })

  it('lists vaults and reveals Load/Delete actions on selection', async () => {
    const wrapper = mountWithSetup(VaultList)
    const vaultStore = useVaultStore()
    vaultStore.vaults = [vault]
    await nextTick()

    expect(wrapper.text()).toContain('Vault 101')
    expect(wrapper.text()).toContain('Bottle Caps: 1000')
    expect(wrapper.findAll('button')).toHaveLength(0)

    await wrapper.find('li').trigger('click')
    await nextTick()

    const buttons = wrapper.findAll('button')
    expect(buttons.map((b) => b.text())).toEqual(['Load', 'Delete'])
  })

  it('loads the selected vault through the router', async () => {
    const wrapper = mountWithSetup(VaultList)
    const vaultStore = useVaultStore()
    vaultStore.vaults = [vault]
    await nextTick()
    await wrapper.find('li').trigger('click')

    const load = wrapper.findAll('button').find((b) => b.text() === 'Load')
    await load!.trigger('click')
    await flushPromises()

    expect(pushMock).toHaveBeenCalledWith('/vault')
  })

  it('deletes the selected vault after confirmation', async () => {
    const wrapper = mountWithSetup(VaultList)
    const vaultStore = useVaultStore()
    vaultStore.vaults = [vault]
    await nextTick()
    await wrapper.find('li').trigger('click')

    const del = wrapper.findAll('button').find((b) => b.text() === 'Delete')
    await del!.trigger('click')
    await flushPromises()

    expect(axios.delete).toHaveBeenCalledWith(
      '/api/v1/vaults/vault-1',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
      })
    )
  })
})
