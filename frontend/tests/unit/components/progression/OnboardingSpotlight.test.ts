import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { reactive, ref } from 'vue'
import OnboardingSpotlight from '@/modules/progression/components/OnboardingSpotlight.vue'
import { useOnboardingState } from '@/core/composables/useOnboardingState'
import { useObjectivesStore } from '@/modules/progression/stores/objectives'
import type { Objective } from '@/modules/progression/models/objective'

const toast = vi.hoisted(() => ({ success: vi.fn(), warning: vi.fn() }))
vi.mock('@/core/composables/useToast', () => ({ useToast: () => toast }))

const stores = vi.hoisted(() => ({
  vault: { loadedVaults: {} as Record<string, unknown>, refreshVault: () => Promise.resolve() },
  dweller: {
    filter: { dwellers: [] as unknown[], fetchDwellersByVault: () => Promise.resolve() },
  },
  room: { availableRooms: [] as unknown[], fetchBuildableRooms: () => Promise.resolve() },
  exploration: { activeExplorations: {} as Record<string, unknown> },
}))

vi.mock('@/modules/auth/stores/auth', () => ({ useAuthStore: () => ({ token: 't' }) }))
vi.mock('@/modules/vault/stores/vault', () => ({ useVaultStore: () => stores.vault }))
vi.mock('@/modules/dwellers/stores/dweller', () => ({ useDwellerStore: () => stores.dweller }))
vi.mock('@/modules/rooms/stores/room', () => ({ useRoomStore: () => stores.room }))
vi.mock('@/modules/exploration/stores/exploration', () => ({
  useExplorationStore: () => stores.exploration,
}))
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

const boundedAnchor = (key: string) => {
  const anchor = document.createElement('div')
  anchor.setAttribute('data-onboarding', key)
  anchor.getBoundingClientRect = () =>
    ({
      width: 40,
      height: 20,
      top: 10,
      left: 10,
      right: 50,
      bottom: 30,
      x: 10,
      y: 10,
      toJSON: () => ({}),
    }) as DOMRect
  document.body.appendChild(anchor)
  return anchor
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  document.body.innerHTML = ''
  setActivePinia(createPinia())
  route.path = '/vault/v1'
  route.params.id = 'v1'
  stores.vault.loadedVaults = {}
  stores.dweller.filter.dwellers = []
  stores.room.availableRooms = []
  stores.exploration.activeExplorations = {}
  vi.spyOn(useObjectivesStore(), 'fetchObjectives').mockResolvedValue()
  // A vault created through the standard creation flow; the marker opts it into the welcome.
  useOnboardingState().patch('v1', { created: true })
})

