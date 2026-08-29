import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import RewardCard from '@/core/components/common/RewardCard.vue'

describe('RewardCard', () => {
  it('renders icon, label, and value', () => {
    const wrapper = mount(RewardCard, {
      props: { icon: 'mdi:star', label: 'Experience Gained', value: '+150 XP' },
    })

    expect(wrapper.get('.reward-label').text()).toBe('Experience Gained')
    expect(wrapper.get('.reward-value').text()).toBe('+150 XP')
    expect(wrapper.find('.reward-icon-container').exists()).toBe(true)
  })

  it('applies the variant class to the icon container and value', () => {
    const wrapper = mount(RewardCard, {
      props: { icon: 'mdi:star', label: 'XP', value: '+50 XP', variant: 'experience' },
    })

    expect(wrapper.get('.reward-icon-container').classes()).toContain('experience')
    expect(wrapper.get('.reward-value').classes()).toContain('experience-value')
  })

  it('spans the full grid width when span is true', () => {
    const wrapper = mount(RewardCard, {
      props: { icon: 'mdi:currency-usd', label: 'Caps', value: '200', span: true },
    })

    expect(wrapper.get('.reward-card').classes()).toContain('span')
  })

  it('does not span when span is false', () => {
    const wrapper = mount(RewardCard, {
      props: { icon: 'mdi:currency-usd', label: 'Caps', value: '200', span: false },
    })

    expect(wrapper.get('.reward-card').classes()).not.toContain('span')
  })
})
