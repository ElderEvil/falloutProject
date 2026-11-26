import { describe, expect, it } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import RewardCard from '@/core/components/common/RewardCard.vue'

const mountCard = (props: Record<string, unknown> = {}) =>
  mount(RewardCard, {
    props: { icon: 'mdi:star', label: 'Experience Gained', value: '+150 XP', ...props },
  })

describe('RewardCard', () => {
  it('renders icon, label, and value', () => {
    const wrapper = mountCard()

    expect(wrapper.get('.reward-label').text()).toBe('Experience Gained')
    expect(wrapper.get('.reward-value').text()).toBe('+150 XP')
    expect(wrapper.find('.reward-icon-container').exists()).toBe(true)
  })

  it('applies the variant class to the icon container and value', () => {
    const wrapper = mountCard({ variant: 'experience' })

    expect(wrapper.get('.reward-icon-container').classes()).toContain('experience')
    expect(wrapper.get('.reward-value').classes()).toContain('experience-value')
  })

  it.each([
    [true, true],
    [false, false],
  ])('spans the full grid width only when span is %s', (span, expected) => {
    expect(
      mountCard({ icon: 'mdi:currency-usd', label: 'Caps', value: '200', span })
        .get('.reward-card')
        .classes()
        .includes('span')
    ).toBe(expected)
  })
})
