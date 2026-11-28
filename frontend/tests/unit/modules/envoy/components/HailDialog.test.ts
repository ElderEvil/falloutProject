import { describe, expect, it, vi } from 'vite-plus/test'
import { createIconifyMock } from '../../../helpers/mocks'
import { mount } from '@vue/test-utils'
import HailDialog from '@/modules/envoy/components/HailDialog.vue'
import type { EnvoySignal } from '@/modules/envoy/models/envoy'

vi.mock('@iconify/vue', () => createIconifyMock())

const target: EnvoySignal = {
  vault_id: 'vault-2',
  number: 12,
  owner_username: 'ada',
  status: 'UNMET',
  standing: 0,
  distance: 1.5,
  can_hail: true,
  incoming_hail: false,
}

function mountDialog(props: Record<string, unknown> = {}) {
  return mount(HailDialog, {
    props: { open: true, signal: target, ttlHours: 48, ...props },
    global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
  })
}

describe('HailDialog', () => {
  it('shows the canned dispatch, cost and server expiry with no free-text field', () => {
    const wrapper = mountDialog()

    expect(wrapper.text()).toContain('VAULT 12')
    expect(wrapper.text()).toContain('CANNED DISPATCH')
    expect(wrapper.text()).toContain('0 CAPS')
    expect(wrapper.text()).toContain('48 H')
    expect(wrapper.find('input, textarea').exists()).toBe(false)
  })

  it('confirms exactly once per press', async () => {
    const wrapper = mountDialog()
    const transmit = wrapper.findAll('button').find((button) => button.text().includes('TRANSMIT'))
    expect(transmit).toBeTruthy()

    await transmit!.trigger('click')

    expect(wrapper.emitted('confirm')).toHaveLength(1)
  })

  it('shows the server refusal inside the dialog', () => {
    const wrapper = mountDialog({ error: 'A hail is already waiting for an answer.' })

    expect(wrapper.text()).toContain('TRANSMISSION REFUSED')
    expect(wrapper.text()).toContain('A hail is already waiting for an answer.')
  })
})
