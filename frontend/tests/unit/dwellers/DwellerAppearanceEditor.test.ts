import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useFeatureFlagsStore } from '@/modules/dwellers/stores/featureFlags'
import DwellerAppearanceEditor from '@/modules/dwellers/components/DwellerAppearanceEditor.vue'
import type { Dweller } from '@/modules/dwellers/models/dweller'

// The editor reads the backend identity catalogue instead of mirroring it.
vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({ token: 'test-token' }),
}))

vi.mock('@/core/utils/errorHandler', () => ({
  handleStoreError: vi.fn(),
}))

vi.mock('@/modules/dwellers/services/dwellerService', () => ({
  getFeatureFlags: vi.fn().mockResolvedValue({ race_mechanics: true, faction_mechanics: true }),
  getIdentityOptions: vi.fn().mockResolvedValue({
    races: ['human', 'ghoul', 'super_mutant', 'synth'],
    factions_by_race: {
      human: ['vault_dweller', 'brotherhood_of_steel', 'enclave'],
      ghoul: ['vault_dweller', 'raiders', 'children_of_atom', 'none'],
      super_mutant: ['super_mutant_tribe', 'raiders', 'none'],
      synth: ['the_institute', 'railroad', 'none'],
    },
    states_by_race: {
      ghoul: ['sane', 'wild', 'feral'],
      super_mutant: ['mild', 'average', 'behemoth'],
      synth: ['gen_3', 'gen_2', 'gen_1'],
    },
  }),
  getAppearanceOptions: vi.fn().mockResolvedValue({
    skin_tones_by_race: {
      human: ['Pale', 'Tan'],
      ghoul: ['Pale Grey', 'Ashen'],
      super_mutant: ['Light Green', 'Green'],
      synth: ['Synthetic Fair', 'Metallic Silver'],
    },
    builds_by_race: {
      human: ['Slim', 'Athletic'],
      ghoul: ['Skeletal'],
      super_mutant: ['Muscular'],
      synth: ['Slender'],
    },
    haircuts_by_race: {
      human: ['Short Hair', 'Buzz Cut'],
      ghoul: ['Patchy Hair'],
      super_mutant: ['Bald'],
      synth: ['Clean Cut'],
    },
    headgear_by_race: {
      human: ['None', 'Combat Helmet'],
      ghoul: ['None', 'Leather Hood'],
      super_mutant: ['None', 'Metal Helmet'],
      synth: ['None', 'Institute Hood'],
    },
    expressions: ['neutral', 'smiling'],
    poses: ['Standing confidently', 'Combat ready'],
    backgrounds: ['Vault Interior', 'Wasteland Ruins'],
    heights: ['tall', 'average', 'short'],
    eye_colors: ['blue', 'green'],
    hair_colors: ['blonde', 'black'],
  }),
}))

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

function enableFactionSwitch(): void {
  const flags = useFeatureFlagsStore()
  flags.raceMechanics = true
  flags.factionMechanics = true
}

async function createWrapper(dweller: Dweller, modelValue = true) {
  const wrapper = mount(DwellerAppearanceEditor, {
    props: {
      dweller,
      modelValue,
    },
    global: {
      stubs: {
        Teleport: { template: '<div><slot /></div>' },
      },
    },
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  setActivePinia(createPinia())
  enableFactionSwitch()
})

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

  it('does not randomise before the identity catalogue loads', async () => {
    const { getIdentityOptions } = await import('@/modules/dwellers/services/dwellerService')
    vi.mocked(getIdentityOptions).mockResolvedValueOnce({
      races: [],
      factions_by_race: {},
      states_by_race: {},
    } as never)

    const dwellerWithAttrs = {
      ...baseDweller,
      visual_attributes: { race: 'ghoul', faction: 'raiders' },
    } as unknown as Dweller

    const wrapper = await createWrapper(dwellerWithAttrs)

    const randomizeBtn = wrapper.findAll('button').filter((b) => b.text().includes('Randomize'))[0]
    expect(randomizeBtn).toBeDefined()
    await randomizeBtn!.trigger('click')

    const saveBtn = wrapper.findAll('button').filter((b) => b.text().includes('Save Changes'))[0]
    await saveBtn!.trigger('click')

    const saved = wrapper.emitted('saved')![0][0] as Record<string, unknown>
    expect(saved.race).toBe('ghoul')
    expect(saved.faction).toBe('raiders')
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
    const thumb = wrapper.find('[role="slider"]')
    for (let i = 0; i < 11; i++) {
      await thumb.trigger('keydown', { key: 'ArrowRight' })
    }
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
    // reka-ui opens the listbox on pointerdown (not click).
    selects[1].element.dispatchEvent(new MouseEvent('pointerdown', { button: 0, bubbles: true }))
    await flushPromises()
    const factionOptions = wrapper.findAll('[role="option"]').map((option) => option.text())

    // Super mutants should not have human-only factions
    expect(factionOptions).not.toContain('Vault Dweller')
    expect(factionOptions).not.toContain('Brotherhood Of Steel')
    // But should have their allowed factions
    expect(factionOptions).toContain('Super Mutant Tribe')
  })

})

  it('upgrades the provisional faction default once the switch resolves', async () => {
    // The immediate watcher runs before the flags land, so a dweller without attributes
    // starts at the system value; the switch then restores the normal default.
    const wrapper = await createWrapper(baseDweller as Dweller)
    await flushPromises()

    expect(wrapper.text()).toContain('Vault Dweller')
  })

  it('hides the faction field while the switch is off', async () => {
    const wrapper = await createWrapper(baseDweller as Dweller)
    await flushPromises()

    // The catalogue load settles first; the switch then hides the field reactively.
    useFeatureFlagsStore().factionMechanics = false
    await flushPromises()

    expect(wrapper.text()).not.toContain('Faction')
    expect(wrapper.text()).toContain('Race')
  })
