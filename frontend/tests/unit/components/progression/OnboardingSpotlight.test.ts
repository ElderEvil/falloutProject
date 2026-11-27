import { enableAutoUnmount, mount, flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { createPinia, setActivePinia } from 'pinia'
import { effectScope, reactive, ref } from 'vue'
import OnboardingSpotlight from '@/modules/progression/components/OnboardingSpotlight.vue'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import { useBlockingOverlay } from '@/core/composables/useBlockingOverlay'
import { useOnboardingState } from '@/core/composables/useOnboardingState'
import { useObjectivesStore } from '@/modules/progression/stores/objectives'
import type { Objective } from '@/modules/progression/models/objective'
import type { components } from '@/core/types/api.generated'
import axios from '@/core/plugins/axios'

enableAutoUnmount(afterEach)

const toast = vi.hoisted(() => ({ success: vi.fn(), warning: vi.fn() }))
vi.mock('@/core/composables/useToast', () => ({ useToast: () => toast }))

const stores = vi.hoisted(() => ({
  vault: { loadedVaults: {} as Record<string, unknown>, refreshVault: () => Promise.resolve() },
  dweller: {
    filter: {
      allDwellers: [] as unknown[],
      allDwellersLoadedVaultId: null as string | null,
      fetchDwellersByVault: () => Promise.resolve(),
      fetchAllDwellers: () => Promise.resolve(),
    },
  },
  room: {
    rooms: [] as unknown[],
    roomsLoadedVaultId: null as string | null,
    availableRooms: [] as unknown[],
    fetchBuildableRooms: () => Promise.resolve(),
    fetchRooms: () => Promise.resolve(),
  },
}))

vi.mock('@/modules/auth/stores/auth', () => ({ useAuthStore: () => ({ token: 't' }) }))
vi.mock('@/modules/vault/stores/vault', () => ({ useVaultStore: () => stores.vault }))
vi.mock('@/modules/dwellers/stores/dweller', () => ({ useDwellerStore: () => stores.dweller }))
vi.mock('@/modules/rooms/stores/room', () => ({ useRoomStore: () => stores.room }))
vi.mock('@vueuse/core', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@vueuse/core')>()),
  usePreferredReducedMotion: () => ref('no-preference'),
}))

const route = reactive({ path: '/vault/v1', params: { id: 'v1' } })
const router = { push: vi.fn() }
vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => router }))

const STAFFING_KEY = 'starter:assign a dweller correctly'
const HOUSING_KEY = 'starter:build a living quarters'
const DEPARTURE_KEY = 'starter:send a dweller exploring'

const ALL_LESSONS = [
  'orientation.resources',
  'orientation.generator',
  'orientation.staffing',
  'orientation.housing',
  'orientation.departure',
] as const

const THROUGH_STAFFING = ALL_LESSONS.slice(0, 3)
const THROUGH_HOUSING = ALL_LESSONS.slice(0, 4)

interface ObjectiveOptions {
  progress?: number
  total?: number
  sequence?: number
  templateKey?: string
  isCompleted?: boolean
}

const objective = (id: string, options: ObjectiveOptions = {}): Objective => {
  const {
    progress = 0,
    total = 2,
    sequence = 0,
    templateKey = STAFFING_KEY,
    isCompleted = false,
  } = options
  return {
    id,
    vault_id: 'v1',
    challenge: 'Match a dweller to their room',
    description: 'Do the thing.',
    progress,
    total,
    reward: '25 caps',
    is_completed: isCompleted,
    category: 'starter',
    sequence,
    template_key: templateKey,
    objective_type: 'assign_correct',
    target_entity: {},
    created_at: '',
  }
}

const mountSpotlight = () => mount(OnboardingSpotlight, { attachTo: document.body })

const findButton = (label: string) =>
  [...document.querySelectorAll<HTMLButtonElement>('.onboarding-actions button')].find(
    (element) => element.textContent?.trim() === label
  )

const clickButton = async (label: string) => {
  findButton(label)?.click()
  await flushPromises()
}

const acknowledgeLessons = (...ids: string[]) => {
  const { acknowledgeLesson } = useOnboardingState()
  for (const id of ids) acknowledgeLesson('v1', id)
}

