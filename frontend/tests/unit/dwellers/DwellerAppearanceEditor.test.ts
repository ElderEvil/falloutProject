import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DwellerAppearanceEditor from '@/modules/dwellers/components/DwellerAppearanceEditor.vue'
import type { Dweller } from '@/modules/dwellers/models/dweller'

const baseDweller = {
  id: 'test-123',
  first_name: 'Test',
  last_name: 'Dweller',
  level: 1,
  health: 100,
  max_health: 100,
  radiation: 0,
  happiness: 50,
  status: 'idle',
  gender: 'male',
  rarity: 'common',
  strength: 1,
  perception: 1,
  endurance: 1,
  charisma: 1,
  intelligence: 1,
  agility: 1,
  luck: 1,
  vault: { id: 'vault-1', number: 1 },
  room: null,
  weapon: null,
  outfit: null,
} as unknown as Dweller

async function createWrapper(dweller: Dweller, modelValue = true) {
  return mount(DwellerAppearanceEditor, {
    props: {
      dweller,
      modelValue,
    },
    global: {
      stubs: {
        UModal: {
          template: `
            <div v-if="modelValue" class="modal-stub">
              <slot />
              <slot name="footer" />
            </div>
          `,
          props: ['modelValue'],
        },
        UTooltip: {
          template: '<div><slot /></div>',
        },
        UButton: {
          template: '<button @click="$emit(\'click\')"><slot /></button>',
        },
      },
    },
  })
}

describe('DwellerAppearanceEditor', () => {
  it('renders modal when modelValue is true', async () => {
    const wrapper = await createWrapper(baseDweller, true)
    expect(wrapper.find('.editor-scroll').exists()).toBe(true)
  })

  it('does not render modal content when modelValue is false', async () => {
    const wrapper = await createWrapper(baseDweller, false)
    expect(wrapper.find('.editor-scroll').exists()).toBe(false)
  })

  it('initializes form from dweller visual_attributes', async () => {
    const dwellerWithAttrs = {
      ...baseDweller,
      visual_attributes: {
        race: 'ghoul',
        faction: 'raiders',
        height: 'tall',
      },
    } as unknown as Dweller

    const wrapper = await createWrapper(dwellerWithAttrs)
    expect(wrapper.findAll('[role="combobox"]')[0].text()).toContain('Ghoul')
  })

  it('sets defaults when dweller has no visual_attributes', async () => {
    const wrapper = await createWrapper(baseDweller)
    expect(wrapper.findAll('[role="combobox"]')[0].text()).toContain('Human')
  })

  it('emits saved with cleaned attributes on save', async () => {
    const dwellerWithAttrs = {
      ...baseDweller,
      visual_attributes: {
        race: 'human',
        faction: 'vault_dweller',
        height: 'average',
      },
    } as unknown as Dweller

    const wrapper = await createWrapper(dwellerWithAttrs)

    // Find and click Save button by its text content
    const saveBtn = wrapper.findAll('button').filter((b) => b.text().includes('Save Changes'))[0]
    expect(saveBtn).toBeDefined()
    await saveBtn!.trigger('click')

    expect(wrapper.emitted('saved')).toBeTruthy()
    const saved = wrapper.emitted('saved')![0][0] as Record<string, unknown>
    expect(saved.race).toBe('human')
    expect(saved.height).toBe('average')
  })

  it('saves the age selected with the range control', async () => {
    const dwellerWithAge = {
      ...baseDweller,
      visual_attributes: { age: 25 },
    } as unknown as Dweller

    const wrapper = await createWrapper(dwellerWithAge)
    await wrapper.find('input[type="range"]').setValue('36')
    await wrapper
      .findAll('button')
      .filter((b) => b.text().includes('Save Changes'))[0]!
      .trigger('click')

    const saved = wrapper.emitted('saved')![0][0] as Record<string, unknown>
    expect(saved.age).toBe(36)
  })

  it('shows state_of_being for non-human races', async () => {
    const dwellerWithGhoul = {
      ...baseDweller,
      visual_attributes: { race: 'ghoul', faction: 'none' },
    } as unknown as Dweller

    const wrapper = await createWrapper(dwellerWithGhoul)
    expect(wrapper.text()).toContain('State of Being')
  })

  it('hides state_of_being for human race', async () => {
    const wrapper = await createWrapper(baseDweller)
    expect(wrapper.text()).not.toContain('State of Being')
  })

  it('shows one appearance section at a time', async () => {
    const wrapper = await createWrapper(baseDweller)
    const sections = wrapper.findAll('.editor-section')

    expect(sections[0].attributes('style')).toBeUndefined()
    expect(sections[1].attributes('style')).toContain('display: none')

    await wrapper
      .findAll('.section-nav-button')
      .filter((button) => button.text().includes('Face'))[0]!
      .trigger('click')

    expect(sections[0].attributes('style')).toContain('display: none')
    expect(sections[2].attributes('style')).not.toContain('display: none')
  })

  it('closes modal on cancel', async () => {
    const wrapper = await createWrapper(baseDweller)

    // Click the Cancel button
    const cancelBtn = wrapper.findAll('button').filter((b) => b.text().includes('Cancel'))[0]
    await cancelBtn?.trigger('click')

    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')![0]).toEqual([false])
  })

  it('filters factions based on selected race', async () => {
    const dwellerWithSuperMutant = {
      ...baseDweller,
      visual_attributes: { race: 'super_mutant', faction: 'none' },
    } as unknown as Dweller

    const wrapper = await createWrapper(dwellerWithSuperMutant)

    const selects = wrapper.findAll('[role="combobox"]')
    expect(selects.length).toBeGreaterThanOrEqual(2)
    await selects[1].trigger('click')
    const factionOptions = wrapper.findAll('[role="option"]').map((option) => option.text())

    // Super mutants should not have human-only factions
    expect(factionOptions).not.toContain('Vault Dweller')
    expect(factionOptions).not.toContain('Brotherhood Of Steel')
    // But should have their allowed factions
    expect(factionOptions).toContain('Super Mutant Tribe')
  })

})
