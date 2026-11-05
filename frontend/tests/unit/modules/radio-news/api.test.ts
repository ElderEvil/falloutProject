import { describe, expect, it, vi, beforeEach } from 'vite-plus/test'
import axios from '@/core/plugins/axios'
import { fetchRadioNews, regenerateRadioNews } from '@/modules/radio-news/api/radioNews'

vi.mock('@/core/plugins/axios', () => ({
  default: { get: vi.fn(), put: vi.fn(), post: vi.fn() },
}))

describe('fetchRadioNews', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches today\'s broadcast for a vault', async () => {
    const broadcast = {
      id: 'b1',
      title: 'Evening News',
      script: 'All systems nominal.',
      audio_url: 'https://s3.example.com/clip.mp3',
      trigger: 'daily' as const,
      created_at: new Date().toISOString(),
    }

    ;(axios.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: broadcast,
    })

    const result = await fetchRadioNews('vault-42')

    // The API client calls apiGet(url, {}) which goes through apiRequest with
    // a config object. Verify the URL is correct.
    const callArgs = (axios.get as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(callArgs[0]).toBe('/api/v1/vaults/vault-42/radio-news')
    expect(result).toEqual(broadcast)
  })

  it('propagates failures', async () => {
    ;(axios.get as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('timeout'))

    await expect(fetchRadioNews('vault-1')).rejects.toThrow('timeout')
  })

  it('handles script-only (null audio) responses', async () => {
    const scriptOnly = {
      id: null,
      title: 'Technical Difficulties',
      script: 'We\'re working on restoring the broadcast feed…',
      audio_url: null,
      trigger: 'daily' as const,
      created_at: new Date().toISOString(),
    }

    ;(axios.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: scriptOnly })

    const result = await fetchRadioNews('vault-1')
    expect(result.audio_url).toBeNull()
    expect(result.id).toBeNull()
    expect(result.script).toBe(scriptOnly.script)
  })
})

describe('regenerateRadioNews', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('posts to the regenerate endpoint', async () => {
    const broadcast = {
      id: 'b2',
      title: 'Breaking News',
      script: 'Breaking news script.',
      audio_url: 'https://s3.example.com/breaking.mp3',
      trigger: 'manual' as const,
      created_at: new Date().toISOString(),
    }

    ;(axios.post as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: broadcast,
    })

    const result = await regenerateRadioNews('vault-1')

    const callArgs = (axios.post as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(callArgs[0]).toBe('/api/v1/vaults/vault-1/radio-news/regenerate')
    expect(result.trigger).toBe('manual')
  })

  it('propagates 429 rate-limit errors', async () => {
    const rateLimitError = new Error('Rate limit exceeded')
    ;(axios.post as ReturnType<typeof vi.fn>).mockRejectedValue(rateLimitError)

    await expect(regenerateRadioNews('vault-1')).rejects.toThrow('Rate limit exceeded')
  })
})
