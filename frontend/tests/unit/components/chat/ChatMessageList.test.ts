import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ChatMessageList from '@/modules/chat/components/ChatMessageList.vue'

describe('ChatMessageList', () => {
  it('renders an actionable dweller message and emits its typed action', async () => {
    const wrapper = mount(ChatMessageList, {
      props: {
        messages: [
          {
            type: 'dweller',
            content: 'Let us train.',
            actionSuggestion: {
              action_type: 'start_training',
              stat: 'strength',
              reason: 'Strength is low',
            },
          },
        ],
        dwellerName: 'Amata',
        username: 'Overseer',
        dwellerAvatarUrl: null,
        isTyping: false,
        currentlyPlayingUrl: null,
        latestActionSuggestionIndex: 0,
        isPerformingAction: false,
        getHappinessColor: () => '',
        getHappinessIcon: () => 'mdi:emoticon',
      },
      global: {
        stubs: { Icon: true },
      },
    })

    expect(wrapper.text()).toContain('Suggested Action')
    await wrapper.find('.action-confirm-btn').trigger('click')

    expect(wrapper.emitted('confirmAction')?.[0]?.[1]).toBe(0)
  })
})
