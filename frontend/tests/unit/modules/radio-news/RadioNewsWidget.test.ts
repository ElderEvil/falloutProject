import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { mount, flushPromises } from '@vue/test-utils'
import { createToastMock, createIconifyMock } from '../../helpers/mocks'
import { Slider } from '@/core/components/ui/slider'
import RadioNewsWidget from '@/modules/radio-news/components/RadioNewsWidget.vue'

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
  const instances: AudioStub[] = []
  class AudioStub {
    onended: unknown = null
    onerror: unknown = null
    play = mock.play
    pause = mock.pause
    currentTime = 0
    volume = 1
    constructor(public src: string) {
      instances.push(this)
    }
  }
  vi.stubGlobal('Audio', AudioStub)
  return instances
}

const now = new Date()
const todayISO = now.toISOString()
const yesterday = new Date(now)
yesterday.setDate(yesterday.getDate() - 1)
const yesterdayISO = yesterday.toISOString()

function makeBroadcast(
  overrides: Partial<Record<keyof Parameters<typeof makeBroadcast>[0], unknown>> = {}
) {
  return {
    id: 'broadcast-1',
    title: 'Vault 111 Evening News',
    script: 'Good evening, Vault dwellers. Population stands at 23.\nAll systems nominal.',
    audio_url: 'https://s3.evillab.dev/narration/vault-1/2024-01-01.mp3',
    trigger: 'daily' as const,
    created_at: todayISO,
    ...overrides,
  }
}

