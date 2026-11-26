import { describe, it, expect } from 'vite-plus/test'
import { mount, type VueWrapper } from '@vue/test-utils'
import HappinessDashboard from '@/modules/vault/components/HappinessDashboard.vue'

type DashboardProps = InstanceType<typeof HappinessDashboard>['$props']

const defaultProps = {
  vaultHappiness: 75,
  dwellerCount: 10,
  distribution: {
    high: 3,
    medium: 4,
    low: 2,
    critical: 1,
  },
}

/** Mounts the dashboard with the required props filled; callers override what the case needs. */
function render(props: Partial<DashboardProps> = {}): VueWrapper {
  return mount(HappinessDashboard, {
    props: { ...defaultProps, ...props } as DashboardProps,
  })
}

function action(wrapper: VueWrapper, label: string) {
  const found = wrapper.findAll('button').find((button) => button.text().includes(label))
  if (!found) throw new Error(`No action button labelled "${label}"`)
  return found
}

describe('HappinessDashboard', () => {
  it.each([false, true])(
    'only exposes embedded dashboard content when loaded, loading=%s',
    (loading) => {
      const wrapper = render({ embedded: true, loading })

      expect(wrapper.text().includes('DWELLER DISTRIBUTION')).toBe(!loading)
      expect(wrapper.findAll('button').length > 0).toBe(!loading)
      wrapper.unmount()
    }
  )

  it('keeps attention actions usable without embedding', async () => {
    const wrapper = render()

    expect(wrapper.text()).toContain('75%')
    await action(wrapper, 'View Low Happiness').trigger('click')

    expect(wrapper.emitted('view-low-happiness')).toHaveLength(1)
    wrapper.unmount()
  })

  it('offers low-happiness attention even without resource, incident, idle, or care warnings', () => {
    expect(
      render({ radioHappinessMode: true })
        .findAll('button')
        .some((button) => button.text().includes('View Low Happiness'))
    ).toBe(true)
  })

  it('should render happiness gauge with correct percentage', () => {
    const wrapper = render()

    expect(wrapper.text()).toContain('75%')
    expect(wrapper.text()).toContain('EXCELLENT')
  })

  it.each([
    [90, 'EXCELLENT'],
    [60, 'GOOD'],
    [35, 'POOR'],
    [15, 'CRITICAL'],
  ])('labels %s%% happiness as %s', (vaultHappiness, label) => {
    expect(render({ vaultHappiness }).text()).toContain(label)
  })

  it('should display dweller distribution correctly', () => {
    const wrapper = render()

    expect(wrapper.text()).toContain('3') // high count
    expect(wrapper.text()).toContain('4') // medium count
    expect(wrapper.text()).toContain('2') // low count
    expect(wrapper.text()).toContain('1') // critical count
  })

  it('should calculate distribution percentages correctly', () => {
    const wrapper = render()

    // 3/10 = 30%, 4/10 = 40%, 2/10 = 20%, 1/10 = 10%
    expect(wrapper.text()).toContain('(30%)')
    expect(wrapper.text()).toContain('(40%)')
    expect(wrapper.text()).toContain('(20%)')
    expect(wrapper.text()).toContain('(10%)')
  })

  it('should show active modifiers when provided', () => {
    const wrapper = render({ lowResourceCount: 2, activeIncidentCount: 3, idleDwellerCount: 5 })

    expect(wrapper.text()).toContain('Low Resources')
    expect(wrapper.text()).toContain('Active Incidents (3)')
    expect(wrapper.text()).toContain('Idle Dwellers (5)')
  })

  it('should show radio happiness mode modifier', () => {
    expect(render({ radioHappinessMode: true }).text()).toContain('Radio Happiness Mode')
  })

  it('should not show modifiers section when no modifiers exist', () => {
    const wrapper = render({
      lowResourceCount: 0,
      activeIncidentCount: 0,
      idleDwellerCount: 0,
      radioHappinessMode: false,
    })

    expect(wrapper.text()).not.toContain('ACTIVE MODIFIERS')
  })

  it('should show quick actions when there are negative modifiers', () => {
    const text = render({ idleDwellerCount: 5 }).text()

    expect(text).toContain('QUICK ACTIONS')
    expect(text).toContain('Assign Idle Dwellers')
  })

  it.each([
    ['assign-idle', 'Assign Idle Dwellers', { idleDwellerCount: 5 }],
    ['activate-radio', 'Activate Radio', { idleDwellerCount: 5, radioHappinessMode: false }],
    ['view-low-happiness', 'View Low Happiness', { idleDwellerCount: 5 }],
    [
      'treat-irradiated',
      'Treat Irradiated',
      { idleDwellerCount: 1, severelyIrradiatedDwellerCount: 4 },
    ],
  ])('emits %s when its quick action is clicked', async (event, label, props) => {
    const wrapper = render(props)

    await action(wrapper, label).trigger('click')

    expect(wrapper.emitted(event)).toBeTruthy()
  })

  it('should hide the treatment button when nobody is severely irradiated', () => {
    expect(render({ idleDwellerCount: 1, severelyIrradiatedDwellerCount: 0 }).text()).not.toContain(
      'Treat Irradiated'
    )
  })

  it('should hide the treatment button for a single severely irradiated dweller', () => {
    const text = render({ idleDwellerCount: 5, severelyIrradiatedDwellerCount: 1 }).text()

    expect(text).toContain('QUICK ACTIONS')
    expect(text).not.toContain('Treat Irradiated')
  })

  it('should not show "Activate Radio Mode" button when already active', () => {
    expect(render({ radioHappinessMode: true, idleDwellerCount: 1 }).text()).not.toContain(
      'Activate Radio Mode'
    )
  })

  it('should not show "Assign Idle Dwellers" when no idle dwellers', () => {
    expect(render({ idleDwellerCount: 0, lowResourceCount: 1 }).text()).not.toContain(
      'Assign Idle Dwellers'
    )
  })

  it('should handle zero dweller count', () => {
    const wrapper = render({
      dwellerCount: 0,
      distribution: { high: 0, medium: 0, low: 0, critical: 0 },
    })

    // Should not crash and show 0% for all
    expect(wrapper.text()).toContain('(0%)')
  })

  it('should apply correct colors based on happiness level', () => {
    expect(render({ vaultHappiness: 85 }).find('.gauge-value').attributes('style')).toContain(
      'var(--color-theme-primary)'
    )
  })

  it('should render SVG gauge with correct dimensions', () => {
    const svg = render().find('svg')

    expect(svg.exists()).toBe(true)
    expect(svg.attributes('viewBox')).toBe('0 0 160 160')
  })

  it('should show trend icon', () => {
    const wrapper = render()
    const trendIcon = wrapper.find('.gauge-trend')

    expect(trendIcon.exists()).toBe(true)
    expect(wrapper.find('.gauge-value-row').element.firstElementChild).toBe(trendIcon.element)
  })

  it('should not exceed 5 modifiers', () => {
    const wrapper = render({
      lowResourceCount: 3,
      activeIncidentCount: 10,
      idleDwellerCount: 5,
      radioHappinessMode: true,
    })

    expect(wrapper.findAll('.modifier-item').length).toBeLessThanOrEqual(5)
  })
})
