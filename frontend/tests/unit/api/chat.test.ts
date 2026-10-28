import { describe, it, expect, vi, beforeEach } from 'vite-plus/test'
import axios from '@/core/plugins/axios'
import { chatApi } from '@/modules/chat/api/chat'

vi.mock('@/core/plugins/axios', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

describe('chatApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads history through the module boundary', async () => {
    const history = [{ id: 'msg-1', message_text: 'hello' }]
    ;(axios.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: history })

    await expect(chatApi.getHistory('dweller-1')).resolves.toEqual(history)
    expect(axios.get).toHaveBeenCalledWith('/api/v1/chat/history/dweller-1')
  })

  it('passes pagination params only when supplied', async () => {
    ;(axios.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })

    await chatApi.getHistory('dweller-1', { offset: 20, limit: 10 })

    expect(axios.get).toHaveBeenCalledWith('/api/v1/chat/history/dweller-1', {
      params: { offset: 20, limit: 10 },
    })
  })

  it('sends a text message with the debug flag', async () => {
    const response = { response: 'hi', dweller_message_id: 'msg-2' }
    ;(axios.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: response })

    await expect(chatApi.sendMessage('dweller-1', 'hello', { debug: true })).resolves.toEqual(
      response
    )
    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/chat/dweller-1',
      { message: 'hello' },
      { params: { debug: true } }
    )
  })

  it('uploads voice audio as multipart without hand-setting the content type', async () => {
    const response = { transcription: 'hello', dweller_message_id: 'msg-3' }
    ;(axios.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: response })
    const audio = new Blob(['audio'], { type: 'audio/webm' })

    await expect(chatApi.sendVoiceMessage('dweller-1', audio)).resolves.toEqual(response)

    const [url, body, config] = (axios.post as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/api/v1/chat/dweller-1/voice')
    expect(body).toBeInstanceOf(FormData)
    expect((body as FormData).get('audio_file')).toBeInstanceOf(File)
    expect(config).toEqual({ params: { return_audio: false } })
    expect(config).not.toHaveProperty('headers')
  })
})