describe('OnboardingSpotlight', () => {
  it('shows the welcome card first for a new vault', async () => {
    const wrapper = mountSpotlight()
    await flushPromises()
    expect(document.body.textContent).toContain('Welcome, Overseer')
    wrapper.unmount()
  })

  it('does not auto-welcome a vault that was not created through the flow', async () => {
    useOnboardingState().reset('v1')
    const wrapper = mountSpotlight()
    await flushPromises()
    expect(document.body.querySelector('.onboarding-card')).toBeNull()
    wrapper.unmount()
  })

  it('starts the tour on the first pending orientation lesson', async () => {
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    expect(document.body.textContent).toContain('Keep the power on')
    wrapper.unmount()
  })

  it('advances to the next lesson when the current one is acknowledged', async () => {
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    await clickButton('Continue')
    expect(document.body.textContent).toContain('Open the Power Generator')
    expect(useOnboardingState().teaching('v1').lessons['orientation.resources']).toBe('acknowledged')
    wrapper.unmount()
  })

  it('skips a single step without ending the tour', async () => {
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    await clickButton('Skip step')
    expect(useOnboardingState().teaching('v1').lessons['orientation.resources']).toBe('skipped')
    expect(useOnboardingState().vaultState('v1').skipped).toBeUndefined()
    expect(document.body.textContent).toContain('Open the Power Generator')
    wrapper.unmount()
  })

  it('skips the whole tour and persists it per vault', async () => {
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Skip tour')
    expect(document.body.querySelector('.onboarding-card')).toBeNull()
    expect(localStorage.getItem('onboarding:v1')).toContain('skipped')
    wrapper.unmount()
  })

  it('hands off once every orientation lesson is handled', async () => {
    acknowledgeLessons(...ALL_LESSONS)
    const wrapper = mountSpotlight()
    await flushPromises()
    expect(document.body.querySelector('.onboarding-card')).toBeNull()
    expect(document.body.querySelector('.onboarding-cutout')).toBeNull()
    wrapper.unmount()
  })

  it('claims the current objective-backed lesson once', async () => {
    const store = useObjectivesStore()
    store.objectives = [objective('first', { progress: 2 })]
    const claim = vi
      .spyOn(store, 'completeObjective')
      .mockResolvedValue(objective('first', { progress: 2, isCompleted: true }))
    acknowledgeLessons('orientation.resources', 'orientation.generator')
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    await clickButton('Claim 25 caps')
    expect(claim).toHaveBeenCalledTimes(1)
    expect(claim).toHaveBeenCalledWith('v1', 'first')
    wrapper.unmount()
  })

  it('renders a failed claim instead of swallowing it', async () => {
    const store = useObjectivesStore()
    store.objectives = [objective('first', { progress: 2 })]
    vi.spyOn(store, 'completeObjective').mockRejectedValue(new Error('capacity reached'))
    acknowledgeLessons('orientation.resources', 'orientation.generator')
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    await clickButton('Claim 25 caps')
    const error = document.querySelector('.onboarding-error')
    expect(error).not.toBeNull()
    expect((error?.textContent ?? '').length).toBeGreaterThan(0)
    wrapper.unmount()
  })

  it('disables the other controls while a claim is in flight', async () => {
    const store = useObjectivesStore()
    store.objectives = [objective('first', { progress: 2 })]
    vi.spyOn(store, 'completeObjective').mockImplementation(() => new Promise(() => {}))
    acknowledgeLessons('orientation.resources', 'orientation.generator')
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    findButton('Claim 25 caps')?.click()
    await flushPromises()
    const buttons = [...document.querySelectorAll<HTMLButtonElement>('.onboarding-actions button')]
    expect(buttons.length).toBeGreaterThan(0)
    expect(buttons.every((button) => button.disabled)).toBe(true)
    wrapper.unmount()
  })

  it('replays a claimed explanation with Continue and no reward action', async () => {
    const store = useObjectivesStore()
    store.objectives = [objective('first', { progress: 2, isCompleted: true })]
    const { replayOrientation, acknowledgeLesson } = useOnboardingState()
    replayOrientation('v1')
    acknowledgeLesson('v1', 'orientation.resources')
    acknowledgeLesson('v1', 'orientation.generator')
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    expect(document.body.textContent).toContain('Understand SPECIAL staffing')
    expect(findButton('Continue')).toBeDefined()
    expect(findButton('Claim 25 caps')).toBeUndefined()
    wrapper.unmount()
  })

  it('withholds a claim until the lowest unclaimed starter step is current', async () => {
    const store = useObjectivesStore()
    store.objectives = [
      objective('earlier', { sequence: 0, templateKey: 'starter:some earlier step' }),
      objective('first', { sequence: 1, progress: 2 }),
    ]
    acknowledgeLessons('orientation.resources', 'orientation.generator')
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    expect(document.body.querySelector('.onboarding-note')).not.toBeNull()
    expect(findButton('Open Starter')).toBeDefined()
    const claimButton = [...document.querySelectorAll('.onboarding-actions button')].find((button) =>
      button.textContent?.trim().startsWith('Claim ')
    )
    expect(claimButton).toBeUndefined()
    wrapper.unmount()
  })

  it('does not dim housing when the vault cannot afford it, and shows the blocker', async () => {
    const store = useObjectivesStore()
    store.objectives = [objective('housing', { templateKey: HOUSING_KEY })]
    stores.vault.loadedVaults = { v1: { bottle_caps: 100 } }
    stores.room.availableRooms = [{ name: 'Living room', base_cost: 150 }]
    acknowledgeLessons('orientation.resources', 'orientation.generator', 'orientation.staffing')
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    expect(document.body.textContent).toContain('Build more Living Quarters')
    expect(document.body.querySelector('.onboarding-note')?.textContent).toContain('Not enough caps')
    expect(document.querySelector('.onboarding-cutout')).toBeNull()
    wrapper.unmount()
  })

  it('offers a route back to construction for housing', async () => {
    const store = useObjectivesStore()
    store.objectives = [objective('housing', { templateKey: HOUSING_KEY })]
    stores.vault.loadedVaults = { v1: { bottle_caps: 500 } }
    stores.room.availableRooms = [{ name: 'Living room', base_cost: 150 }]
    acknowledgeLessons('orientation.resources', 'orientation.generator', 'orientation.staffing')
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    await clickButton('Open Vault')
    expect(router.push).toHaveBeenCalledWith('/vault/v1')
    wrapper.unmount()
  })

  it('blocks departure when no dweller is free, and shows the blocker', async () => {
    const store = useObjectivesStore()
    store.objectives = [objective('depart', { templateKey: DEPARTURE_KEY })]
    stores.dweller.filter.dwellers = [{ id: 'c', age_group: 'child', status: 'idle' }]
    acknowledgeLessons(
      'orientation.resources',
      'orientation.generator',
      'orientation.staffing',
      'orientation.housing'
    )
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    expect(document.body.textContent).toContain('Send a dweller exploring')
    expect(document.body.querySelector('.onboarding-note')?.textContent).toContain(
      'No dweller is free'
    )
    wrapper.unmount()
  })

  it('dims departure once a mature dweller is available', async () => {
    const store = useObjectivesStore()
    store.objectives = [objective('depart', { templateKey: DEPARTURE_KEY })]
    stores.dweller.filter.dwellers = [{ id: 'a', age_group: 'adult', status: 'resting' }]
    boundedAnchor('wasteland')
    acknowledgeLessons(
      'orientation.resources',
      'orientation.generator',
      'orientation.staffing',
      'orientation.housing'
    )
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    await vi.waitFor(() => expect(document.querySelector('.onboarding-cutout')).not.toBeNull())
    wrapper.unmount()
  })

  it('does not dim a lesson whose required data is not loaded', async () => {
    boundedAnchor('nav-dwellers')
    acknowledgeLessons('orientation.resources', 'orientation.generator')
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    expect(document.body.textContent).toContain('Understand SPECIAL staffing')
    expect(document.querySelector('.onboarding-cutout')).toBeNull()
    wrapper.unmount()
  })

  it('dims an eligible lesson that has a visible anchor', async () => {
    useObjectivesStore().objectives = [objective('first')]
    boundedAnchor('nav-dwellers')
    acknowledgeLessons('orientation.resources', 'orientation.generator')
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    await vi.waitFor(() => expect(document.querySelector('.onboarding-cutout')).not.toBeNull())
    wrapper.unmount()
  })

  it('shows the card without a cut-out when no anchor is present', async () => {
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    expect(document.body.textContent).toContain('Keep the power on')
    expect(document.querySelector('.onboarding-cutout')).toBeNull()
    wrapper.unmount()
  })
})
