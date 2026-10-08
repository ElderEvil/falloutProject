import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import VaultInfoModal from '@/modules/map/components/VaultInfoModal.vue'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import type { VaultWithNumbers } from '@/modules/vault/stores/vault'

const teleportStub = { Teleport: { template: '<div><slot /></div>' } }

function createVault(overrides: Partial<VaultWithNumbers> = {}): VaultWithNumbers {
  return {
    id: 'vault-2',
    number: 121,
    bottle_caps: 1500,
    happiness: 82,
    power: 40,
    power_max: 80,
    food: 30,
    food_max: 60,
    water: 20,
    water_max: 50,
    room_count: 12,
    dweller_count: 18,
    updated_at: '2026-01-02T03:04:05Z',
    ...overrides,
  } as VaultWithNumbers
}

function mountModal(props: {
  open: boolean
  vault: VaultWithNumbers | null
  loading?: boolean
}) {
  return mount(VaultInfoModal, {
    props,
    global: { stubs: teleportStub },
  })
}

describe('VaultInfoModal', () => {
  it('renders the vault number as the modal title', () => {
    const wrapper = mountModal({ open: true, vault: createVault() })

    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Vault 121')
  })

  it('renders the same summary metrics as the vault-selection card', () => {
    const wrapper = mountModal({ open: true, vault: createVault() })

    expect(wrapper.text()).toContain('Caps')
    expect(wrapper.text()).toContain('1500')
    expect(wrapper.text()).toContain('Happiness')
    expect(wrapper.text()).toContain('82%')
    expect(wrapper.text()).toContain('Rooms')
    expect(wrapper.text()).toContain('12')
    expect(wrapper.text()).toContain('Dwellers')
    expect(wrapper.text()).toContain('18')
  })

  it('renders power, food and water as current/max with a fill bar each', () => {
    const wrapper = mountModal({ open: true, vault: createVault() })

    expect(wrapper.text()).toContain('40 / 80')
    expect(wrapper.text()).toContain('30 / 60')
    expect(wrapper.text()).toContain('20 / 50')

    const bars = wrapper.findAll('[role="progressbar"]')
    expect(bars).toHaveLength(3)
    expect(bars.map((bar) => bar.attributes('aria-valuenow'))).toEqual(['50', '50', '40'])
  })

  it('shows a loading state while the vault record is being resolved', () => {
    const wrapper = mountModal({ open: true, vault: null, loading: true })

    expect(wrapper.text()).toContain('Accessing vault records')
    expect(wrapper.text()).not.toContain('Caps')
  })

  it('shows an unavailable state when the record is null after loading', () => {
    const wrapper = mountModal({ open: true, vault: null, loading: false })

    expect(wrapper.text()).toContain('Vault unavailable')
  })

  it('closes via the close action and emits close', async () => {
    const wrapper = mountModal({ open: true, vault: createVault() })

    const closeButton = wrapper.findAll('button').find((button) => button.text() === 'Close')
    expect(closeButton).toBeTruthy()
    await closeButton!.trigger('click')

    expect(wrapper.emitted('update:open')).toEqual([[false]])
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('forwards TerminalModal close events', async () => {
    const wrapper = mountModal({ open: true, vault: createVault() })

    wrapper.findComponent(TerminalModal).vm.$emit('close')

    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})
