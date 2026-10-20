import { beforeEach, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import axios from '@/core/plugins/axios'
import StorageMaintenancePanel from '@/modules/storage/components/StorageMaintenancePanel.vue'

vi.mock('@/core/plugins/axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }))

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

it.each([
  ['rusting', 10, 50, 0.01, 3600, 'Rusting · 1.0% / hour'],
  ['stable', 20, 100, 0, 3600, 'Stable · 0.0% / hour'],
  ['improving', 40, 100, 0.02, 1800, 'Improving · 2.0% / 30 min'],
] as const)(
  'shows %s odds and shared vault protection, and refreshes after staffing changes',
  async (mode, endurance, protection, chance, interval, label) => {
    vi.mocked(axios.get).mockImplementation(async (url) => ({
      data: String(url).endsWith('/maintenance')
        ? {
            enabled: true,
            mode,
            worker_count: 4,
            total_endurance: endurance,
            protection_pct: protection,
            hourly_chance: chance,
            trial_interval_seconds: interval,
          }
        : String(url).endsWith('/items')
          ? { weapons: [], outfits: [], junk: [], items: [], pets: [] }
          : {},
    }))
    const wrapper = mount(StorageMaintenancePanel, {
      props: { vaultId: 'vault-1', workers: 2, slots: 4 },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('2 / 4 room workers')
    expect(wrapper.text()).toContain(label)
    expect(wrapper.text()).toContain(`Vault-wide: ${endurance} END · ${protection}% protection`)
    expect(wrapper.text()).not.toContain('Trials run while you are online')
    vi.mocked(axios.get).mockClear()
    await wrapper.setProps({ workers: 3 })
    await flushPromises()
    expect(wrapper.text()).toContain('3 / 4 room workers')
    expect(axios.get).toHaveBeenCalledWith('/api/v1/storage/vault/vault-1/maintenance')
    wrapper.unmount()
  }
)

it('shows an inactive message without exposing stale odds when disabled', async () => {
  vi.mocked(axios.get).mockResolvedValue({ data: { enabled: false } })
  const wrapper = mount(StorageMaintenancePanel, {
    props: { vaultId: 'vault-1', workers: 0, slots: 4 },
  })
  await flushPromises()
  expect(wrapper.text()).toContain('Weapon maintenance is not active.')
  expect(wrapper.text()).not.toContain('Vault-wide:')
  wrapper.unmount()
})