/** Mount, settle the objective read and press Start — the setup most lessons share. */
const startTour = async () => {
  const wrapper = mountSpotlight()
  await flushPromises()
  await clickButton('Start')
  return wrapper
}

const startFrom = async (...lessons: readonly string[]) => {
  acknowledgeLessons(...lessons)
  return startTour()
}

/** Field-guide lessons all begin after the introduction is taught and welcomed. */
const arriveAtFieldGuide = () => {
  acknowledgeLessons(...THROUGH_HOUSING)
  useOnboardingState().patch('v1', { welcomed: true })
}

const rect = (top: number, width = 40, height = 20): DOMRect =>
  ({
    width,
    height,
    top,
    left: 10,
    right: 10 + width,
    bottom: top + height,
    x: 10,
    y: top,
    toJSON: () => ({}),
  }) as DOMRect

const addAnchor = (key: string, size: () => DOMRect) => {
  const anchor = document.createElement('div')
  anchor.setAttribute('data-onboarding', key)
  anchor.getBoundingClientRect = size
  document.body.appendChild(anchor)
  return anchor
}

const boundedAnchor = (key: string) => addAnchor(key, () => rect(10))
const hiddenAnchor = (key: string) => addAnchor(key, () => rect(0, 0, 0))

const seedHousing = (caps: number) => {
  useObjectivesStore().objectives = [objective('housing', { templateKey: HOUSING_KEY })]
  stores.vault.loadedVaults = { v1: { bottle_caps: caps } }
  stores.room.availableRooms = [
    { name: 'Living room', category: 'Capacity', base_cost: 100, incremental_cost: 25 },
  ]
  stores.room.rooms = [{ category: 'Capacity' }, { category: 'Capacity' }]
  stores.room.roomsLoadedVaultId = 'v1'
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  document.body.innerHTML = ''
  setActivePinia(createPinia())
  route.path = '/vault/v1'
  route.params.id = 'v1'
  stores.vault.loadedVaults = {}
  stores.dweller.filter.allDwellers = []
  stores.dweller.filter.allDwellersLoadedVaultId = null
  stores.room.rooms = []
  stores.room.roomsLoadedVaultId = null
  stores.room.availableRooms = []
  vi.spyOn(useObjectivesStore(), 'fetchObjectives').mockResolvedValue()
  useOnboardingState().resetAll()
  // A vault created through the standard creation flow; the marker opts it into the welcome.
  useOnboardingState().patch('v1', { created: true })
})

