import { afterEach, describe, expect, it, vi } from 'vite-plus/test'
import { createIconifyMock } from '../../helpers/mocks'
import { mount, type VueWrapper } from '@vue/test-utils'
import PetCarrierOpenModal from '@/modules/storage/components/PetCarrierOpenModal.vue'
import type { components } from '@/core/types/api.generated'

vi.mock('@iconify/vue', () => createIconifyMock())

type PetCarrierOpened = components['schemas']['PetCarrierOpened']

const result: PetCarrierOpened = {
  reward_type: 'pet_carrier',
  pet: {
    id: 'pet-1',
    name: 'Husky',
    rarity: 'rare',
    value: 100,
    image_url: '/static/pet_images/FOS Husky.png',
    created_at: '2026-10-01T00:00:00Z',
    updated_at: '2026-10-01T00:00:00Z',
    dweller_id: null,
    storage_id: 'storage-1',
    effect: {
      strength: 0,
      perception: 0,
      endurance: 0,
      charisma: 0,
      intelligence: 0,
      agility: 2,
      luck: 0,
      max_health: 0,
      damage_pct: 0.25,
      incident_response_pct: 0,
      radiation_resist_pct: 0,
      happiness: 0,
      caps_pct: 0,
      xp_pct: 0,
      training_speed_pct: 0,
      twin_chance_pct: 0,
    },
    description: 'A sturdy companion.',
  },
}

const mountModal = (props: Record<string, unknown> = {}) =>
  mount(PetCarrierOpenModal, {
    props: { show: true, result: null, ...props },
    global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
  })

const findButton = (wrapper: VueWrapper, label: string) =>
  wrapper.findAll('button').find((button) => button.text().includes(label))

describe('PetCarrierOpenModal', () => {
  let wrapper: VueWrapper | null = null

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
  })

  it('reveals only on demand', async () => {
    wrapper = mountModal()

    expect(wrapper.text()).toContain('Reveal Pet')
    expect(wrapper.text()).not.toContain('Husky')

    await findButton(wrapper, 'Reveal Pet')!.trigger('click')

    expect(wrapper.emitted('reveal')).toHaveLength(1)
  })

  it('shows the rolled pet, its description and catalog effect', () => {
    wrapper = mountModal({ result })

    expect(wrapper.text()).toContain('Husky')
    expect(wrapper.text()).toContain('A sturdy companion.')
    expect(wrapper.text()).toContain('Agility +2')
    expect(wrapper.text()).toContain('Damage +25%')
  })

  it('closes only after the reveal', async () => {
    wrapper = mountModal({ result })

    await findButton(wrapper, 'Done')!.trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('disables the footer while opening and surfaces the error', () => {
    wrapper = mountModal({ opening: true })
    expect(findButton(wrapper, 'Opening…')?.attributes('disabled')).toBeDefined()
    wrapper.unmount()

    wrapper = mountModal({ error: 'No pets available' })
    expect(wrapper.text()).toContain('No pets available')
  })
})
