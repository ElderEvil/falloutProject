import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { mount, flushPromises } from '@vue/test-utils'
import { createToastMock, createIconifyMock } from '../../helpers/mocks'

// Capture mock references so we can control them in tests
const mockApiGet = vi.fn()
const mockApiPost = vi.fn()

vi.mock('@/core/utils/api', () => ({
  apiGet: (...args: unknown[]) => mockApiGet(...args),
  apiPost: (...args: unknown[]) => mockApiPost(...args),
  apiPut: vi.fn(),
  apiRequest: vi.fn(),
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    request: vi.fn(),
  },
}))

vi.mock('@iconify/vue', () => createIconifyMock({ template: '<span class="icon-mock"></span>' }))
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => createToastMock(),
}))

// Constructable Audio stub: vi.fn().mockImplementation is not callable with `new`,
// but the widget does `new Audio(url)`. The stub exposes the mock's fns on the instance.
function stubAudio(mock: { play: ReturnType<typeof vi.fn>; pause: ReturnType<typeof vi.fn> }) {
  class AudioStub {
    onended: unknown = null
    onerror: unknown = null
    play = mock.play
    pause = mock.pause
    constructor(public src: string) {}
  }
  vi.stubGlobal('Audio', AudioStub)
}

const now = new Date()
const todayISO = now.toISOString()
const yesterday = new Date(now)
yesterday.setDate(yesterday.getDate() - 1)
const yesterdayISO = yesterday.toISOString()

function makeBroadcast(overrides: Partial<Record<keyof Parameters<typeof makeBroadcast>[0], unknown>> = {}) {
  return {
    id: 'broadcast-1',
    title: "Vault 111 Evening News",
    script: "Good evening, Vault dwellers. Population stands at 23.\nAll systems nominal.",
    audio_url: 'https://s3.evillab.dev/narration/vault-1/2024-01-01.mp3',
    trigger: 'daily' as const,
    created_at: todayISO,
    ...overrides,
  }
}

function makeEmptyBroadcast() {
  return {
    id: null,
    title: '',
    script: 'No broadcast available today.',
    audio_url: null,
    trigger: 'daily' as const,
    created_at: todayISO,
  }
}

