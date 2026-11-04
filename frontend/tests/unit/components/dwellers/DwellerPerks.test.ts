import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import axios from '@/core/plugins/axios'
import { useAuthStore } from '@/modules/auth/stores/auth'
import DwellerPerks from '@/modules/dwellers/components/DwellerPerks.vue'
import {
  createMockDwellerDetailContext,
  mountWithDwellerContext,
} from '../../helpers/dwellerDetailContext'
import type { Dweller } from '@/modules/dwellers/models/dweller'

vi.mock('@/core/plugins/axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }))

const catalog = {
  dweller_id: 'dweller-1',
  selected_perk: null,
  options: [
    {
      id: 'hacker',
      name: 'Hacker',
      description: 'Access terminal solutions.',
      stat: 'intelligence',
      minimum_stat: 4,
      minimum_level: 5,
      eligible: true,
      unavailable_reason: null,
    },
  ],
}

function mountPerks() {
  return mountWithDwellerContext(DwellerPerks, {
    context: createMockDwellerDetailContext({
      vaultId: ref('vault-1'),
      dweller: ref({ id: 'dweller-1' } as Dweller),
    }),
  })
}

describe('DwellerPerks', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()
    useAuthStore().token = 'owner-token'
  })

  it('requires confirmation before learning a permanent perk and shows the result', async () => {
    vi.mocked(axios.get).mockResolvedValue({ data: catalog })
    vi.mocked(axios.post).mockResolvedValue({ data: { ...catalog, selected_perk: 'hacker' } })
    const wrapper = mountPerks()
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'Choose Hacker')!
      .trigger('click')
    expect(axios.post).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('only perk choice')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'Confirm Hacker')!
      .trigger('click')
    await flushPromises()
    expect(axios.post).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('Learned')
    expect(wrapper.text()).not.toContain('Choose Hacker')
  })

  it('explains and disables an ineligible choice', async () => {
    vi.mocked(axios.get).mockResolvedValue({
      data: {
        ...catalog,
        options: [
          { ...catalog.options[0], eligible: false, unavailable_reason: 'Requires level 5.' },
        ],
      },
    })
    const wrapper = mountPerks()
    await flushPromises()
    expect(wrapper.text()).toContain('Requires level 5.')
    expect(
      wrapper
        .findAll('button')
        .find((button) => button.text() === 'Choose Hacker')!
        .attributes('disabled')
    ).toBeDefined()
  })
})
