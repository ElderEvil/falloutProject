import { describe, expect, it } from 'vitest'
import { shallowMount } from '@vue/test-utils'

import IncidentPlaygroundView from '@/modules/combat/views/IncidentPlaygroundView.vue'
import CombatModal from '@/modules/combat/components/incidents/CombatModal.vue'

describe('IncidentPlaygroundView', () => {
  it('offers a modal launcher for every incident type', () => {
    const wrapper = shallowMount(IncidentPlaygroundView)

    const labels = wrapper.findAll('.launcher-btn').map((button) => button.text())
    for (const label of [
      'Raider attack',
      'Radroach infestation',
      'Mole rat attack',
      'Deathclaw spreading',
      'Feral ghoul',
      'Radscorpion attack',
      'Fire containment',
    ]) {
      expect(labels).toContain(label)
    }
  })

  it('opens the modal with the selected incident as preview', async () => {
    const wrapper = shallowMount(IncidentPlaygroundView)

    expect(wrapper.findComponent(CombatModal).exists()).toBe(false)
    const launcher = wrapper
      .findAll('.launcher-btn')
      .find((button) => button.text() === 'Deathclaw spreading')
    expect(launcher).toBeTruthy()
    await launcher!.trigger('click')

    const modal = wrapper.findComponent(CombatModal)
    expect(modal.exists()).toBe(true)
    expect(modal.props('preview')).toBe(true)
    expect(modal.props('previewIncident')).toMatchObject({ type: 'deathclaw_attack' })
    expect(modal.props('previewVaultMedical')).toEqual({ stimpack: 5, radaway: 3 })
  })
})