function makeEmptyBroadcast() {
  return {
    id: 'broadcast-empty',
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
    vi.stubGlobal(
      'Audio',
      vi.fn().mockImplementation(() => ({
        onended: null,
        onerror: null,
        play: vi.fn().mockResolvedValue(undefined),
        pause: vi.fn(),
      }))
    )
    // Reset localStorage mock
    localStorage.clear()
  })

  it('opens the receiver console from the HUD tuner', async () => {
    mockApiGet.mockResolvedValue(makeBroadcast())

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })
    await flushPromises()

    const panel = wrapper.find('#radio-news-panel')
    expect(panel.attributes('style')).toContain('display: none')

    await wrapper.find('.radio-news-widget__toggle').trigger('click')

    expect(wrapper.find('.radio-news-widget__toggle').attributes('aria-expanded')).toBe('true')
    expect(wrapper.find('#radio-news-panel').attributes('style') ?? '').not.toContain(
      'display: none'
    )
  })

  it('dismisses the receiver console on Escape', async () => {
    mockApiGet.mockResolvedValue(makeBroadcast())

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })
    await flushPromises()
    await wrapper.find('.radio-news-widget__toggle').trigger('click')

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()

    expect(wrapper.find('#radio-news-panel').attributes('style')).toContain('display: none')
    expect(wrapper.find('.radio-news-widget__toggle').attributes('aria-expanded')).toBe('false')
  })

  it('marks a transcript-only broadcast read when it arrives while the console is open', async () => {
    let resolveLoad!: (value: unknown) => void
    mockApiGet.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveLoad = resolve
        })
    )

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })
    await wrapper.find('.radio-news-widget__toggle').trigger('click')

    resolveLoad(makeEmptyBroadcast())
    await flushPromises()

    expect(localStorage.getItem('radio_news_played')).toContain('broadcast-empty')
    expect(wrapper.find('.radio-news-widget__badge').text()).toContain('Radio')
  })

  it('shows a loading skeleton on initial mount', async () => {
    mockApiGet.mockResolvedValue(undefined as never)

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })

    expect(wrapper.find('.radio-news-widget__loading').exists()).toBe(true)
  })

  it('renders a badge when a broadcast loads', async () => {
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
    mockApiGet.mockResolvedValue(makeBroadcast())

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })

    await flushPromises()

    const playBtn = wrapper.find('.radio-news-widget__play-btn')
    expect(playBtn.exists()).toBe(true)
    expect(playBtn.text()).toContain('Play')
  })

  it('pauses and resumes the same audio at the current position', async () => {
    const audioMock = {
      onended: null,
      onerror: null,
      play: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn(),
    }
    const instances = stubAudio(audioMock)

    mockApiGet.mockResolvedValue(makeBroadcast())

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })

    await flushPromises()

    // Click play
    await wrapper.find('.radio-news-widget__play-btn').trigger('click')
    expect(audioMock.play).toHaveBeenCalled()

    instances[0].currentTime = 18
    await wrapper.find('.radio-news-widget__play-btn').trigger('click')
    expect(audioMock.pause).toHaveBeenCalled()
    expect(wrapper.find('.radio-news-widget__play-btn').text()).toContain('Resume')
    await wrapper.find('.radio-news-widget__play-btn').trigger('click')
    await flushPromises()
    expect(instances).toHaveLength(1)
    expect(instances[0].currentTime).toBe(18)
    expect(audioMock.play).toHaveBeenCalledTimes(2)
    expect(wrapper.find('.radio-news-widget__play-btn').text()).toContain('Pause')
    wrapper.unmount()
  })

  it('replays from the beginning while playing or paused', async () => {
    const audioMock = { play: vi.fn().mockResolvedValue(undefined), pause: vi.fn() }
    const instances = stubAudio(audioMock)
    mockApiGet.mockResolvedValue(makeBroadcast())
    const wrapper = mount(RadioNewsWidget, { props: { vaultId: 'vault-1' } })
    await flushPromises()
    await wrapper.find('.radio-news-widget__play-btn').trigger('click')
    await flushPromises()
    instances[0].currentTime = 20
    await wrapper.find('[aria-label="Replay broadcast from the beginning"]').trigger('click')
    expect(instances[0].currentTime).toBe(0)
    expect(audioMock.play).toHaveBeenCalledTimes(1)

    await wrapper.find('.radio-news-widget__play-btn').trigger('click')
    instances[0].currentTime = 12
    await wrapper.find('[aria-label="Replay broadcast from the beginning"]').trigger('click')
    await flushPromises()
    expect(instances).toHaveLength(1)
    expect(instances[0].currentTime).toBe(0)
    expect(audioMock.play).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('applies volume before playback and while playing, with mute and restore', async () => {
    const instances = stubAudio({ play: vi.fn().mockResolvedValue(undefined), pause: vi.fn() })
    mockApiGet.mockResolvedValue(makeBroadcast())
    const wrapper = mount(RadioNewsWidget, { props: { vaultId: 'vault-1' } })
    await flushPromises()
    const slider = wrapper.findComponent(Slider)
    slider.vm.$emit('update:modelValue', [30])
    await flushPromises()
    await wrapper.find('.radio-news-widget__play-btn').trigger('click')
    expect(instances[0].volume).toBe(0.3)
    slider.vm.$emit('update:modelValue', [45])
    await flushPromises()
    expect(instances[0].volume).toBe(0.45)
    await wrapper.find('[aria-label="Mute broadcast"]').trigger('click')
    expect(instances[0].volume).toBe(0)
    await wrapper.find('[aria-label="Unmute broadcast"]').trigger('click')
    expect(instances[0].volume).toBe(0.45)
    wrapper.unmount()
  })

  it('remembers the broadcast volume when the widget remounts', async () => {
    const instances = stubAudio({ play: vi.fn().mockResolvedValue(undefined), pause: vi.fn() })
    mockApiGet.mockResolvedValue(makeBroadcast())
    const first = mount(RadioNewsWidget, { props: { vaultId: 'vault-1' } })
    await flushPromises()
    first.findComponent(Slider).vm.$emit('update:modelValue', [25])
    await flushPromises()
    first.unmount()
    const second = mount(RadioNewsWidget, { props: { vaultId: 'vault-1' } })
    await flushPromises()
    expect(second.findComponent(Slider).props('modelValue')).toEqual([25])
    await second.find('.radio-news-widget__play-btn').trigger('click')
    expect(instances[0].volume).toBe(0.25)
    second.unmount()
  })

  it('ignores a delayed play result after the vault changes', async () => {
    let resolvePlay!: () => void
    const audioMock = {
      play: vi.fn(
        () =>
          new Promise<void>((resolve) => {
            resolvePlay = resolve
          })
      ),
      pause: vi.fn(),
    }
    stubAudio(audioMock)
    mockApiGet
      .mockResolvedValueOnce(makeBroadcast())
      .mockResolvedValueOnce(makeBroadcast({ id: 'second' }))
    const wrapper = mount(RadioNewsWidget, { props: { vaultId: 'vault-1' } })
    await flushPromises()
    await wrapper.find('.radio-news-widget__play-btn').trigger('click')
    await wrapper.setProps({ vaultId: 'vault-2' })
    await flushPromises()
    resolvePlay()
    await flushPromises()
    expect(audioMock.pause).toHaveBeenCalled()
    expect(localStorage.getItem('radio_news_played') ?? '').not.toContain('broadcast-1')
    expect(wrapper.find('.radio-news-widget__play-btn').text()).toContain('Play')
    wrapper.unmount()
  })

  it('keeps resumed audio playing when the earlier play request is aborted', async () => {
    let rejectFirstPlay!: (error: Error) => void
    const audioMock = {
      play: vi
        .fn()
        .mockImplementationOnce(
          () =>
            new Promise<void>((_resolve, reject) => {
              rejectFirstPlay = reject
            })
        )
        .mockResolvedValue(undefined),
      pause: vi.fn(),
    }
    const instances = stubAudio(audioMock)
    mockApiGet.mockResolvedValue(makeBroadcast())
    const wrapper = mount(RadioNewsWidget, { props: { vaultId: 'vault-1' } })
    await flushPromises()
    await wrapper.find('.radio-news-widget__play-btn').trigger('click')
    await wrapper.find('.radio-news-widget__play-btn').trigger('click')
    await wrapper.find('.radio-news-widget__play-btn').trigger('click')
    await flushPromises()
    rejectFirstPlay(new DOMException('Playback interrupted by pause', 'AbortError'))
    await flushPromises()
    expect(instances).toHaveLength(1)
    expect(audioMock.pause).toHaveBeenCalledTimes(1)
    expect(wrapper.find('.radio-news-widget__play-btn').text()).toContain('Pause')
    wrapper.unmount()
  })

  it('shows a text-only panel when audio_url is null but script exists', async () => {
    mockApiGet.mockResolvedValue(makeEmptyBroadcast())

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })

    await flushPromises()

    expect(wrapper.find('.radio-news-widget__text-panel').exists()).toBe(true)
    expect(wrapper.find('.radio-news-widget__text-panel').text()).toContain(
      'No broadcast available today'
    )
    // No play button
    expect(wrapper.find('.radio-news-widget__play-btn').exists()).toBe(false)
  })

  it('does not show a play button when audio_url is null', async () => {
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
    mockApiGet.mockRejectedValue(new Error('network'))

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })

    await flushPromises()

    const errorEl = wrapper.find('.radio-news-widget__error')
    expect(errorEl.exists()).toBe(true)
    expect(errorEl.text()).toContain('network')
  })

  it('does not autoplay on mount', async () => {
    const audioMock = {
      onended: null,
      onerror: null,
      play: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn(),
    }
    stubAudio(audioMock)
    mockApiGet.mockResolvedValue(makeBroadcast({ id: 'broadcast-1' }))

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })
    await flushPromises()

    expect(audioMock.play).not.toHaveBeenCalled()
    expect(wrapper.find('.radio-news-widget__badge').exists()).toBe(true)
    expect(wrapper.find('.radio-news-widget__play-btn').exists()).toBe(true)
  })

  it('reloads when the vault changes and ignores the old response', async () => {
    let resolveFirst!: (value: unknown) => void
    mockApiGet
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFirst = resolve
          })
      )
      .mockResolvedValueOnce(makeBroadcast({ id: 'second', title: 'Second Vault' }))

    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1' },
    })
    await wrapper.setProps({ vaultId: 'vault-2' })
    await flushPromises()

    expect(wrapper.emitted('newBroadcast')?.at(-1)).toEqual([
      makeBroadcast({ id: 'second', title: 'Second Vault' }),
    ])
    resolveFirst(makeBroadcast({ id: 'first', title: 'First Vault' }))
    await flushPromises()
    expect(wrapper.emitted('newBroadcast')?.at(-1)).toEqual([
      makeBroadcast({ id: 'second', title: 'Second Vault' }),
    ])
  })
})

