import { describe, it, expect, beforeEach } from 'vitest'
import { ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { useFeatureFlagsStore } from '@/modules/dwellers/stores/featureFlags'
import DwellerDetailPane from '@/modules/dwellers/components/DwellerDetailPane.vue'
import {
  createMockDwellerDetailContext,
  mountWithDwellerContext,
} from '../../helpers/dwellerDetailContext'
import type { Dweller } from '@/modules/dwellers/models/dweller'

let pinia: ReturnType<typeof createPinia>

beforeEach(() => {
  pinia = createPinia()
  setActivePinia(pinia)
  const flags = useFeatureFlagsStore()
  flags.raceMechanics = true
  flags.factionMechanics = true
})
// The header owns the identity lockup now, so gender/rarity/age and the
// race/faction/state chips are asserted here rather than on the card.
const dweller = {
  id: '11111111-2222-3333-4444-555555555555',
  first_name: 'Nora',
  last_name: 'Vance',
  gender: 'female',
  rarity: 'rare',
  age_group: 'adult',
  is_adult: true,
  is_dead: false,
  is_permanently_dead: false,
  status: 'working',
  level: 12,
  health: 82,
  max_health: 100,
  radiation: 12,
  happiness: 64,
  experience: 0,
  stimpack: 0,
  radaway: 0,
  room: { id: 'room-1', name: 'Power Generator' },
  visual_attributes: { race: 'ghoul', faction: 'raiders', state_of_being: 'sane' },
} as unknown as Dweller

function mountPane() {
  const ctx = createMockDwellerDetailContext({ dweller: ref(dweller) as never })
  return mountWithDwellerContext(DwellerDetailPane, {
    context: ctx,
    global: { plugins: [pinia], stubs: { RouterLink: true } },
  } as never)
}

describe('DwellerDetailPane header lockup', () => {
  it('names the dweller and says what they are doing', () => {
    const wrapper = mountPane()

    expect(wrapper.find('.dweller-name').text()).toContain('Nora Vance')
    expect(wrapper.findAll('.activity-caption')).toHaveLength(1)
    expect(wrapper.find('.activity-caption').text()).toBe('Power Generator')
  })

  it('keeps the room out of the name row', () => {
    const wrapper = mountPane()

    expect(wrapper.find('.name-line').text()).not.toContain('Power Generator')
  })

  it('shows gender, rarity and age badges', () => {
    const wrapper = mountPane()

    const badges = wrapper.findAll('.dweller-badge')
    expect(badges.find((b) => b.attributes('aria-label') === 'Gender: Female')).toBeDefined()
    expect(badges.find((b) => b.attributes('aria-label') === 'Rarity: Rare')).toBeDefined()
    expect(badges.find((b) => b.attributes('aria-label') === 'Age group: Adult')).toBeDefined()
  })

  it('shows the race, faction and state-of-being chips', () => {
    const wrapper = mountPane()

    const identity = wrapper.find('[aria-label="Dweller identity"]')
    expect(identity.exists()).toBe(true)
    expect(identity.text()).toContain('Ghoul')
    expect(identity.text()).toContain('Raiders')
    expect(identity.text()).toContain('Sane')
  })
})
