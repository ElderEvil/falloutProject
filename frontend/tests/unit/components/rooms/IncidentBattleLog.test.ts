import { describe, expect, it } from 'vitest'
import { nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import IncidentBattleLog from '@/modules/rooms/components/IncidentBattleLog.vue'

const event = (overrides: Record<string, unknown> = {}) => ({
  id: 'e1',
  kind: 'round',
  message: 'Raiders push into the room.',
  data: null,
  ...overrides,
})

const mountLog = (events: unknown[] = []) =>
  mount(IncidentBattleLog, { props: { events: events as never } })

const setScrollMetrics = (
  el: Element,
  { scrollHeight, clientHeight, scrollTop }: Record<string, number>
) => {
  Object.defineProperty(el, 'scrollHeight', { value: scrollHeight, configurable: true })
  Object.defineProperty(el, 'clientHeight', { value: clientHeight, configurable: true })
  Object.defineProperty(el, 'scrollTop', { value: scrollTop, writable: true, configurable: true })
}

describe('IncidentBattleLog', () => {
  it('renders each round message in journal order', () => {
    const wrapper = mountLog([
      event({ id: 'e1', message: 'First round' }),
      event({ id: 'e2', message: 'Second round' }),
    ])

    const items = wrapper.findAll('li')
    expect(items).toHaveLength(2)
    expect(items[0].text()).toContain('First round')
    expect(items[1].text()).toContain('Second round')
  })

  it('announces rounds politely instead of interrupting', () => {
    const log = mountLog([event()]).find('[aria-label="Battle log"]')
    expect(log.attributes('aria-live')).toBe('polite')
  })

  it('states when no rounds have been fought', () => {
    expect(mountLog().text()).toContain('No rounds fought yet.')
  })

  it('pairs damage with text rather than colour alone', () => {
    const wrapper = mountLog([
      event({ id: 'e1', message: 'Trade fire.', data: { damage_to_threat: 12 } }),
      event({ id: 'e2', message: 'They hit back.', data: { damage_to_dwellers: 7 } }),
    ])

    expect(wrapper.text()).toContain('-12 threat')
    expect(wrapper.text()).toContain('-7 dwellers')
  })

  it('reports containment gain as a percentage', () => {
    const wrapper = mountLog([event({ id: 'e1', message: 'Foam spreads.', data: { amount: 0.25 } })])
    expect(wrapper.text()).toContain('+25% contained')
  })

  it('rounds fractional damage so the log reads cleanly', () => {
    const wrapper = mountLog([
      event({ id: 'e1', message: 'Trade fire.', data: { damage_to_threat: 4.5200000000000005 } }),
    ])

    expect(wrapper.text()).toContain('-4 threat')
    expect(wrapper.text()).not.toContain('4.5200000000000005')
  })

  it('labels each entry with its event kind', () => {
    const wrapper = mountLog([
      event({ id: 'e1', kind: 'responders_dispatched', message: 'Hazard team dispatched.' }),
      event({ id: 'e2', kind: 'spread', message: 'Fire spreads.' }),
    ])

    expect(wrapper.text()).toContain('DISPATCHED')
    expect(wrapper.text()).toContain('SPREAD')
  })

  it('does not move focus when new rounds arrive', async () => {
    const wrapper = mountLog([event({ id: 'e1' })])
    const log = wrapper.find('[aria-label="Battle log"]').element
    setScrollMetrics(log, { scrollHeight: 100, clientHeight: 100, scrollTop: 0 })

    const active = document.activeElement
    await wrapper.setProps({ events: [event({ id: 'e1' }), event({ id: 'e2' })] as never })
    await nextTick()

    expect(document.activeElement).toBe(active)
  })

  it('follows the newest round when the reader is already at the bottom', async () => {
    const wrapper = mountLog([event({ id: 'e1' })])
    const log = wrapper.find('[aria-label="Battle log"]').element
    setScrollMetrics(log, { scrollHeight: 200, clientHeight: 100, scrollTop: 100 })

    await wrapper.setProps({ events: [event({ id: 'e1' }), event({ id: 'e2' })] as never })
    await nextTick()
    await nextTick()

    expect(log.scrollTop).toBe(200)
    expect(wrapper.text()).not.toContain('New rounds below')
  })

  it('opens a pre-populated log at the newest round', async () => {
    const wrapper = mountLog([event({ id: 'e1' }), event({ id: 'e2' })])
    const log = wrapper.find('[aria-label="Battle log"]').element
    setScrollMetrics(log, { scrollHeight: 300, clientHeight: 100, scrollTop: 0 })

    await nextTick()
    await nextTick()

    expect(log.scrollTop).toBe(300)
  })

  it('offers a jump affordance instead of yanking a reader who scrolled away', async () => {
    const wrapper = mountLog([event({ id: 'e1' })])
    const log = wrapper.find('[aria-label="Battle log"]').element
    setScrollMetrics(log, { scrollHeight: 400, clientHeight: 100, scrollTop: 0 })
    await wrapper.find('[aria-label="Battle log"]').trigger('scroll')

    await wrapper.setProps({ events: [event({ id: 'e1' }), event({ id: 'e2' })] as never })
    await nextTick()
    await nextTick()

    expect(log.scrollTop).toBe(0)
    expect(wrapper.text()).toContain('New rounds below')
  })

  it('collapses consecutive identical entries into one row with a count badge', () => {
    const wrapper = mountLog([
      event({ id: 'e1', kind: 'round', message: 'Trade fire.' }),
      event({ id: 'e2', kind: 'round', message: 'Trade fire.' }),
      event({ id: 'e3', kind: 'round', message: 'Trade fire.' }),
    ])

    const items = wrapper.findAll('li')
    expect(items).toHaveLength(1)
    expect(items[0].text()).toContain('Trade fire.')
    expect(items[0].text()).toContain('×3')
  })

  it('keeps non-consecutive identical entries as separate rows', () => {
    const wrapper = mountLog([
      event({ id: 'e1', kind: 'round', message: 'Trade fire.' }),
      event({ id: 'e2', kind: 'spread', message: 'Fire spreads.' }),
      event({ id: 'e3', kind: 'round', message: 'Trade fire.' }),
    ])

    expect(wrapper.findAll('li')).toHaveLength(3)
  })

  it('omits the count badge for a single entry', () => {
    const wrapper = mountLog([event({ id: 'e1', kind: 'round', message: 'Trade fire.' })])

    expect(wrapper.text()).not.toContain('×')
  })

  it('keeps the first delta when collapsing identical entries', () => {
    const wrapper = mountLog([
      event({ id: 'e1', kind: 'round', message: 'Trade fire.', data: { damage_to_threat: 12 } }),
      event({ id: 'e2', kind: 'round', message: 'Trade fire.', data: { damage_to_threat: 8 } }),
    ])

    expect(wrapper.text()).toContain('-12 threat')
  })

  it('lists unavailable responders by first name', () => {
    const wrapper = mountLog([
      event({ id: 'e1', kind: 'round', message: 'Trade fire.', data: { skipped: ['Alice', 'Bob'] } }),
    ])

    expect(wrapper.text()).toContain('Unavailable: Alice, Bob')
  })

  it('omits the unavailable suffix when nobody was skipped', () => {
    const wrapper = mountLog([
      event({ id: 'e1', kind: 'round', message: 'Trade fire.', data: { skipped: [] } }),
    ])

    expect(wrapper.text()).not.toContain('Unavailable')
  })
})
