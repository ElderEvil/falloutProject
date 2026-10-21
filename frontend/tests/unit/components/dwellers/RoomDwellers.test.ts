import { afterEach, expect, it, vi } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import RoomDwellers from '@/modules/dwellers/components/RoomDwellers.vue'
import { TooltipProvider } from '@/core/components/ui/tooltip'

vi.mock('@/modules/dwellers/stores/dweller', () => ({
  useDwellerStore: () => ({
    filter: {
      dwellers: [{ id: 'd1', room_id: 'r1', first_name: 'Alice', last_name: 'Smith', level: 3 }],
    },
  }),
}))
enableAutoUnmount(afterEach)

it('shows dweller details in an app tooltip on keyboard focus without a browser title', async () => {
  const wrapper = mount(
    defineComponent({
      components: { RoomDwellers, TooltipProvider },
      template:
        '<TooltipProvider :delay-duration="0"><RoomDwellers room-id="r1" /></TooltipProvider>',
    }),
    { attachTo: document.body }
  )
  const avatar = wrapper.get('.dweller-avatar')
  expect(avatar.attributes('title')).toBeUndefined()
  await avatar.trigger('focus')
  await vi.waitFor(() =>
    expect(document.querySelector('[role="tooltip"]')?.textContent).toContain('Alice Smith (Lv3)')
  )
  expect(avatar.attributes('draggable')).toBe('true')
})
