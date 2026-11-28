import { describe, expect, it, vi } from 'vite-plus/test'
import { createIconifyMock } from '../../../helpers/mocks'
import { mount, type VueWrapper } from '@vue/test-utils'
import SignalCard from '@/modules/envoy/components/SignalCard.vue'
import type { EnvoySignal } from '@/modules/envoy/models/envoy'

vi.mock('@iconify/vue', () => createIconifyMock())

function signal(overrides: Partial<EnvoySignal> = {}): EnvoySignal {
  return {
    vault_id: 'vault-2',
    number: 12,
    owner_username: 'ada',
    status: 'UNMET',
    standing: 42,
    distance: 1.5,
    can_hail: false,
    incoming_hail: false,
    ...overrides,
  }
}

function button(wrapper: VueWrapper, label: string) {
  const match = wrapper.findAll('button').find((candidate) => candidate.text().includes(label))
  expect(match, `button containing ${label}`).toBeTruthy()
  return match!
}

describe('SignalCard', () => {
  it('offers TRANSMIT as the only primary action when the vault is in range', async () => {
    const wrapper = mount(SignalCard, { props: { signal: signal({ can_hail: true }) } })

    expect(wrapper.text()).toContain('VAULT 12')
    expect(wrapper.text()).toContain('OVERSEER')
    expect(wrapper.text()).toContain('1.5 U')
    expect(wrapper.text()).toContain('ACCEPTED')

    await button(wrapper, 'TRANSMIT').trigger('click')

    expect(wrapper.emitted('hail')).toHaveLength(1)
    expect(wrapper.findAll('button')).toHaveLength(1)
  })

  it('shows AWAITING REPLY disabled while our hail is unanswered', () => {
    const wrapper = mount(SignalCard, {
      props: { signal: signal({ can_hail: true }), awaiting: true },
    })

    expect(wrapper.text()).toContain('AWAITING REPLY')
    expect(button(wrapper, 'AWAITING REPLY').attributes('disabled')).toBeDefined()
    expect(wrapper.find('button').text()).not.toContain('TRANSMIT')
  })

  it('answers an incoming hail with ACCEPT or REFUSE', async () => {
    const wrapper = mount(SignalCard, {
      props: { signal: signal({ incoming_hail: true, status: 'UNMET' }) },
    })

    await button(wrapper, 'ACCEPT').trigger('click')
    await button(wrapper, 'REFUSE').trigger('click')

    expect(wrapper.emitted('respond')).toEqual([[true], [false]])
    expect(wrapper.find('button').text()).not.toContain('TRANSMIT')
  })

  it('explains a locked line instead of offering an action', () => {
    const wrapper = mount(SignalCard, {
      props: { signal: signal({ locked_until: '2026-01-02T00:00:00Z' }) },
    })

    expect(wrapper.text()).toContain('LINE LOCKED')
    expect(wrapper.findAll('button')).toHaveLength(0)
  })
})
