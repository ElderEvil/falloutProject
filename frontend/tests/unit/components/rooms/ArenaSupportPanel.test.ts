import { describe, expect, it, vi } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { nextTick, reactive } from 'vue'
import ArenaSupportPanel from '@/modules/rooms/components/ArenaSupportPanel.vue'
import type { ArenaMatchDraft } from '@/modules/rooms/composables/useArenaMatchDraft'
import type { ArenaRosterEntry, ArenaRoomState } from '@/modules/rooms/api/arena'

vi.mock('@iconify/vue', () => ({
  Icon: { props: ['icon'], template: '<span :data-icon="icon" />' },
}))

const entry = (id: string, name: string, level: number): ArenaRosterEntry => ({
  id,
  name,
  level,
  health: 80,
  max_health: 100,
})

const match = reactive({
  bench: [entry('c-1', 'Charlie Dweller', 7), entry('d-1', 'Delta Dweller', 9)],
  isFighting: false,
  roomState: {
    events: [
      { id: 'e3', round_seq: 3, kind: 'finish', message: 'Alpha defeated Bravo!' },
      { id: 'e2', round_seq: 2, kind: 'hit', message: 'Alpha hits Bravo for 5' },
      { id: 'e1', round_seq: 1, kind: 'hit', message: 'Bravo hits Alpha for 3' },
    ],
  } as unknown as ArenaRoomState,
  isDone: false,
  injuredFighters: [],
  isHealing: false,
  unassign: vi.fn(),
  clearJournal: vi.fn(),
  healInjured: vi.fn(),
}) as unknown as ArenaMatchDraft

const mountPanel = () =>
  mount(ArenaSupportPanel, {
    props: { match },
    global: { plugins: [createPinia()] },
  })

describe('ArenaSupportPanel', () => {
  it('shows useful bench details without duplicating selected fighters', () => {
    const wrapper = mountPanel()
    const bench = wrapper.get('[aria-label="Arena bench"]')

    expect(bench.text()).toContain('Charlie Dweller')
    expect(bench.text()).toContain('Level 7')
    expect(bench.text()).toContain('80 / 100 HP')
    expect(bench.findAll('[role="progressbar"]')).toHaveLength(2)
  })

  it('removes a benched dweller through the match draft', async () => {
    const wrapper = mountPanel()
    await wrapper.get('button[aria-label="Remove Charlie Dweller from Arena"]').trigger('click')

    expect(match.unassign).toHaveBeenCalledWith(entry('c-1', 'Charlie Dweller', 7))
  })

  it('renders the journal in chronological order', () => {
    const wrapper = mountPanel()
    const items = wrapper.findAll('[aria-label="Battle log"] li')

    expect(items).toHaveLength(3)
    expect(items[0].text()).toContain('Bravo hits Alpha for 3')
    expect(items[1].text()).toContain('Alpha hits Bravo for 5')
    expect(items[2].text()).toContain('FINISH')
  })

  it('clears the journal through the match draft', async () => {
    const wrapper = mountPanel()
    await wrapper
      .findAll('button')
      .find((button) => button.text().includes('CLEAR'))!
      .trigger('click')

    expect(match.clearJournal).toHaveBeenCalledTimes(1)
  })

  it('offers the heal action only after a completed match', async () => {
    const wrapper = mountPanel()
    expect(wrapper.text()).not.toContain('HEAL INJURED')

    match.isDone = true
    match.injuredFighters = [
      {
        id: 'a-1',
        name: 'Alpha',
        level: 5,
        health: 10,
        max_health: 100,
        power: 10,
        is_creature: false,
        is_robot: false,
      },
    ]
    await nextTick()

    await wrapper
      .findAll('button')
      .find((button) => button.text().includes('HEAL INJURED'))!
      .trigger('click')
    expect(match.healInjured).toHaveBeenCalledTimes(1)
  })

  it('keeps room-management actions out of the support panel', () => {
    const wrapper = mountPanel()

    expect(wrapper.text()).not.toContain('Unassign All Dwellers')
    expect(wrapper.text()).not.toContain('Destroy Room')
  })
})
