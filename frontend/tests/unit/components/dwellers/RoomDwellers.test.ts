import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import RoomDwellers from '@/modules/dwellers/components/RoomDwellers.vue'
import { TooltipProvider } from '@/core/components/ui/tooltip'

vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    props: ['icon'],
    template: '<span :data-icon="icon" />',
  },
}))

const roster = vi.hoisted(() => ({
  dwellers: [] as Array<Record<string, unknown>>,
}))

vi.mock('@/modules/dwellers/stores/dweller', () => ({
  useDwellerStore: () => ({
    filter: { dwellers: roster.dwellers },
  }),
}))

enableAutoUnmount(afterEach)

const alice = {
  id: 'd1',
  room_id: 'r1',
  first_name: 'Alice',
  last_name: 'Smith',
  level: 3,
  apprentice_stat: null,
  thumbnail_url: null,
}

const mountDwellers = () =>
  mount(
    defineComponent({
      components: { RoomDwellers, TooltipProvider },
      template:
        '<TooltipProvider :delay-duration="0"><RoomDwellers room-id="r1" /></TooltipProvider>',
    }),
    { attachTo: document.body }
  )

beforeEach(() => {
  roster.dwellers.splice(0, roster.dwellers.length, alice)
})

it('shows dweller details in an app tooltip on keyboard focus without a browser title', async () => {
  const wrapper = mountDwellers()
  const avatar = wrapper.get('.dweller-avatar')
  expect(avatar.attributes('title')).toBeUndefined()
  await avatar.trigger('focus')
  await vi.waitFor(() =>
    expect(document.querySelector('[role="tooltip"]')?.textContent).toContain('Alice Smith (Lv3)')
  )
  expect(avatar.attributes('draggable')).toBe('true')
})

it('orders workers before apprentices and marks the apprentice avatar', () => {
  roster.dwellers.splice(
    0,
    roster.dwellers.length,
    {
      ...alice,
      id: 'a1',
      first_name: 'Ash',
      last_name: 'Apprentice',
      level: 2,
      apprentice_stat: 'strength',
    },
    alice
  )

  const wrapper = mountDwellers()
  const avatars = wrapper.findAll('.dweller-avatar')

  expect(avatars[0].attributes('aria-label')).toContain('Alice Smith (Lv3)')
  expect(avatars[1].attributes('aria-label')).toContain(
    'Ash Apprentice (Lv2), apprentice in Strength'
  )
  expect(avatars[0].attributes('class')).not.toContain('dweller-avatar--apprentice')
  expect(avatars[1].attributes('class')).toContain('dweller-avatar--apprentice')
  expect(avatars[0].find('.apprentice-badge').exists()).toBe(false)
  expect(avatars[1].find('.apprentice-badge').exists()).toBe(true)
})