describe('OnboardingSpotlight', () => {
  it('offers an earned starter claim from the API response without per-row vault metadata', async () => {
    const row = {
      id: 'staffing',
      challenge: 'Match a dweller to their room',
      category: 'starter',
      objective_type: 'assign_correct',
      target_amount: 1,
      template_key: STAFFING_KEY,
      sequence: 0,
      reward: '25 caps',
      progress: 1,
      total: 1,
      is_completed: false,
    } satisfies components['schemas']['ObjectiveRead']
    const get = vi.spyOn(axios, 'get').mockResolvedValue({ data: [row] })
    const store = useObjectivesStore()
    vi.mocked(store.fetchObjectives).mockRestore()
    await startFrom('orientation.resources', 'orientation.generator')

    expect(get).toHaveBeenCalledWith('/api/v1/objectives/v1/', {
      params: { skip: 0, limit: 100 },
    })
    expect(document.body.textContent).toContain('1 / 1')
    expect(findButton('Claim 25 caps')).toBeDefined()
    expect(store.objectives[0]?.vault_id).toBe('v1')
    get.mockRestore()
  })

  it('shows the welcome card first for a new vault', async () => {
    mountSpotlight()
    await flushPromises()
    expect(document.body.textContent).toContain('Welcome, Overseer')
  })

  it('does not auto-welcome a vault that was not created through the flow', async () => {
    useOnboardingState().reset('v1')
    mountSpotlight()
    await flushPromises()
    expect(document.body.querySelector('.onboarding-card')).toBeNull()
  })

  it('starts the tour on the first pending orientation lesson, with no cut-out and no anchor', async () => {
    await startTour()
    expect(document.body.textContent).toContain('Check your reserves')
    expect(document.querySelector('.onboarding-cutout')).toBeNull()
  })

  it('advances to the next lesson when the current one is acknowledged', async () => {
    await startTour()
    await clickButton('Continue')
    expect(document.body.textContent).toContain('Open the Power Generator')
    expect(useOnboardingState().teaching('v1').lessons['orientation.resources']).toBe(
      'acknowledged'
    )
  })

  it('skips a single step without ending the tour', async () => {
    await startTour()
    await clickButton('Skip step')
    expect(useOnboardingState().teaching('v1').lessons['orientation.resources']).toBe('skipped')
    expect(useOnboardingState().vaultState('v1').skipped).toBeUndefined()
    expect(document.body.textContent).toContain('Open the Power Generator')
  })

  it('skips the whole tour and persists it per vault', async () => {
    await startTour()
    await clickButton('Skip tour')
    expect(document.body.querySelector('.onboarding-card')).toBeNull()
    expect(localStorage.getItem('onboarding:v1')).toContain('skipped')
  })

  it('hands off once every orientation lesson is handled', async () => {
    acknowledgeLessons(...ALL_LESSONS)
    mountSpotlight()
    await flushPromises()
    expect(document.body.querySelector('.onboarding-card')).toBeNull()
    expect(document.body.querySelector('.onboarding-cutout')).toBeNull()
  })

  it('claims the current objective-backed lesson once', async () => {
    const store = useObjectivesStore()
    store.objectives = [objective('first', { progress: 2 })]
    const claim = vi
      .spyOn(store, 'completeObjective')
      .mockResolvedValue(objective('first', { progress: 2, isCompleted: true }))
    await startFrom('orientation.resources', 'orientation.generator')
    await clickButton('Claim 25 caps')
    expect(claim).toHaveBeenCalledTimes(1)
    expect(claim).toHaveBeenCalledWith('v1', 'first')
  })

  it('renders a failed claim instead of swallowing it', async () => {
    const store = useObjectivesStore()
    store.objectives = [objective('first', { progress: 2 })]
    vi.spyOn(store, 'completeObjective').mockRejectedValue(new Error('capacity reached'))
    await startFrom('orientation.resources', 'orientation.generator')
    await clickButton('Claim 25 caps')
    const error = document.querySelector('.onboarding-error')
    expect(error).not.toBeNull()
    expect((error?.textContent ?? '').length).toBeGreaterThan(0)
  })

  it('disables the other controls while a claim is in flight', async () => {
    const store = useObjectivesStore()
    store.objectives = [objective('first', { progress: 2 })]
    vi.spyOn(store, 'completeObjective').mockImplementation(() => new Promise(() => {}))
    await startFrom('orientation.resources', 'orientation.generator')
    findButton('Claim 25 caps')?.click()
    await flushPromises()
    const buttons = [...document.querySelectorAll<HTMLButtonElement>('.onboarding-actions button')]
    expect(buttons.length).toBeGreaterThan(0)
    expect(buttons.every((button) => button.disabled)).toBe(true)
  })

  it('replays a claimed explanation with Continue and no reward action', async () => {
    useObjectivesStore().objectives = [objective('first', { progress: 2, isCompleted: true })]
    const { replayOrientation, acknowledgeLesson } = useOnboardingState()
    replayOrientation('v1')
    acknowledgeLesson('v1', 'orientation.resources')
    acknowledgeLesson('v1', 'orientation.generator')
    await startTour()
    expect(document.body.textContent).toContain('Understand SPECIAL staffing')
    expect(findButton('Continue')).toBeDefined()
    expect(findButton('Claim 25 caps')).toBeUndefined()
  })

  it('does not block an earned step behind earlier unclaimed starter steps', async () => {
    useObjectivesStore().objectives = [
      objective('earlier', { sequence: 0, templateKey: 'starter:some earlier step' }),
      objective('first', { sequence: 1, progress: 2 }),
    ]
    await startFrom('orientation.resources', 'orientation.generator')
    expect(findButton('Open Starter')).toBeUndefined()
    expect(document.body.textContent).not.toContain('Claim your earlier reward in Starter first.')
    expect(findButton('Claim 25 caps')).toBeDefined()
  })

  it('does not dim housing when the raised price is unaffordable, and shows it', async () => {
    seedHousing(125)
    await startFrom(...THROUGH_STAFFING)
    expect(document.body.textContent).toContain('Build more Living Quarters')
    expect(document.body.querySelector('.onboarding-note')?.textContent).toContain(
      'Not enough caps for Living Quarters (need 150)'
    )
    expect(document.querySelector('.onboarding-cutout')).toBeNull()
  })

  it('offers a route back to construction when housing is taught on another page', async () => {
    route.path = '/vault/v1/dwellers'
    seedHousing(500)
    await startFrom(...THROUGH_STAFFING)
    await clickButton('Open Vault')
    expect(router.push).toHaveBeenCalledWith('/vault/v1')
  })

  it.each([
    [
      [{ id: 'c', age_group: 'child', status: 'idle', health: 50 }],
      'Grow the vault to send an adult out',
    ],
    [[{ id: 'a', age_group: 'adult', status: 'exploring', health: 50 }], 'Your dwellers are away'],
    [[{ id: 'a', age_group: 'adult', status: 'resting', health: 0 }], 'Treat a wounded dweller'],
  ])('blocks departure with the remedy matching the blocker (%#)', async (dwellers, note) => {
    useObjectivesStore().objectives = [objective('depart', { templateKey: DEPARTURE_KEY })]
    stores.dweller.filter.allDwellersLoadedVaultId = 'v1'
    stores.dweller.filter.allDwellers = dwellers
    await startFrom(...THROUGH_HOUSING)
    expect(document.body.querySelector('.onboarding-note')?.textContent).toContain(note)
  })

  it('dims the drag source once a healthy mature dweller is available', async () => {
    useObjectivesStore().objectives = [objective('depart', { templateKey: DEPARTURE_KEY })]
    stores.dweller.filter.allDwellersLoadedVaultId = 'v1'
    stores.dweller.filter.allDwellers = [
      { id: 'a', age_group: 'adult', status: 'resting', health: 50 },
    ]
    boundedAnchor('dweller-drag-source')
    await startFrom(...THROUGH_HOUSING)
    await vi.waitFor(() => expect(document.querySelector('.onboarding-cutout')).not.toBeNull())
    expect(document.body.textContent).toContain('Pick your explorer')
  })

  it('does not dim a lesson whose required data is not loaded', async () => {
    boundedAnchor('nav-dwellers')
    await startFrom('orientation.resources', 'orientation.generator')
    expect(document.body.textContent).toContain('Understand SPECIAL staffing')
    expect(document.querySelector('.onboarding-cutout')).toBeNull()
  })

  it('dims an eligible lesson that has a visible anchor', async () => {
    useObjectivesStore().objectives = [objective('first')]
    boundedAnchor('nav-dwellers')
    await startFrom('orientation.resources', 'orientation.generator')
    await vi.waitFor(() => expect(document.querySelector('.onboarding-cutout')).not.toBeNull())
  })

  it('surfaces a failed objective read and retries', async () => {
    const store = useObjectivesStore()
    const fetchObjectives = vi.mocked(store.fetchObjectives)
    fetchObjectives.mockRejectedValue(new Error('offline'))

    await startTour()
    expect(findButton('Retry')).toBeDefined()

    fetchObjectives.mockResolvedValue(undefined)
    await clickButton('Retry')
    expect(findButton('Retry')).toBeUndefined()
  })

  it('clears a claim error when the lesson changes', async () => {
    const store = useObjectivesStore()
    store.objectives = [objective('first', { progress: 2 })]
    vi.spyOn(store, 'completeObjective').mockRejectedValue(new Error('rejected'))
    await startFrom('orientation.resources', 'orientation.generator')
    await clickButton('Claim 25 caps')
    expect(document.querySelector('.onboarding-error')).not.toBeNull()

    await clickButton('Skip step')
    expect(document.querySelector('.onboarding-error')).toBeNull()
  })

  it('ignores a hidden anchor and offers navigation', async () => {
    hiddenAnchor('nav-dwellers')
    await startFrom('orientation.resources', 'orientation.generator')
    expect(document.body.textContent).toContain('Understand SPECIAL staffing')
    expect(document.querySelector('.onboarding-cutout')).toBeNull()
    expect(findButton('Open Dwellers')).toBeDefined()
  })

  describe('dialog coordination', () => {
    const openOverlay = () => {
      const scope = effectScope()
      const open = ref(false)
      scope.run(() => useBlockingOverlay(open))
      return { scope, open }
    }

    it('suspends the card and cut-out while a dialog is open, then resumes the same lesson', async () => {
      boundedAnchor('resource-power')
      await startTour()
      expect(document.body.textContent).toContain('Check your reserves')
      expect(document.querySelector('.onboarding-card')).not.toBeNull()

      const { scope, open } = openOverlay()
      open.value = true
      await flushPromises()
      expect(document.querySelector('.onboarding-card')).toBeNull()
      expect(document.querySelector('.onboarding-cutout--off')).not.toBeNull()

      open.value = false
      await flushPromises()
      expect(document.querySelector('.onboarding-card')).not.toBeNull()
      expect(document.body.textContent).toContain('Check your reserves')

      scope.stop()
    })

    it('stays suspended until every stacked dialog closes', async () => {
      await startTour()
      expect(document.querySelector('.onboarding-card')).not.toBeNull()

      const roomDialog = openOverlay()
      const confirmDialog = openOverlay()
      roomDialog.open.value = true
      confirmDialog.open.value = true
      await flushPromises()
      expect(document.querySelector('.onboarding-card')).toBeNull()

      confirmDialog.open.value = false
      await flushPromises()
      expect(document.querySelector('.onboarding-card')).toBeNull()

      roomDialog.open.value = false
      await flushPromises()
      expect(document.querySelector('.onboarding-card')).not.toBeNull()

      roomDialog.scope.stop()
      confirmDialog.scope.stop()
    })

    it('releases suspension when an open dialog unmounts with the route', async () => {
      await startTour()
      expect(document.querySelector('.onboarding-card')).not.toBeNull()

      const dialog = mount(TerminalModal, {
        props: { open: true },
        global: { stubs: { Icon: true, Teleport: { template: '<div><slot /></div>' } } },
      })
      await flushPromises()
      expect(document.querySelector('.onboarding-card')).toBeNull()

      dialog.unmount()
      await flushPromises()
      expect(document.querySelector('.onboarding-card')).not.toBeNull()
    })
  })

  it('offers to scroll to an off-screen control instead of navigating in place', async () => {
    const offscreen = addAnchor('nav-dwellers', () => rect(5000))
    const scrollIntoView = vi.fn()
    offscreen.scrollIntoView = scrollIntoView
    await startFrom('orientation.resources', 'orientation.generator')

    // The control is on this page but out of view: scroll, do not re-navigate.
    expect(findButton('Show control')).toBeDefined()
    expect(findButton('Open Dwellers')).toBeUndefined()

    await clickButton('Show control')
    expect(scrollIntoView).toHaveBeenCalled()
    expect(router.push).not.toHaveBeenCalled()
  })

  describe('guide card', () => {
    const card = () => document.querySelector<HTMLElement>('.onboarding-card')
    const collapseToggle = () => document.querySelector<HTMLButtonElement>('.onboarding-collapse')

    it('collapses to the title and expands again, preserving the lesson', async () => {
      await startTour()
      expect(card()?.textContent).toContain('Check whether power, food, and water')
      expect(collapseToggle()?.getAttribute('aria-expanded')).toBe('true')

      collapseToggle()?.click()
      await flushPromises()
      expect(collapseToggle()?.getAttribute('aria-expanded')).toBe('false')
      expect(document.querySelector('#onboarding-guide-body')?.getAttribute('style')).toContain(
        'display: none'
      )
      // Collapsed keeps the lesson title on screen.
      expect(card()?.textContent).toContain('Check your reserves')

      collapseToggle()?.click()
      await flushPromises()
      expect(collapseToggle()?.getAttribute('aria-expanded')).toBe('true')
      expect(
        document.querySelector('#onboarding-guide-body')?.getAttribute('style') ?? ''
      ).not.toContain('display: none')
    })

    it('keeps a collapsed card collapsed when objectives refresh, without stealing focus', async () => {
      await startTour()
      collapseToggle()?.click()
      await flushPromises()
      expect(collapseToggle()?.getAttribute('aria-expanded')).toBe('false')

      useObjectivesStore().objectives = [objective('first', { progress: 1 })]
      await flushPromises()

      expect(collapseToggle()?.getAttribute('aria-expanded')).toBe('false')
      expect(document.body.textContent).toContain('Check your reserves')
    })
  })

  describe('viewport lifecycle', () => {
    it('restores the spotlight after an off-screen control is scrolled into view', async () => {
      let onScreen = false
      const anchor = addAnchor('resource-power', () => (onScreen ? rect(10) : rect(5000)))
      anchor.scrollIntoView = vi.fn()

      await startTour()
      expect(findButton('Show control')).toBeDefined()
      expect(document.querySelector('.onboarding-cutout')).toBeNull()

      onScreen = true
      await clickButton('Show control')

      await vi.waitFor(() => expect(document.querySelector('.onboarding-cutout')).not.toBeNull())
      expect(findButton('Show control')).toBeUndefined()
    })

    it('swaps the spotlight for navigation when resizing hides the control', async () => {
      const anchor = boundedAnchor('nav-dwellers')
      useObjectivesStore().objectives = [objective('first')]
      await startFrom('orientation.resources', 'orientation.generator')
      await vi.waitFor(() => expect(document.querySelector('.onboarding-cutout')).not.toBeNull())

      anchor.getBoundingClientRect = () => rect(0, 0, 0)
      window.dispatchEvent(new Event('resize'))

      await vi.waitFor(() => expect(document.querySelector('.onboarding-cutout')).toBeNull())
      expect(findButton('Open Dwellers')).toBeDefined()
    })
  })
})

