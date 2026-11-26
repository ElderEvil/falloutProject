import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { mount, flushPromises } from '@vue/test-utils'
import { createToastMock, createIconifyMock } from '../../helpers/mocks'
import { Slider } from '@/core/components/ui/slider'
import RadioNewsWidget from '@/modules/radio-news/components/RadioNewsWidget.vue'

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
vi.mock('@/core/composables/useToast', () => ({ useToast: () => createToastMock() }))

// Constructable Audio stub: the widget does `new Audio(url)`, so a plain
// vi.fn() implementation is not enough — the mock's fns live on the instance.
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
  return { instances, mock }
}

const audioPair = () => ({ play: vi.fn().mockResolvedValue(undefined), pause: vi.fn() })

const now = new Date()
const todayISO = now.toISOString()
const yesterday = new Date(now)
yesterday.setDate(yesterday.getDate() - 1)
const yesterdayISO = yesterday.toISOString()

function makeBroadcast(overrides: Record<string, unknown> = {}) {
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

const emptyBroadcast = () => ({
  id: 'broadcast-empty',
  title: '',
  script: 'No broadcast available today.',
  audio_url: null,
  trigger: 'daily' as const,
  created_at: todayISO,
})

const invalidVolumes = [
  ['-20', 0],
  ['175', 100],
  ['NaN', 75],
  ['Infinity', 75],
  ['-Infinity', 75],
  ['invalid', 75],
] as const

const mountWidget = async (
  props: Record<string, unknown> = { vaultId: 'vault-1' },
  { broadcast = makeBroadcast() as unknown }: { broadcast?: unknown } = {}
) => {
  mockApiGet.mockResolvedValue(broadcast)
  const wrapper = mount(RadioNewsWidget, { props })
  await flushPromises()
  return wrapper
}

const openConsole = async (wrapper: Awaited<ReturnType<typeof mountWidget>>) => {
  await wrapper.get('.radio-news-widget__toggle').trigger('click')
  await flushPromises()
}

const playButton = (wrapper: Awaited<ReturnType<typeof mountWidget>>) =>
  wrapper.get('.radio-news-widget__play-btn')

const play = async (wrapper: Awaited<ReturnType<typeof mountWidget>>) => {
  await playButton(wrapper).trigger('click')
  await flushPromises()
}

describe('RadioNewsWidget', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    stubAudio(audioPair())
    localStorage.clear()
  })

  it('opens the receiver console from the HUD tuner', async () => {
    const wrapper = await mountWidget()
    expect(wrapper.get('#radio-news-panel').attributes('style')).toContain('display: none')

    await openConsole(wrapper)

    expect(wrapper.get('.radio-news-widget__toggle').attributes('aria-expanded')).toBe('true')
    expect(wrapper.get('#radio-news-panel').attributes('style') ?? '').not.toContain(
      'display: none'
    )
  })

  it('dismisses the receiver console on Escape', async () => {
    const wrapper = await mountWidget()
    await openConsole(wrapper)

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()

    expect(wrapper.get('#radio-news-panel').attributes('style')).toContain('display: none')
    expect(wrapper.get('.radio-news-widget__toggle').attributes('aria-expanded')).toBe('false')
  })

  it('renders an inline tuner and teleports the console to body', async () => {
    mockApiGet.mockResolvedValue(makeBroadcast())
    const wrapper = mount(RadioNewsWidget, {
      props: { vaultId: 'vault-1', inline: true },
      attachTo: document.body,
    })
    await flushPromises()

    // Inline trigger mounts with the console teleported out of the wrapper
    // (body-level, outside the control bar's transform/overflow clipping).
    expect(wrapper.find('#radio-news-panel').exists()).toBe(false)
    const panel = document.querySelector('#radio-news-panel') as HTMLElement | null
    expect(panel?.style.display).toContain('none')

    await wrapper.get('.radio-news-widget__toggle').trigger('click')
    expect(panel!.style.display).not.toContain('none')
    expect(wrapper.get('.radio-news-widget__toggle').attributes('aria-expanded')).toBe('true')
    wrapper.unmount()
  })

  it('marks a transcript-only broadcast read when it arrives while the console is open', async () => {
    mockApiGet.mockResolvedValueOnce(makeBroadcast()).mockResolvedValueOnce(emptyBroadcast())
    const wrapper = await mountWidget()
    await openConsole(wrapper)

    // The next broadcast lands while the console is already open.
    await wrapper.setProps({ vaultId: 'vault-2' })
    await flushPromises()

    expect(localStorage.getItem('radio_news_played')).toContain('broadcast-empty')
    expect(wrapper.get('.radio-news-widget__badge').text()).toContain('Radio')
  })

  it('stays out of the HUD while the first broadcast is loading', async () => {
    let resolveLoad!: (value: unknown) => void
    mockApiGet.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveLoad = resolve
        })
    )
    const wrapper = mount(RadioNewsWidget, { props: { vaultId: 'vault-1' } })

    // No empty tuner flash before data arrives: the widget is simply absent.
    expect(wrapper.find('.radio-news-widget__toggle').exists()).toBe(false)
    expect(wrapper.find('#radio-news-panel').exists()).toBe(false)

    resolveLoad(makeBroadcast())
    await flushPromises()
    expect(wrapper.find('.radio-news-widget__toggle').exists()).toBe(true)
  })

  it('renders the badge and emits the broadcast on load', async () => {
    const broadcast = makeBroadcast()
    const wrapper = await mountWidget({ vaultId: 'vault-1' }, { broadcast })

    expect(wrapper.get('.radio-news-widget__badge').text()).toContain('New Broadcast')
    expect(wrapper.emitted('newBroadcast')![0]).toEqual([broadcast])
  })

  it('renders a founding-day broadcast like any other broadcast', async () => {
    const foundingDay = makeBroadcast({ id: 'broadcast-founding-day', title: 'Vault 111 Signs On' })
    const wrapper = await mountWidget({ vaultId: 'vault-1' }, { broadcast: foundingDay })

    // There is no off-air special case any more: the payload is a normal broadcast.
    expect(wrapper.find('.radio-news-widget__off-air').exists()).toBe(false)
    expect(wrapper.get('.radio-news-widget__badge').text()).toContain('New Broadcast')
    await openConsole(wrapper)

    expect(wrapper.get('.radio-news-widget__title').text()).toBe('Vault 111 Signs On')
    expect(wrapper.get('.radio-news-widget__play-btn').text()).toContain('Play')
    expect(wrapper.get('.radio-news-widget__transcript').text()).toContain(
      'Population stands at 23.'
    )
    expect(wrapper.emitted('newBroadcast')?.[0]).toEqual([foundingDay])
  })

  it('derives the toggle name from its visible content', async () => {
    const wrapper = await mountWidget()
    const toggle = wrapper.get('button')

    // axe's label-content-name rule requires the whole visible text inside the
    // accessible name; the name must therefore come from the content itself.
    expect(toggle.attributes('aria-label')).toBeUndefined()
    expect(toggle.text()).toContain('Vault radio:')
    expect(toggle.text()).toContain('New Broadcast')
    expect(toggle.text()).toContain('Vault 111 Evening News')
  })

  it('does not show the "New" label for a yesterday broadcast', async () => {
    const wrapper = await mountWidget(
      { vaultId: 'vault-1' },
      { broadcast: makeBroadcast({ created_at: yesterdayISO }) }
    )

    const badge = wrapper.get('.radio-news-widget__badge')
    expect(badge.text()).toContain('Radio')
    expect(badge.text()).not.toContain('New')
  })

  it('shows the player chrome for a playable broadcast', async () => {
    const wrapper = await mountWidget()
    await openConsole(wrapper)

    expect(wrapper.find('[aria-label="Play broadcast"]').exists()).toBe(true)
    expect(wrapper.findComponent(Slider).exists()).toBe(true)
    expect(wrapper.find('[aria-label="Mute broadcast"]').exists()).toBe(true)
    expect(wrapper.find('[aria-label="Regenerate the broadcast"]').exists()).toBe(true)
    expect(wrapper.get('.radio-news-widget__play-btn').text()).toContain('Play')
  })

  it('pauses and resumes the same audio at the current position', async () => {
    const { instances, mock } = stubAudio(audioPair())
    const wrapper = await mountWidget()

    await playButton(wrapper).trigger('click')
    expect(mock.play).toHaveBeenCalled()

    instances[0].currentTime = 18
    await playButton(wrapper).trigger('click')
    expect(mock.pause).toHaveBeenCalled()
    expect(playButton(wrapper).text()).toContain('Resume')

    await play(wrapper)
    expect(instances).toHaveLength(1)
    expect(instances[0].currentTime).toBe(18)
    expect(mock.play).toHaveBeenCalledTimes(2)
    expect(playButton(wrapper).text()).toContain('Pause')
    wrapper.unmount()
  })

  it('replays from the beginning while playing or paused', async () => {
    const { instances, mock } = stubAudio(audioPair())
    const wrapper = await mountWidget()
    await play(wrapper)

    instances[0].currentTime = 20
    await wrapper.get('[aria-label="Replay broadcast from the beginning"]').trigger('click')
    expect(instances[0].currentTime).toBe(0)
    expect(mock.play).toHaveBeenCalledTimes(1)

    await playButton(wrapper).trigger('click')
    instances[0].currentTime = 12
    await wrapper.get('[aria-label="Replay broadcast from the beginning"]').trigger('click')
    await flushPromises()

    expect(instances).toHaveLength(1)
    expect(instances[0].currentTime).toBe(0)
    expect(mock.play).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('applies volume before playback and while playing, with mute and restore', async () => {
    const { instances } = stubAudio(audioPair())
    const wrapper = await mountWidget()
    const slider = wrapper.findComponent(Slider)

    slider.vm.$emit('update:modelValue', [30])
    await flushPromises()
    await playButton(wrapper).trigger('click')
    expect(instances[0].volume).toBe((30 / 100) ** 2)

    slider.vm.$emit('update:modelValue', [45])
    await flushPromises()
    expect(instances[0].volume).toBe((45 / 100) ** 2)

    await wrapper.get('[aria-label="Mute broadcast"]').trigger('click')
    expect(instances[0].volume).toBe(0)
    await wrapper.get('[aria-label="Unmute broadcast"]').trigger('click')
    expect(instances[0].volume).toBe((45 / 100) ** 2)
    wrapper.unmount()
  })

  it('remembers the broadcast volume when the widget remounts', async () => {
    const { instances } = stubAudio(audioPair())
    mockApiGet.mockResolvedValue(makeBroadcast())
    const first = mount(RadioNewsWidget, { props: { vaultId: 'vault-1' } })
    await flushPromises()
    first.findComponent(Slider).vm.$emit('update:modelValue', [25])
    await flushPromises()
    first.unmount()

    const second = mount(RadioNewsWidget, { props: { vaultId: 'vault-1' } })
    await flushPromises()
    expect(second.findComponent(Slider).props('modelValue')).toEqual([25])
    await second.get('.radio-news-widget__play-btn').trigger('click')
    expect(instances[0].volume).toBe((25 / 100) ** 2)
    second.unmount()
  })

  it.each(invalidVolumes)('normalizes saved volume %s before playback', async (saved, expected) => {
    localStorage.setItem('radio_news_volume', saved)
    const { instances, mock } = stubAudio(audioPair())
    const wrapper = await mountWidget()

    expect(wrapper.findComponent(Slider).props('modelValue')).toEqual([expected])
    await play(wrapper)
    expect(instances[0].volume).toBe((expected / 100) ** 2)
    expect(mock.play).toHaveBeenCalledOnce()

    if (expected > 0) {
      await wrapper.get('[aria-label="Mute broadcast"]').trigger('click')
      await wrapper.get('[aria-label="Unmute broadcast"]').trigger('click')
      expect(instances[0].volume).toBe((expected / 100) ** 2)
    }
    wrapper.unmount()
  })

  it.each(invalidVolumes)(
    'normalizes volume %s received through storage updates while playing',
    async (saved, expected) => {
      const { instances, mock } = stubAudio(audioPair())
      const wrapper = await mountWidget()
      await play(wrapper)

      // VueUse uses this event for the suite's custom storage backend.
      window.dispatchEvent(
        new CustomEvent('vueuse-storage', {
          detail: { key: 'radio_news_volume', newValue: saved, storageArea: localStorage },
        })
      )
      await flushPromises()

      expect(wrapper.findComponent(Slider).props('modelValue')).toEqual([expected])
      expect(instances[0].volume).toBe((expected / 100) ** 2)
      expect(playButton(wrapper).text()).toContain('Pause')
      expect(mock.pause).not.toHaveBeenCalled()
      wrapper.unmount()
    }
  )

  it('ignores a delayed play result after the vault changes', async () => {
    let resolvePlay!: () => void
    const { mock } = stubAudio({
      play: vi.fn(
        () =>
          new Promise<void>((resolve) => {
            resolvePlay = resolve
          })
      ),
      pause: vi.fn(),
    })
    mockApiGet
      .mockResolvedValueOnce(makeBroadcast())
      .mockResolvedValueOnce(makeBroadcast({ id: 'second' }))
    const wrapper = await mountWidget()
    await playButton(wrapper).trigger('click')

    await wrapper.setProps({ vaultId: 'vault-2' })
    await flushPromises()
    resolvePlay()
    await flushPromises()

    expect(mock.pause).toHaveBeenCalled()
    expect(localStorage.getItem('radio_news_played') ?? '').not.toContain('broadcast-1')
    expect(playButton(wrapper).text()).toContain('Play')
    wrapper.unmount()
  })

  it('keeps resumed audio playing when the earlier play request is aborted', async () => {
    let rejectFirstPlay!: (error: Error) => void
    const { instances, mock } = stubAudio({
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
    })
    const wrapper = await mountWidget()

    await playButton(wrapper).trigger('click')
    await playButton(wrapper).trigger('click')
    await playButton(wrapper).trigger('click')
    await flushPromises()
    rejectFirstPlay(new DOMException('Playback interrupted by pause', 'AbortError'))
    await flushPromises()

    expect(instances).toHaveLength(1)
    expect(mock.pause).toHaveBeenCalledTimes(1)
    expect(playButton(wrapper).text()).toContain('Pause')
    wrapper.unmount()
  })

  it('renders only the transcript card when a broadcast has no audio', async () => {
    const wrapper = await mountWidget({ vaultId: 'vault-1' }, { broadcast: emptyBroadcast() })

    expect(wrapper.get('.radio-news-widget__text-panel').text()).toContain(
      'No broadcast available today'
    )
    // No player chrome at all: no dial, no play/pause, no volume, no player shell.
    expect(wrapper.find('.radio-news-widget__dial').exists()).toBe(false)
    expect(wrapper.find('.radio-news-widget__play-btn').exists()).toBe(false)
    expect(wrapper.findComponent(Slider).exists()).toBe(false)
    // Regeneration survives, outside the player chrome.
    expect(wrapper.find('[aria-label="Regenerate the broadcast"]').exists()).toBe(true)
  })

  it('shows the caption overlay while playing', async () => {
    stubAudio(audioPair())
    // Mark today's broadcast as played so the login auto-play doesn't fire —
    // this test exercises the manual play button.
    localStorage.setItem('radio_news_played', JSON.stringify({ 'broadcast-1': Date.now() }))
    const wrapper = await mountWidget()
    expect(wrapper.find('.radio-news-widget__caption').exists()).toBe(false)

    await play(wrapper)

    expect(wrapper.get('.radio-news-widget__caption').text()).toContain('Vault 111 Evening News')
  })

  it('stays out of the HUD and logs the vault context when the broadcast request fails', async () => {
    mockApiGet.mockRejectedValue(new Error('network'))
    const warning = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const wrapper = mount(RadioNewsWidget, { props: { vaultId: 'vault-1' } })
    await flushPromises()

    // Nothing to listen to and nothing to read: no trigger, no empty console.
    expect(wrapper.find('.radio-news-widget__toggle').exists()).toBe(false)
    expect(wrapper.find('#radio-news-panel').exists()).toBe(false)
    expect(warning).toHaveBeenCalledWith(
      '[radio-news] Failed to load broadcast for vault vault-1: network'
    )
  })

  it('does not autoplay on mount', async () => {
    const { mock } = stubAudio(audioPair())
    const wrapper = await mountWidget()

    expect(mock.play).not.toHaveBeenCalled()
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
    const wrapper = mount(RadioNewsWidget, { props: { vaultId: 'vault-1' } })
    await wrapper.setProps({ vaultId: 'vault-2' })
    await flushPromises()

    const expected = [makeBroadcast({ id: 'second', title: 'Second Vault' })]
    expect(wrapper.emitted('newBroadcast')?.at(-1)).toEqual(expected)

    resolveFirst(makeBroadcast({ id: 'first', title: 'First Vault' }))
    await flushPromises()
    expect(wrapper.emitted('newBroadcast')?.at(-1)).toEqual(expected)
  })

  it('regenerates from the HUD control', async () => {
    const regenerated = makeBroadcast({ id: 'broadcast-2', title: 'Regenerated' })
    mockApiGet.mockResolvedValue(makeBroadcast({ id: 'broadcast-1' }))
    mockApiPost.mockResolvedValue(regenerated)
    const wrapper = mount(RadioNewsWidget, { props: { vaultId: 'vault-1' } })
    await flushPromises()

    await wrapper.get('.radio-news-widget__regenerate-btn').trigger('click')
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
    const wrapper = mount(RadioNewsWidget, { props: { vaultId: 'vault-1' } })
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
    const wrapper = mount(RadioNewsWidget, { props: { vaultId: 'vault-1' } })
    await flushPromises()
    await wrapper.get('.radio-news-widget__regenerate-btn').trigger('click')
    await flushPromises()

    await wrapper.setProps({ vaultId: 'vault-2' })
    await flushPromises()
    expect(wrapper.get('.radio-news-widget__regenerate-btn').attributes('disabled')).toBeUndefined()

    resolveRegenerate(makeBroadcast({ id: 'stale-regeneration' }))
    await flushPromises()
    expect(wrapper.get('.radio-news-widget__regenerate-btn').attributes('disabled')).toBeUndefined()
  })
})
