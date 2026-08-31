import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ChatMessageList from '@/modules/chat/components/ChatMessageList.vue'
import type { ChatMessageDisplay } from '@/modules/chat/models/chat'

// iconify's Icon ships with no component name, so VTU stubs can't match it — mock the module instead.
vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-stub" :data-icon="icon"></span>',
    props: ['icon'],
  },
}))

type ListProps = InstanceType<typeof ChatMessageList>['$props']

const mountList = (messages: ChatMessageDisplay[], overrides: Partial<ListProps> = {}) =>
  mount(ChatMessageList, {
    props: {
      messages,
      dwellerName: 'Amata',
      username: 'Overseer',
      dwellerAvatarUrl: null,
      userAvatarUrl: null,
      isTyping: false,
      currentlyPlayingUrl: null,
      latestActionSuggestionIndex: -1,
      isPerformingAction: false,
      getHappinessColor: () => '',
      getHappinessIcon: () => 'mdi:emoticon',
      ...overrides,
    },
  })

describe('ChatMessageList', () => {
  it('renders an actionable dweller message and emits its typed action', async () => {
    const wrapper = mountList(
      [
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
      { latestActionSuggestionIndex: 0 }
    )

    expect(wrapper.text()).toContain('Suggested Action')
    await wrapper.find('.action-confirm-btn').trigger('click')

    expect(wrapper.emitted('confirmAction')?.[0]?.[1]).toBe(0)
  })

  it('renders dweller avatars via DwellerPortrait with the app-standard fallback', () => {
    const dwellerMessage = [{ type: 'dweller', content: 'Hi' }] as ChatMessageDisplay[]

    // No avatar -> fallback icon (mdi:account, matching the rest of the app)
    const fallback = mountList(dwellerMessage)
    expect(fallback.find('span[role="img"]').attributes('aria-label')).toBe('Amata')
    expect(fallback.find('.icon-stub').attributes('data-icon')).toBe('mdi:account')

    // With avatar -> img with the dweller's name as alt
    const withAvatar = mountList(dwellerMessage, { dwellerAvatarUrl: '/media/thumbs/amata.png' })
    const img = withAvatar.find('img.avatar-image')
    expect(img.attributes('src')).toBe('/media/thumbs/amata.png')
    expect(img.attributes('alt')).toBe('Amata')
  })

  it('renders user avatars via DwellerPortrait with the profile fallback icon', () => {
    const userMessage = [{ type: 'user', content: 'Hi' }] as ChatMessageDisplay[]

    const fallback = mountList(userMessage)
    expect(fallback.find('span[role="img"]').attributes('aria-label')).toBe('Overseer')
    expect(fallback.find('.icon-stub').attributes('data-icon')).toBe('mdi:account-circle')

    const withAvatar = mountList(userMessage, { userAvatarUrl: '/media/avatars/overseer.png' })
    const img = withAvatar.find('img.avatar-image')
    expect(img.attributes('src')).toBe('/media/avatars/overseer.png')
    expect(img.attributes('alt')).toBe('Overseer')
  })

  it('links known dweller locations in chat text to their map markers', () => {
    const wrapper = mountList(
      [{ type: 'dweller', content: 'Megaton taught me to keep moving.' }],
      {
        vaultId: 'vault-123',
        placeLinks: [{ name: 'Megaton', locationId: 'place-megaton' }],
      }
    )

    const placeLink = wrapper.find('.chat-place-link')
    expect(placeLink.text()).toBe('Megaton')
    expect(placeLink.attributes('href')).toBe('/vault/vault-123/map?place=place-megaton')
  })
})
