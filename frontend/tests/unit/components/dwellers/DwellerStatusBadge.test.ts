import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DwellerStatusBadge from '@/modules/dwellers/components/stats/DwellerStatusBadge.vue'

describe('DwellerStatusBadge', () => {
  describe('Status Display', () => {
    it('should render all status labels correctly', () => {
      const statuses = [
        { status: 'idle', label: 'Idle' },
        { status: 'working', label: 'Working' },
        { status: 'exploring', label: 'Exploring' },
        { status: 'questing', label: 'Questing' },
        { status: 'training', label: 'Training' },
        { status: 'dead', label: 'Dead' },
      ]

      statuses.forEach(({ status, label }) => {
        const wrapper = mount(DwellerStatusBadge, {
          props: {
            status: status as any,
            showLabel: true,
          },
        })

        expect(wrapper.text()).toContain(label)
      })
    })

    it('should render status badge container', () => {
      const wrapper = mount(DwellerStatusBadge, {
        props: {
          status: 'working',
        },
      })

      const badge = wrapper.find('.status-badge')
      expect(badge.exists()).toBe(true)
    })
  })

  describe('Label Visibility', () => {
    it('should show label when showLabel is true', () => {
      const wrapper = mount(DwellerStatusBadge, {
        props: {
          status: 'working',
          showLabel: true,
        },
      })

      expect(wrapper.text()).toContain('Working')
    })

    it('should hide label when showLabel is false', () => {
      const wrapper = mount(DwellerStatusBadge, {
        props: {
          status: 'working',
          showLabel: false,
        },
      })

      expect(wrapper.text()).not.toContain('Working')
    })
  })

  describe('Size Variants', () => {
    it('should apply small size classes', () => {
      const wrapper = mount(DwellerStatusBadge, {
        props: {
          status: 'working',
          size: 'small',
        },
      })

      const badge = wrapper.find('.status-badge')
      expect(badge.classes()).toContain('h-5')
    })

    it('should apply medium size classes', () => {
      const wrapper = mount(DwellerStatusBadge, {
        props: {
          status: 'working',
          size: 'medium',
        },
      })

      const badge = wrapper.find('.status-badge')
      expect(badge.classes()).toContain('h-6')
    })

    it('should apply large size classes', () => {
      const wrapper = mount(DwellerStatusBadge, {
        props: {
          status: 'working',
          size: 'large',
        },
      })

      const badge = wrapper.find('.status-badge')
      expect(badge.classes()).toContain('h-7')
    })
  })

  describe('Default Props', () => {
    it('should use default props when not specified', () => {
      const wrapper = mount(DwellerStatusBadge, {
        props: {
          status: 'working',
        },
      })

      // Default showLabel is false
      expect(wrapper.text()).not.toContain('Working')

      // Default size is small - check for small size container classes
      const badge = wrapper.find('.status-badge')
      expect(badge.exists()).toBe(true)
      expect(badge.classes()).toContain('h-5')
    })
  })

  describe('A8 Hover Glow Fix', () => {
    it('should set --glow-color CSS custom property', () => {
      const wrapper = mount(DwellerStatusBadge, {
        props: {
          status: 'working',
        },
      })

      const badge = wrapper.find('.status-badge')
      const style = badge.attributes('style')
      expect(style).toContain('--glow-color')
      expect(style).toContain('rgb(34 197 94 / 0.3)')
    })

    it('should NOT use dynamic hover class prefix', () => {
      const wrapper = mount(DwellerStatusBadge, {
        props: {
          status: 'exploring',
        },
      })

      const badge = wrapper.find('.status-badge')
      const classes = badge.classes()
      // The fix removes dynamic class like `hover:shadow-blue-500/30`
      // Instead uses CSS custom property for hover glow
      const hasHoverClass = classes.some((c) => c.startsWith('hover:'))
      expect(hasHoverClass).toBe(false)
    })

    it('should apply different glow colors for different statuses', () => {
      const testCases = [
        { status: 'exploring', expected: 'rgb(59 130 246 / 0.3)' },
        { status: 'working', expected: 'rgb(34 197 94 / 0.3)' },
        { status: 'dead', expected: 'rgb(239 68 68 / 0.3)' },
        { status: 'idle', expected: 'rgb(234 179 8 / 0.3)' },
      ]

      testCases.forEach(({ status, expected }) => {
        const wrapper = mount(DwellerStatusBadge, {
          props: { status: status as any },
        })

        const badge = wrapper.find('.status-badge')
        const style = badge.attributes('style')
        expect(style).toContain(expected)
      })
    })
  })
})