describe('first-session continuity', () => {
  const mountHandoff = () =>
    mount(OnboardingSpotlight, {
      attachTo: document.body,
      global: {
        stubs: {
          IntroHandoffCard: {
            props: ['vaultId', 'compact', 'milestone'],
            emits: ['dismiss', 'claim', 'hide'],
            template: `<section :aria-label="compact ? 'Vault guide' : 'First expedition handoff'">
              <template v-if="compact"><p>{{ milestone?.challenge }}</p><button @click="$emit('claim')">Claim milestone</button><button @click="$emit('hide')">Hide guide</button></template>
              <button v-else @click="$emit('dismiss')">Finish intro</button></section>`,
          },
        },
      },
    })

  const finishOrientation = () => {
    acknowledgeLessons(...ALL_LESSONS)
    useOnboardingState().patch('v1', { welcomed: true })
    useObjectivesStore().objectives = [
      objective('departure', {
        templateKey: DEPARTURE_KEY,
        progress: 1,
        total: 1,
        isCompleted: true,
      }),
    ]
  }

  const handoff = () => document.querySelector('[aria-label="First expedition handoff"]')
  const guideButton = (label: string) =>
    [...document.querySelectorAll<HTMLButtonElement>('[aria-label="Vault guide"] button')].find(
      (button) => button.textContent === label
    )

  it('hands off only after a real departure claim and keeps dismissal per vault', async () => {
    finishOrientation()
    mountHandoff()
    await flushPromises()
    expect(!!handoff()).toBe(true)
    expect(document.querySelector('.onboarding-cutout')).toBeNull()

    document
      .querySelector<HTMLButtonElement>('[aria-label="First expedition handoff"] button')!
      .click()
    await flushPromises()
    expect(useOnboardingState().vaultState('v1').handoffDismissed).toBe(true)
    expect(useOnboardingState().vaultState('v2').handoffDismissed).toBeUndefined()
    expect(!!handoff()).toBe(false)
  })

  it.each(['skip', 'replay', 'unearned', 'other-vault'])(
    'does not show the handoff for %s',
    async (condition) => {
      finishOrientation()
      if (condition === 'skip') useOnboardingState().skipTour('v1')
      if (condition === 'replay') {
        useOnboardingState().replayOrientation('v1')
        acknowledgeLessons(...ALL_LESSONS)
      }
      if (condition === 'unearned') useObjectivesStore().objectives[0]!.is_completed = false
      if (condition === 'other-vault') useObjectivesStore().objectives[0]!.vault_id = 'v2'
      mountHandoff()
      await flushPromises()
      expect(!!handoff()).toBe(false)
    }
  )

  it('shows a celebration and roster handoff when housing is claimed in the guide', async () => {
    seedHousing(200)
    acknowledgeLessons('orientation.resources', 'orientation.generator', 'orientation.staffing')
    const store = useObjectivesStore()
    store.objectives[0]!.progress = 2
    store.objectives[0]!.reward = 'dweller:Wanderer'
    const claimed = { ...store.objectives[0]!, is_completed: true }
    vi.spyOn(store, 'completeObjective').mockImplementation(async () => {
      store.objectives = [claimed]
      return claimed
    })
    await startTour()
    await clickButton('Claim Wanderer')
    expect(document.body.textContent).toContain('Wanderer has joined your vault')
    const view = [...document.querySelectorAll<HTMLButtonElement>('button')].find(
      (button) => button.textContent?.trim() === 'View dwellers'
    )
    expect(view).toBeDefined()
    view!.click()
    await flushPromises()
    expect(router.push).toHaveBeenCalledWith('/vault/v1/dwellers')
  })

  it('continues the optional vault guide after finishing the introduction, and persists hiding it', async () => {
    finishOrientation()
    useObjectivesStore().objectives.push({
      ...objective('food', { templateKey: 'starter:produce 100 food#v3', sequence: 12 }),
      challenge: 'Produce 100 Food',
    })
    let wrapper = mountHandoff()
    await flushPromises()
    const finish = document.querySelector(
      '[aria-label="First expedition handoff"] button'
    ) as HTMLButtonElement
    finish.click()
    await flushPromises()
    expect(useOnboardingState().vaultState('v1').handoffDismissed).toBe(true)
    expect(handoff()).toBeNull()
    expect(document.querySelector('[aria-label="Vault guide"]')?.textContent).toContain(
      'Produce 100 Food'
    )
    wrapper.unmount()

    wrapper = mountHandoff()
    await flushPromises()
    expect(document.querySelector('[aria-label="Vault guide"]')).not.toBeNull()
    guideButton('Hide guide')!.click()
    await flushPromises()
    expect(useOnboardingState().vaultState('v1').skipped).toBe(true)
    expect(document.querySelector('[aria-label="Vault guide"]')).toBeNull()
    wrapper.unmount()
  })

  it('claims a later milestone through the shared claim owner and celebrates the earned reward', async () => {
    finishOrientation()
    useOnboardingState().patch('v1', { handoffDismissed: true })
    const food = objective('food', {
      templateKey: 'starter:produce 100 food#v3',
      sequence: 12,
      progress: 100,
      total: 100,
    })
    const store = useObjectivesStore()
    store.objectives.push(food)
    const complete = vi
      .spyOn(store, 'completeObjective')
      .mockResolvedValue({ ...food, is_completed: true })
    mountHandoff()
    await flushPromises()

    guideButton('Claim milestone')!.click()
    await flushPromises()
    expect(complete).toHaveBeenCalledWith('v1', 'food')
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain('Objective Complete!')
  })
})

