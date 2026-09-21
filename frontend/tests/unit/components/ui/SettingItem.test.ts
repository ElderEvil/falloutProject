import { describe, expect, it } from 'vitest'

import { mountWithSetup } from '../../helpers/mountWithSetup'
import SettingItem from '@/core/components/ui/SettingItem.vue'

describe('SettingItem', () => {
  it('renders the label and a string value', () => {
    const wrapper = mountWithSetup(SettingItem, {
      props: { label: 'Vault name', value: 'Vault 101' },
    })

    expect(wrapper.text()).toContain('Vault name')
    expect(wrapper.text()).toContain('Vault 101')
  })

  it('formats numbers with the requested decimals', () => {
    const wrapper = mountWithSetup(SettingItem, {
      props: { label: 'Happiness', value: 85.456, decimals: 1 },
    })

    expect(wrapper.text()).toContain('85.5')
  })

  it('renders numbers without decimals as-is', () => {
    const wrapper = mountWithSetup(SettingItem, { props: { label: 'Population', value: 42 } })

    expect(wrapper.text()).toContain('42')
  })

  it('renders booleans as Yes or No', () => {
    const yes = mountWithSetup(SettingItem, { props: { label: 'Enabled', value: true } })
    expect(yes.text()).toContain('Yes')

    const no = mountWithSetup(SettingItem, { props: { label: 'Enabled', value: false } })
    expect(no.text()).toContain('No')
  })

  it('renders the unit suffix after the value', () => {
    const wrapper = mountWithSetup(SettingItem, {
      props: { label: 'Radiation', value: 50, unit: '%' },
    })

    expect(wrapper.text()).toContain('50')
    expect(wrapper.text()).toContain('%')
  })
})