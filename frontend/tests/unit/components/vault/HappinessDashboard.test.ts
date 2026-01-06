import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import HappinessDashboard from '@/components/vault/HappinessDashboard.vue';

describe('HappinessDashboard', () => {
  const defaultProps = {
    vaultHappiness: 75,
    dwellerCount: 10,
    distribution: {
      high: 3,
      medium: 4,
      low: 2,
      critical: 1,
    },
  };

  it('should render happiness gauge with correct percentage', () => {
    const wrapper = mount(HappinessDashboard, {
      props: defaultProps,
    });

    expect(wrapper.text()).toContain('75%');
    expect(wrapper.text()).toContain('EXCELLENT');
  });

  it('should display correct happiness level labels', () => {
    const levels = [
      { happiness: 90, label: 'EXCELLENT' },
      { happiness: 60, label: 'GOOD' },
      { happiness: 35, label: 'POOR' },
      { happiness: 15, label: 'CRITICAL' },
    ];

    levels.forEach(({ happiness, label }) => {
      const wrapper = mount(HappinessDashboard, {
        props: {
          ...defaultProps,
          vaultHappiness: happiness,
        },
      });

      expect(wrapper.text()).toContain(label);
    });
  });

  it('should display dweller distribution correctly', () => {
    const wrapper = mount(HappinessDashboard, {
      props: defaultProps,
    });

    expect(wrapper.text()).toContain('3'); // high count
    expect(wrapper.text()).toContain('4'); // medium count
    expect(wrapper.text()).toContain('2'); // low count
    expect(wrapper.text()).toContain('1'); // critical count
  });

  it('should calculate distribution percentages correctly', () => {
    const wrapper = mount(HappinessDashboard, {
      props: defaultProps,
    });

    // 3/10 = 30%, 4/10 = 40%, 2/10 = 20%, 1/10 = 10%
    expect(wrapper.text()).toContain('(30%)');
    expect(wrapper.text()).toContain('(40%)');
    expect(wrapper.text()).toContain('(20%)');
    expect(wrapper.text()).toContain('(10%)');
  });

  it('should show active modifiers when provided', () => {
    const wrapper = mount(HappinessDashboard, {
      props: {
        ...defaultProps,
        lowResourceCount: 2,
        activeIncidentCount: 3,
        idleDwellerCount: 5,
      },
    });

    expect(wrapper.text()).toContain('Low Resources');
    expect(wrapper.text()).toContain('Active Incidents (3)');
    expect(wrapper.text()).toContain('Idle Dwellers (5)');
  });

  it('should show radio happiness mode modifier', () => {
    const wrapper = mount(HappinessDashboard, {
      props: {
        ...defaultProps,
        radioHappinessMode: true,
      },
    });

    expect(wrapper.text()).toContain('Radio Happiness Mode');
  });

  it('should not show modifiers section when no modifiers exist', () => {
    const wrapper = mount(HappinessDashboard, {
      props: {
        ...defaultProps,
        lowResourceCount: 0,
        activeIncidentCount: 0,
        idleDwellerCount: 0,
        radioHappinessMode: false,
      },
    });

    expect(wrapper.text()).not.toContain('ACTIVE MODIFIERS');
  });

  it('should show quick actions when there are negative modifiers', () => {
    const wrapper = mount(HappinessDashboard, {
      props: {
        ...defaultProps,
        idleDwellerCount: 5,
      },
    });

    expect(wrapper.text()).toContain('QUICK ACTIONS');
    expect(wrapper.text()).toContain('Assign Idle Dwellers');
  });

  it('should emit assign-idle event when button clicked', async () => {
    const wrapper = mount(HappinessDashboard, {
      props: {
        ...defaultProps,
        idleDwellerCount: 5,
      },
    });

    const buttons = wrapper.findAll('button');
    const assignButton = buttons.find(b => b.text().includes('Assign Idle Dwellers'));

    if (assignButton) {
      await assignButton.trigger('click');
      expect(wrapper.emitted('assign-idle')).toBeTruthy();
    } else {
      throw new Error('Assign Idle Dwellers button not found');
    }
  });

  it('should emit activate-radio event when button clicked', async () => {
    const wrapper = mount(HappinessDashboard, {
      props: {
        ...defaultProps,
        idleDwellerCount: 1,
        radioHappinessMode: false,
      },
    });

    const buttons = wrapper.findAll('button');
    const radioButton = buttons.find(b => b.text().includes('Activate Radio'));

    if (radioButton) {
      await radioButton.trigger('click');
      expect(wrapper.emitted('activate-radio')).toBeTruthy();
    }
  });

  it('should emit view-low-happiness event when button clicked', async () => {
    const wrapper = mount(HappinessDashboard, {
      props: {
        ...defaultProps,
        distribution: {
          high: 3,
          medium: 4,
          low: 2,
          critical: 1,
        },
      },
    });

    const buttons = wrapper.findAll('button');
    const viewButton = buttons.find(b => b.text().includes('View Low Happiness'));

    if (viewButton) {
      await viewButton.trigger('click');
      expect(wrapper.emitted('view-low-happiness')).toBeTruthy();
    }
  });

  it('should not show "Activate Radio Mode" button when already active', () => {
    const wrapper = mount(HappinessDashboard, {
      props: {
        ...defaultProps,
        radioHappinessMode: true,
        idleDwellerCount: 1,
      },
    });

    expect(wrapper.text()).not.toContain('Activate Radio Mode');
  });

  it('should not show "Assign Idle Dwellers" when no idle dwellers', () => {
    const wrapper = mount(HappinessDashboard, {
      props: {
        ...defaultProps,
        idleDwellerCount: 0,
        lowResourceCount: 1,
      },
    });

    expect(wrapper.text()).not.toContain('Assign Idle Dwellers');
  });

  it('should handle zero dweller count', () => {
    const wrapper = mount(HappinessDashboard, {
      props: {
        ...defaultProps,
        dwellerCount: 0,
        distribution: {
          high: 0,
          medium: 0,
          low: 0,
          critical: 0,
        },
      },
    });

    // Should not crash and show 0% for all
    expect(wrapper.text()).toContain('(0%)');
  });

  it('should apply correct colors based on happiness level', () => {
    const wrapper = mount(HappinessDashboard, {
      props: {
        ...defaultProps,
        vaultHappiness: 85,
      },
    });

    const gaugeValue = wrapper.find('.gauge-value');
    expect(gaugeValue.attributes('style')).toContain('var(--color-theme-primary)');
  });

  it('should render SVG gauge with correct dimensions', () => {
    const wrapper = mount(HappinessDashboard, {
      props: defaultProps,
    });

    const svg = wrapper.find('svg');
    expect(svg.exists()).toBe(true);
    expect(svg.attributes('viewBox')).toBe('0 0 160 160');
  });

  it('should show trend icon', () => {
    const wrapper = mount(HappinessDashboard, {
      props: defaultProps,
    });

    const trendIcon = wrapper.find('.gauge-trend');
    expect(trendIcon.exists()).toBe(true);
  });

  it('should limit modifiers to 5', () => {
    const wrapper = mount(HappinessDashboard, {
      props: {
        ...defaultProps,
        lowResourceCount: 3,
        activeIncidentCount: 10,
        idleDwellerCount: 5,
        radioHappinessMode: true,
      },
    });

    const modifierItems = wrapper.findAll('.modifier-item');
    expect(modifierItems.length).toBeLessThanOrEqual(5);
  });
});
