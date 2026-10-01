import { describe, expect, it, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import { setActivePinia, createPinia } from 'pinia'

const post = vi.fn()
vi.mock('@/core/plugins/axios', () => ({
  default: { post: (...args: unknown[]) => post(...args), get: vi.fn() },
}))
vi.mock('@/core/utils/errorHandler', () => ({ handleStoreError: () => 'error' }))

import { useChatMessages } from '@/modules/chat/composables/useChatMessages'

describe('useChatMessages avatar URL', () => {
  it('uses the API origin for backend static avatars', () => {
    const { dwellerAvatarUrl } = useChatMessages({
      dwellerId: 'dweller-1',
      dwellerAvatar: '/static/legendary_dweller_images/FOS_Dw_Butch.png',
      token: null,
    })

    expect(dwellerAvatarUrl.value).toBe(
      'http://localhost:8000/static/legendary_dweller_images/FOS_Dw_Butch.png'
    )
  })

  it('passes absolute avatar URLs through unchanged', () => {
    const { dwellerAvatarUrl } = useChatMessages({
      dwellerId: 'dweller-1',
      dwellerAvatar: 'https://s3-api.example.com/dweller-images/photo.png',
      token: null,
    })

    expect(dwellerAvatarUrl.value).toBe('https://s3-api.example.com/dweller-images/photo.png')
  })
})

describe('useChatMessages debug payload', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    post.mockReset()
    post.mockResolvedValue({
      data: { response: 'hi', dweller_message_id: 'm1', debug: { model: 'gpt-5.4-mini', total_tokens: 42 } },
    })
  })

  it('requests and captures the debug payload when enabled', async () => {
    const { userMessage, sendMessage, lastChatDebug } = useChatMessages({
      dwellerId: 'dweller-1',
      token: 'tok',
      debugEnabled: ref(true),
    })
    userMessage.value = 'hello'
    await sendMessage()

    expect(post.mock.calls[0][2].params).toEqual({ debug: true })
    expect(lastChatDebug.value?.total_tokens).toBe(42)
  })

  it('omits debug when disabled', async () => {
    post.mockResolvedValue({ data: { response: 'hi', dweller_message_id: 'm1', debug: null } })
    const { userMessage, sendMessage, lastChatDebug } = useChatMessages({
      dwellerId: 'dweller-1',
      token: 'tok',
      debugEnabled: ref(false),
    })
    userMessage.value = 'hello'
    await sendMessage()

    expect(post.mock.calls[0][2].params).toEqual({ debug: undefined })
    expect(lastChatDebug.value).toBeNull()
  })
})
