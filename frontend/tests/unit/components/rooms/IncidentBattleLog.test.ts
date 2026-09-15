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
})