describe('RadioNewsWidget', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Reset audio mock
    vi.stubGlobal('Audio', vi.fn().mockImplementation(() => ({
      onended: null,
      onerror: null,
      play: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn(),
    })))
    // Reset localStorage mock
    localStorage.clear()
  })

  it('shows a loading skeleton on initial mount', async () => {
    const { default: RadioNewsWidget } = await import('@/modules/radio-news/components/RadioNewsWidget.vue')

    mockApiGet.mockResolvedValue(undefined as never)

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })

    expect(wrapper.find('.radio-news-widget__loading').exists()).toBe(true)
  })

  it('renders a badge when a broadcast loads', async () => {
    const { default: RadioNewsWidget } = await import('@/modules/radio-news/components/RadioNewsWidget.vue')

    mockApiGet.mockResolvedValue(makeBroadcast())

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })

    await flushPromises()

    const badge = wrapper.find('.radio-news-widget__badge')
    expect(badge.exists()).toBe(true)
    expect(badge.text()).toContain('New Broadcast')
  })

  it('does not show the "New" label for a yesterday broadcast', async () => {
    const { default: RadioNewsWidget } = await import('@/modules/radio-news/components/RadioNewsWidget.vue')

    const broadcast = makeBroadcast({ created_at: yesterdayISO })
    mockApiGet.mockResolvedValue(broadcast)

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })

    await flushPromises()

    const badge = wrapper.find('.radio-news-widget__badge')
    expect(badge.exists()).toBe(true)
    expect(badge.text()).toContain('Radio')
    expect(badge.text()).not.toContain('New')
  })

  it('emits newBroadcast on successful fetch', async () => {
    const { default: RadioNewsWidget } = await import('@/modules/radio-news/components/RadioNewsWidget.vue')

    const broadcast = makeBroadcast()
    mockApiGet.mockResolvedValue(broadcast)

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })

    await flushPromises()

    expect(wrapper.emitted('newBroadcast')).toBeTruthy()
    expect(wrapper.emitted('newBroadcast')![0]).toEqual([broadcast])
  })

  it('shows a play button when audio_url is present', async () => {
    const { default: RadioNewsWidget } = await import('@/modules/radio-news/components/RadioNewsWidget.vue')

    mockApiGet.mockResolvedValue(makeBroadcast())

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })

    await flushPromises()

    const playBtn = wrapper.find('.radio-news-widget__play-btn')
    expect(playBtn.exists()).toBe(true)
    expect(playBtn.text()).toContain('Play')
  })

  it('stops audio when the play button is toggled', async () => {
    const audioMock = {
      onended: null,
      onerror: null,
      play: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn(),
    }
    stubAudio(audioMock)

    const { default: RadioNewsWidget } = await import('@/modules/radio-news/components/RadioNewsWidget.vue')

    mockApiGet.mockResolvedValue(makeBroadcast())

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })

    await flushPromises()

    // Click play
    await wrapper.find('.radio-news-widget__play-btn').trigger('click')
    expect(audioMock.play).toHaveBeenCalled()

    // Click stop
    await wrapper.find('.radio-news-widget__play-btn').trigger('click')
    expect(audioMock.pause).toHaveBeenCalled()
  })

  it('shows a text-only panel when audio_url is null but script exists', async () => {
    const { default: RadioNewsWidget } = await import('@/modules/radio-news/components/RadioNewsWidget.vue')

    mockApiGet.mockResolvedValue(makeEmptyBroadcast())

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })

    await flushPromises()

    expect(wrapper.find('.radio-news-widget__text-panel').exists()).toBe(true)
    expect(wrapper.find('.radio-news-widget__text-panel').text()).toContain('No broadcast available today')
    // No play button
    expect(wrapper.find('.radio-news-widget__play-btn').exists()).toBe(false)
  })

  it('does not show a play button when audio_url is null', async () => {
    const { default: RadioNewsWidget } = await import('@/modules/radio-news/components/RadioNewsWidget.vue')

    mockApiGet.mockResolvedValue(makeEmptyBroadcast())

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })

    await flushPromises()

    expect(wrapper.find('.radio-news-widget__play-btn').exists()).toBe(false)
  })

  it('shows the caption overlay while playing', async () => {
    const audioMock = {
      onended: null,
      onerror: null,
      play: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn(),
    }
    stubAudio(audioMock)

    const { default: RadioNewsWidget } = await import('@/modules/radio-news/components/RadioNewsWidget.vue')

    mockApiGet.mockResolvedValue(makeBroadcast())

    // Mark today's broadcast as played so the login auto-play doesn't fire —
    // this test exercises the manual play button.
    localStorage.setItem('radio_news_played', JSON.stringify({ 'broadcast-1': Date.now() }))

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })

    await flushPromises()

    // Before playing, no caption
    expect(wrapper.find('.radio-news-widget__caption').exists()).toBe(false)

    // Click play
    await wrapper.find('.radio-news-widget__play-btn').trigger('click')
    await flushPromises()

    expect(wrapper.find('.radio-news-widget__caption').exists()).toBe(true)
    expect(wrapper.find('.radio-news-widget__caption').text()).toContain('Vault 111 Evening News')
  })

  it('shows error state when fetch fails and no broadcast exists', async () => {
    const { default: RadioNewsWidget } = await import('@/modules/radio-news/components/RadioNewsWidget.vue')

    mockApiGet.mockRejectedValue(new Error('network'))

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })

    await flushPromises()

    const errorEl = wrapper.find('.radio-news-widget__error')
    expect(errorEl.exists()).toBe(true)
    expect(errorEl.text()).toContain('network')
  })

  // Welcome panel tests
  it('attempts autoplay on mount for today\'s unplayed broadcast', async () => {
    const audioMock = {
      onended: null,
      onerror: null,
      play: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn(),
    }
    stubAudio(audioMock)

    const { default: RadioNewsWidget } = await import('@/modules/radio-news/components/RadioNewsWidget.vue')

    const broadcast = makeBroadcast({ id: 'broadcast-1' })
    mockApiGet.mockResolvedValue(broadcast)

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })

    await flushPromises()

    expect(audioMock.play).toHaveBeenCalled()
    expect(wrapper.find('.radio-news-widget__welcome-panel').exists()).toBe(false)
  })

  it('shows welcome panel with tap-to-listen when autoplay is blocked', async () => {
    const { default: RadioNewsWidget } = await import('@/modules/radio-news/components/RadioNewsWidget.vue')

    const broadcast = makeBroadcast({ id: 'broadcast-1' })
    mockApiGet.mockResolvedValue(broadcast)

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })

    await flushPromises()

    // Simulate autoplay blocking by directly setting the state
    const vm = wrapper.vm as any
    vm.showWelcomePanel = true
    vm.welcomeBlocked = true
    await flushPromises()

    const panel = wrapper.find('.radio-news-widget__welcome-panel')
    expect(panel.exists()).toBe(true)
    expect(panel.text()).toContain('Vault Radio Hour')
    expect(panel.text()).toContain('Tap to listen')
    expect(panel.text()).toContain('Good evening')
  })

  it('marks broadcast as played after successful welcome panel playback', async () => {
    const { default: RadioNewsWidget } = await import('@/modules/radio-news/components/RadioNewsWidget.vue')

    const audioMock = {
      onended: null,
      onerror: null,
      play: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn(),
    }
    stubAudio(audioMock)

    const broadcast = makeBroadcast({ id: 'broadcast-1' })
    mockApiGet.mockResolvedValue(broadcast)

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })

    await flushPromises()

    // Simulate autoplay blocked
    const vm = wrapper.vm as any
    vm.showWelcomePanel = true
    vm.welcomeBlocked = true
    await flushPromises()

    // Click "Tap to listen"
    await wrapper.find('.radio-news-widget__welcome-panel').find('button').trigger('click')
    await flushPromises()

    expect(audioMock.play).toHaveBeenCalled()
    expect(wrapper.find('.radio-news-widget__welcome-panel').exists()).toBe(false)

    // Check localStorage
    const played = JSON.parse(localStorage.getItem('radio_news_played') || '{}')
    expect(played['broadcast-1']).toBeTruthy()
  })

  it('does not show welcome panel for yesterday broadcast', async () => {
    const audioMock = {
      onended: null,
      onerror: null,
      play: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn(),
    }
    stubAudio(audioMock)

    const { default: RadioNewsWidget } = await import('@/modules/radio-news/components/RadioNewsWidget.vue')

    const broadcast = makeBroadcast({ created_at: yesterdayISO, id: 'broadcast-yest' })
    mockApiGet.mockResolvedValue(broadcast)

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })

    await flushPromises()

    expect(wrapper.find('.radio-news-widget__welcome-panel').exists()).toBe(false)
    // Should show badge normally
    expect(wrapper.find('.radio-news-widget__badge').exists()).toBe(true)
  })

  it('does not show welcome panel when broadcast is already played', async () => {
    const audioMock = {
      onended: null,
      onerror: null,
      play: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn(),
    }
    stubAudio(audioMock)

    const { default: RadioNewsWidget } = await import('@/modules/radio-news/components/RadioNewsWidget.vue')

    // Mark broadcast as played before mounting
    localStorage.setItem('radio_news_played', JSON.stringify({ 'broadcast-1': Date.now() }))

    const broadcast = makeBroadcast({ id: 'broadcast-1' })
    mockApiGet.mockResolvedValue(broadcast)

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })

    await flushPromises()

    expect(wrapper.find('.radio-news-widget__welcome-panel').exists()).toBe(false)
    expect(wrapper.find('.radio-news-widget__badge').exists()).toBe(true)
  })

  it('does not show welcome panel when audio_url is null', async () => {
    const { default: RadioNewsWidget } = await import('@/modules/radio-news/components/RadioNewsWidget.vue')

    const broadcast = makeEmptyBroadcast()
    mockApiGet.mockResolvedValue(broadcast)

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })

    await flushPromises()

    expect(wrapper.find('.radio-news-widget__welcome-panel').exists()).toBe(false)
    expect(wrapper.find('.radio-news-widget__text-panel').exists()).toBe(true)
  })

  it('does not show welcome panel when broadcast id is null', async () => {
    const { default: RadioNewsWidget } = await import('@/modules/radio-news/components/RadioNewsWidget.vue')

    // Broadcast with id: null and audio_url: null
    const broadcast = {
      id: null,
      title: '',
      script: 'No broadcast available today.',
      audio_url: null,
      trigger: 'daily' as const,
      created_at: todayISO,
    }
    mockApiGet.mockResolvedValue(broadcast)

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })

    await flushPromises()

    expect(wrapper.find('.radio-news-widget__welcome-panel').exists()).toBe(false)
  })
})