describe('field guide milestones', () => {
  it('prepares equipment before departure and claims an earned reward without an earlier claim gate', async () => {
    arriveAtFieldGuide()
    const store = useObjectivesStore()
    const weapon = objective('weapon', {
      templateKey: 'starter:equip a weapon',
      sequence: 3,
      progress: 1,
      total: 1,
    })
    store.objectives = [objective('departure', { templateKey: DEPARTURE_KEY, sequence: 2 }), weapon]
    const complete = vi
      .spyOn(store, 'completeObjective')
      .mockResolvedValue({ ...weapon, is_completed: true })
    mountSpotlight()
    await flushPromises()

    expect(document.body.textContent).toContain('Arm your explorer')
    expect(document.body.textContent).toContain('Prepare equipment')
    expect(findButton('Claim 25 caps')).toBeDefined()
    await clickButton('Claim 25 caps')
    expect(complete).toHaveBeenCalledWith('v1', 'weapon')

    const dialog = document.querySelector('[role="dialog"]')
    expect(dialog?.textContent).toContain('Objective Complete!')
    const confirm = [...dialog!.querySelectorAll<HTMLButtonElement>('button')].find(
      (button) => button.textContent?.trim() === 'Continue'
    )
    confirm?.click()
    await flushPromises()
    expect(document.body.textContent).toContain('Pick your explorer')
    expect(useOnboardingState().teaching('v1').lessons['orientation.departure']).toBeUndefined()
    await clickButton('Continue')
    await flushPromises()
    expect(document.body.textContent).toContain('Drag the card to The Wasteland')
  })

  it('shows the milestone roadmap and a useful destination before equipment is earned', async () => {
    arriveAtFieldGuide()
    useObjectivesStore().objectives = [
      objective('weapon', { templateKey: 'starter:equip a weapon' }),
    ]
    mountSpotlight()
    await flushPromises()

    expect(document.body.textContent).toContain('VAULT FIELD GUIDE')
    expect(document.querySelector('[aria-label="Introduction milestones"]')?.textContent).toContain(
      'Welcome someone'
    )
    expect(findButton('Open Dwellers')).toBeDefined()
    expect(findButton('Claim 25 caps')).toBeUndefined()
    await clickButton('Open Dwellers')
    expect(router.push).toHaveBeenCalledWith('/vault/v1/dwellers')
    expect(useOnboardingState().teaching('v1').lessons['orientation.weapon']).toBeUndefined()
  })

  it('does not reopen equipment teaching for a completed existing introduction', async () => {
    acknowledgeLessons(...ALL_LESSONS)
    useOnboardingState().patch('v1', { welcomed: true, handoffDismissed: true })
    useObjectivesStore().objectives = [
      objective('weapon', { templateKey: 'starter:equip a weapon' }),
    ]
    mountSpotlight()
    await flushPromises()
    expect(document.querySelector('[aria-label="Vault onboarding"]')).toBeNull()
  })
})