it('regenerates from the HUD control', async () => {
  const regenerated = makeBroadcast({ id: 'broadcast-2', title: 'Regenerated' })
  mockApiGet.mockResolvedValue(makeBroadcast({ id: 'broadcast-1' }))
  mockApiPost.mockResolvedValue(regenerated)

  const wrapper = mount(RadioNewsWidget, {
    props: { vaultId: 'vault-1' },
  })
  await flushPromises()
  await wrapper.find('.radio-news-widget__regenerate-btn').trigger('click')
  await flushPromises()

  expect(mockApiPost.mock.calls[0][0]).toContain('/radio-news/regenerate')
  expect(wrapper.emitted('newBroadcast')?.at(-1)).toEqual([regenerated])
})

it('ignores a stale response when returning to the same vault', async () => {
  const resolvers: Array<(value: unknown) => void> = []
  mockApiGet.mockImplementation(
    () =>
      new Promise((resolve) => {
        resolvers.push(resolve)
      })
  )

  const wrapper = mount(RadioNewsWidget, {
    props: { vaultId: 'vault-1' },
  })
  await wrapper.setProps({ vaultId: 'vault-2' })
  await wrapper.setProps({ vaultId: 'vault-1' })

  resolvers[2](makeBroadcast({ id: 'latest-a', title: 'Latest A' }))
  await flushPromises()
  resolvers[0](makeBroadcast({ id: 'stale-a', title: 'Stale A' }))
  await flushPromises()

  expect(wrapper.emitted('newBroadcast')?.at(-1)).toEqual([
    makeBroadcast({ id: 'latest-a', title: 'Latest A' }),
  ])
})

it('re-enables regeneration after switching vaults mid-request', async () => {
  mockApiGet.mockResolvedValue(makeBroadcast())
  let resolveRegenerate!: (value: unknown) => void
  mockApiPost.mockImplementation(
    () =>
      new Promise((resolve) => {
        resolveRegenerate = resolve
      })
  )

  const wrapper = mount(RadioNewsWidget, {
    props: { vaultId: 'vault-1' },
  })
  await flushPromises()
  await wrapper.find('.radio-news-widget__regenerate-btn').trigger('click')
  await flushPromises()

  await wrapper.setProps({ vaultId: 'vault-2' })
  await flushPromises()
  expect(wrapper.find('.radio-news-widget__regenerate-btn').attributes('disabled')).toBeUndefined()

  resolveRegenerate(makeBroadcast({ id: 'stale-regeneration' }))
  await flushPromises()
  expect(wrapper.find('.radio-news-widget__regenerate-btn').attributes('disabled')).toBeUndefined()
})
