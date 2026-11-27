import { beforeEach, describe, expect, it } from 'vite-plus/test'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import CombatZoneBanner from '@/modules/combat-zone/components/CombatZoneBanner.vue'
import { useFeatureFlagsStore } from '@/core/stores/featureFlags'

function mountBanner() {
  return mount(CombatZoneBanner, {
    props: { vaultId: 'vault-1' },
    global: { stubs: { CombatZonePanel: true, Icon: true } },
  })
}

describe('CombatZoneBanner', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const flags = useFeatureFlagsStore()
    flags.loaded = true
  })

  it('offers the Zone when the feature is on', async () => {
    const flags = useFeatureFlagsStore()
    flags.combatZone = true

    const wrapper = mountBanner()
    await flushPromises()

    expect(wrapper.text()).toContain('INTERCHANGE 77 · THE COMBAT ZONE')
    expect(wrapper.text()).toContain('Enter the Zone')
  })

  it('stays hidden while the feature is off', async () => {
    const flags = useFeatureFlagsStore()
    flags.combatZone = false

    const wrapper = mountBanner()
    await flushPromises()

    expect(wrapper.text()).not.toContain('INTERCHANGE 77')
  })
})