describe('lesson destination handoff', () => {
  // Chamber lessons that happen on a dweller detail must anchor there, not bounce to the roster.
  async function handoffOnDetail(
    anchor: string,
    lessonId: string,
    key: string,
    absent: string,
    extra: readonly string[] = []
  ) {
    arriveAtFieldGuide()
    acknowledgeLessons(...extra)
    route.path = '/vault/v1/dwellers/d1'
    boundedAnchor(anchor)
    useObjectivesStore().objectives = [objective(lessonId, { templateKey: key })]
    mountSpotlight()
    await flushPromises()
    expect(document.querySelector('.onboarding-cutout')).not.toBeNull()
    expect(findButton(absent)).toBeUndefined()
  }

  it('highlights the Equipment tab on a dweller detail', () =>
    handoffOnDetail('dweller-equipment-tab', 'weapon', 'starter:equip a weapon', 'Open Dwellers'))

  it('points at the card the drag starts from on the vault floor', async () => {
    arriveAtFieldGuide()
    stores.dweller.filter.allDwellers = [
      { id: 'd1', age_group: 'adult', status: 'idle', health: 100 },
    ]
    stores.dweller.filter.allDwellersLoadedVaultId = 'v1'
    boundedAnchor('dweller-drag-source')
    useObjectivesStore().objectives = [objective('departure', { templateKey: DEPARTURE_KEY })]
    mountSpotlight()
    await flushPromises()
    expect(document.querySelector('.onboarding-cutout')).not.toBeNull()
    expect(document.body.textContent).toContain('Pick your explorer')
  })

  it('points at the dropzone once the crew step is acknowledged', async () => {
    arriveAtFieldGuide()
    acknowledgeLessons('orientation.departure.crew')
    stores.dweller.filter.allDwellers = [
      { id: 'd1', age_group: 'adult', status: 'idle', health: 100 },
    ]
    stores.dweller.filter.allDwellersLoadedVaultId = 'v1'
    boundedAnchor('wasteland')
    useObjectivesStore().objectives = [objective('departure', { templateKey: DEPARTURE_KEY })]
    mountSpotlight()
    await flushPromises()
    expect(document.querySelector('.onboarding-cutout')).not.toBeNull()
    expect(document.body.textContent).toContain('Release to send!')
  })

  it('points to the prepared dispatch action', () => {
    stores.dweller.filter.allDwellers = [
      { id: 'd1', age_group: 'adult', status: 'idle', health: 100 },
    ]
    stores.dweller.filter.allDwellersLoadedVaultId = 'v1'
    return handoffOnDetail('dweller-departure', 'departure', DEPARTURE_KEY, 'Open Vault', [
      'orientation.departure.crew',
      'orientation.departure.drag',
    ])
  })
})
