import { describe, expect, it, vi, beforeEach } from 'vite-plus/test'
import { createAxiosMock } from '../../helpers/mocks'
import { ref } from 'vue'
import { setActivePinia, createPinia } from 'pinia'

const post = vi.hoisted(() => vi.fn())
vi.mock('@/core/plugins/axios', () => createAxiosMock({ post }))
vi.mock('@/core/utils/errorHandler', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/core/utils/errorHandler')>()),
  handleStoreError: () => 'error',
}))

import { useChatMessages } from '@/modules/chat/composables/useChatMessages'

describe('useChatMessages avatar URL', () => {
  it.each([
    [
      'backend static',
      '/static/legendary_dweller_images/FOS_Dw_Butch.png',
      'http://localhost:8000/static/legendary_dweller_images/FOS_Dw_Butch.png',
    ],
    [
      'absolute',
      'https://s3-api.example.com/dweller-images/photo.png',
      'https://s3-api.example.com/dweller-images/photo.png',
    ],
  ])('resolves %s avatar URLs', (_kind, dwellerAvatar, expected) => {
    const { dwellerAvatarUrl } = useChatMessages({
      dwellerId: 'dweller-1',
      dwellerAvatar,
      token: null,
    })

    expect(dwellerAvatarUrl.value).toBe(expected)
  })
})

describe('useChatMessages debug payload', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    post.mockReset()
    post.mockResolvedValue({
      data: {
        response: 'hi',
        dweller_message_id: 'm1',
        debug: { model: 'gpt-5.4-mini', total_tokens: 42 },
      },
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

  it('passes the debug flag to the WebSocket send path', async () => {
    const sendMessage = vi.fn()
    const handlers: Record<string, (msg: unknown) => void> = {}
    const chatWs = {
      state: ref('connected'),
      sendMessage,
      on: (event: string, cb: (msg: unknown) => void) => {
        handlers[event] = cb
      },
    }

    const {
      userMessage,
      sendMessage: send,
      lastChatDebug,
    } = useChatMessages({
      dwellerId: 'dweller-1',
      token: 'tok',
      debugEnabled: ref(true),
      chatWs: chatWs as never,
    })
    userMessage.value = 'hello'
    void send()
    await Promise.resolve()

    expect(sendMessage).toHaveBeenCalledWith('hello', true)

    handlers.done?.({
      response_text: 'hi',
      dweller_message_id: 'm1',
      debug: { model: 'gpt-5.4-mini', total_tokens: 7 },
    })
    expect(lastChatDebug.value?.total_tokens).toBe(7)
  })
})
