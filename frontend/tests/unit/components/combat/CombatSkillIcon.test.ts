import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import CombatSkillIcon from '@/modules/combat/components/CombatSkillIcon.vue'
import type { CombatSkillIcon as SkillIconKey } from '@/modules/combat/models/playback'

const icons: SkillIconKey[] = [
  'unarmed',
  'melee-blunt',
  'melee-edged',
  'melee-pointed',
  'gun-pistol',
  'gun-rifle',
  'gun-shotgun',
  'energy-pistol',
  'energy-rifle',
  'heavy-automatic',
  'heavy-flamer',
  'heavy-explosive',
]

describe('CombatSkillIcon', () => {
  it.each(icons)('renders the %s glyph locally with a stable size and no motion', (icon) => {
    const wrapper = mount(CombatSkillIcon, { props: { icon } })
    expect(wrapper.attributes('data-skill-icon')).toBe(icon)
    expect(wrapper.attributes('viewBox')).toBe('0 0 24 24')
    expect(wrapper.attributes('aria-hidden')).toBe('true')
    expect(wrapper.get('path').attributes('d')).toBeTruthy()
    expect(wrapper.find('image, animate, animateTransform').exists()).toBe(false)
  })

  it('distinguishes all categories, including ballistic and energy weapons', () => {
    const paths = icons.map((icon) =>
      mount(CombatSkillIcon, { props: { icon } }).get('path').attributes('d')
    )
    expect(new Set(paths).size).toBe(12)
  })

  it('uses the unarmed fallback when metadata is missing', () => {
    const wrapper = mount(CombatSkillIcon)
    expect(wrapper.attributes('data-skill-icon')).toBe('unarmed')
  })
})
