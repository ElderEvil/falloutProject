import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import IncidentAftermath from '@/modules/rooms/components/IncidentAftermath.vue'
import type { IncidentAftermath as Aftermath } from '@/modules/combat/models/incident'

const clearAftermath = vi.fn()
const takeOverflow = vi.fn()
const sellOverflow = vi.fn()

vi.mock('@/modules/combat/stores/incident', () => ({
  useIncidentStore: () => ({ clearAftermath, takeOverflow, sellOverflow }),
}))

vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({ token: 'test-token' }),
}))

const aftermath = (overrides: Partial<Aftermath> = {}): Aftermath =>
  ({
    incidentId: 'incident-1',
    roomId: 'room-1',
    type: 'raider_attack',
    roomName: 'Power Generator',
    outcome: 'victory',
    capsEarned: 50,
    experienceEarned: 40,
    loot: null,
    unclaimed: [],
    enemiesDefeated: 3,
    damageDealt: 40,
    rounds: 6,
    ...overrides,
  }) as Aftermath

const mountAftermath = (props: Record<string, unknown> = {}) =>
  mount(IncidentAftermath, {
    props: { aftermath: aftermath(), vaultId: 'vault-1', ...props },
    global: {
      stubs: {
        UButton: {
          props: ['variant', 'size', 'block', 'disabled', 'loading'],
          template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
        },
      },
    },
  })

describe('IncidentAftermath', () => {
  beforeEach(() => {
    clearAftermath.mockReset()
    takeOverflow.mockReset()
    sellOverflow.mockReset()
  })

  it('summarises a victory with its haul and experience', () => {
    const text = mountAftermath().text()

    expect(text).toContain('Incident contained')
    expect(text).toContain('RAIDER ATTACK')
    expect(text).toContain('Power Generator')
    expect(text).toContain('Experience Gained')
    expect(text).toContain('+40 XP')
    expect(text).toContain('Bottle Caps')
    expect(text).toContain('50')
  })

  it('reports the damage the responders took, not dealt', () => {
    const text = mountAftermath().text()

    expect(text).toContain('Damage Taken')
    expect(text).not.toContain('Damage Dealt')
  })

  it('names a defeat plainly', () => {
    const wrapper = mountAftermath({ aftermath: aftermath({ outcome: 'defeat', capsEarned: 0 }) })

    expect(wrapper.text()).toContain('Incident lost')
    expect(wrapper.text()).not.toContain('Incident contained')
  })

  it('admits when the outcome was never reported', () => {
    const wrapper = mountAftermath({ aftermath: aftermath({ outcome: 'unknown' }) })

    expect(wrapper.text()).toContain('Incident ended')
    expect(wrapper.text()).toContain('outcome was not reported')
  })

  it('lists recovered loot with quantities and rarity', () => {
    const wrapper = mountAftermath({
      aftermath: aftermath({
        loot: {
          caps: 50,
          items: [
            { item_type: 'weapon', rarity: 'rare', name: 'Laser Pistol', quantity: 1 },
            { item_type: 'junk', rarity: 'common', name: 'Stimpak', quantity: 3 },
          ],
        },
      }),
    })

    expect(wrapper.text()).toContain('Recovered (2)')
    expect(wrapper.text()).toContain('Laser Pistol')
    expect(wrapper.text()).toContain('Stimpak')
    expect(wrapper.text()).toContain('x3')
  })

  it('omits the recovered section when nothing was recovered', () => {
    expect(mountAftermath().text()).not.toContain('Recovered')
  })

  it('offers take and sell for loot the vault could not hold', async () => {
    const wrapper = mountAftermath({
      aftermath: aftermath({
        unclaimed: [{ item_type: 'weapon', rarity: 'common', name: 'Raider Pistol', quantity: 1 }],
      }),
    })

    expect(wrapper.text()).toContain('Held — Storage Full (1)')
    expect(wrapper.text()).toContain('Raider Pistol')

    const [take, sell] = wrapper.findAll('button')
    await take.trigger('click')
    expect(takeOverflow).toHaveBeenCalledWith('vault-1', 'incident-1', 0, 'test-token')

    await sell.trigger('click')
    expect(sellOverflow).toHaveBeenCalledWith('vault-1', 'incident-1', 0, 'test-token')
  })

  it('omits the held section when everything fit', () => {
    expect(mountAftermath().text()).not.toContain('Held')
  })

  it('dismisses its own room summary', async () => {
    const wrapper = mountAftermath()
    await wrapper.find('button').trigger('click')

    expect(clearAftermath).toHaveBeenCalledWith('room-1')
  })
})
