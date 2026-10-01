import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PetCard from '@/modules/pets/components/PetCard.vue'
import type { Pet } from '@/modules/pets/models/pet'

const neutralEffect = {
  strength: 0,
  perception: 0,
  endurance: 0,
  charisma: 0,
  intelligence: 0,
  agility: 0,
  luck: 0,
  max_health: 0,
  damage_pct: 0,
  incident_response_pct: 0,
  radiation_resist_pct: 0,
  happiness: 0,
  caps_pct: 0,
  xp_pct: 0,
  training_speed_pct: 0,
}

function makePet(overrides: Partial<Pet> = {}): Pet {
  return {
    id: 'pet-1',
    name: 'Dogmeat',
    rarity: 'rare',
    value: 100,
    image_url: null,
    dweller_id: null,
    storage_id: 'storage-1',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    effect: neutralEffect,
    ...overrides,
  }
}

describe('PetCard', () => {
  it('renders the pet name and rarity', () => {
    const wrapper = mount(PetCard, {
      props: { pet: makePet() },
      global: { stubs: { Icon: true } },
    })

    expect(wrapper.text()).toContain('Dogmeat')
    expect(wrapper.text()).toContain('Pet')
    expect(wrapper.text()).toContain('rare')
  })

  it('renders bonus chips from the pet effect', () => {
    const wrapper = mount(PetCard, {
      props: {
        pet: makePet({
          effect: {
            ...neutralEffect,
            strength: 2,
            max_health: 50,
            damage_pct: 0.25,
            xp_pct: 0.5,
          },
        }),
      },
      global: { stubs: { Icon: true } },
    })

    expect(wrapper.text()).toContain('Strength +2')
    expect(wrapper.text()).toContain('Max HP +50')
    expect(wrapper.text()).toContain('Damage +25%')
    expect(wrapper.text()).toContain('XP +50%')
  })

  it('renders no chips for a neutral pet', () => {
    const wrapper = mount(PetCard, {
      props: { pet: makePet() },
      global: { stubs: { Icon: true } },
    })

    expect(wrapper.findAll('[data-slot="badge"]')).toHaveLength(0)
  })

  it('emits equip for an available pet', async () => {
    const wrapper = mount(PetCard, {
      props: { pet: makePet(), showActions: true },
      global: { stubs: { Icon: true } },
    })

    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('equip')).toHaveLength(1)
  })

  it('emits unequip for an equipped pet', async () => {
    const wrapper = mount(PetCard, {
      props: { pet: makePet(), showActions: true, equipped: true },
      global: { stubs: { Icon: true } },
    })

    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('unequip')).toHaveLength(1)
  })
})