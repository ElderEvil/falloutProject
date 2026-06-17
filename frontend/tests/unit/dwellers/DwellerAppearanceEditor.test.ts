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
    const raceSelect = wrapper.find('select').element as HTMLSelectElement
    expect(raceSelect.value).toBe('ghoul')
  })

  it('sets defaults when dweller has no visual_attributes', async () => {
    const wrapper = await createWrapper(baseDweller)
    const raceSelect = wrapper.find('select').element as HTMLSelectElement
    expect(raceSelect.value).toBe('human')
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

    // Get the select elements (race is first, faction is second)
    const selects = wrapper.findAll('select')
    expect(selects.length).toBeGreaterThanOrEqual(2)

    const factionSelect = selects[1].element as HTMLSelectElement
    const factionOptions = Array.from(factionSelect.options).map((o) => o.value)

    // Super mutants should not have human-only factions
    expect(factionOptions).not.toContain('vault_dweller')
    expect(factionOptions).not.toContain('brotherhood_of_steel')
    // But should have their allowed factions
    expect(factionOptions).toContain('super_mutant_tribe')
  })
})
