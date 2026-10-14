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

  it('does not dim housing when the raised price is unaffordable, and shows it', async () => {
    seedHousing(125)
    acknowledgeLessons('orientation.resources', 'orientation.generator', 'orientation.staffing')
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    expect(document.body.textContent).toContain('Build more Living Quarters')
    expect(document.body.querySelector('.onboarding-note')?.textContent).toContain(
      'Not enough caps for Living Quarters (need 150)'
    )
    expect(document.querySelector('.onboarding-cutout')).toBeNull()
    wrapper.unmount()
  })

  it('offers a route back to construction for housing', async () => {
    seedHousing(500)
    acknowledgeLessons('orientation.resources', 'orientation.generator', 'orientation.staffing')
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    await clickButton('Open Vault')
    expect(router.push).toHaveBeenCalledWith('/vault/v1')
    wrapper.unmount()
  })

  it('blocks departure with the remedy matching the blocker', async () => {
    const store = useObjectivesStore()
    store.objectives = [objective('depart', { templateKey: DEPARTURE_KEY })]
    stores.dweller.filter.allDwellersLoadedVaultId = 'v1'
    acknowledgeLessons(
      'orientation.resources',
      'orientation.generator',
      'orientation.staffing',
      'orientation.housing'
    )

    stores.dweller.filter.allDwellers = [
      { id: 'c', age_group: 'child', status: 'idle', health: 50 },
    ]
    let wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    expect(document.body.querySelector('.onboarding-note')?.textContent).toContain(
      'Grow the vault to send an adult out'
    )
    wrapper.unmount()

    document.body.innerHTML = ''
    stores.dweller.filter.allDwellers = [
      { id: 'a', age_group: 'adult', status: 'exploring', health: 50 },
    ]
    wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    expect(document.body.querySelector('.onboarding-note')?.textContent).toContain(
      'Your dwellers are away'
    )
    wrapper.unmount()

    document.body.innerHTML = ''
    stores.dweller.filter.allDwellers = [
      { id: 'a', age_group: 'adult', status: 'resting', health: 0 },
    ]
    wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    expect(document.body.querySelector('.onboarding-note')?.textContent).toContain(
      'Treat a wounded dweller'
    )
    wrapper.unmount()
  })

  it('dims departure once a healthy mature dweller is available', async () => {
    const store = useObjectivesStore()
    store.objectives = [objective('depart', { templateKey: DEPARTURE_KEY })]
    stores.dweller.filter.allDwellersLoadedVaultId = 'v1'
    stores.dweller.filter.allDwellers = [
      { id: 'a', age_group: 'adult', status: 'resting', health: 50 },
    ]
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

  it('surfaces a failed objective read and retries', async () => {
    const store = useObjectivesStore()
    const fetchObjectives = vi.mocked(store.fetchObjectives)
    fetchObjectives.mockRejectedValue(new Error('offline'))

    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    expect(findButton('Retry')).toBeDefined()

    fetchObjectives.mockResolvedValue(undefined)
    await clickButton('Retry')
    expect(findButton('Retry')).toBeUndefined()
    wrapper.unmount()
  })

  it('clears a claim error when the lesson changes', async () => {
    const store = useObjectivesStore()
    store.objectives = [objective('first', { progress: 2 })]
    vi.spyOn(store, 'completeObjective').mockRejectedValue(new Error('rejected'))
    acknowledgeLessons('orientation.resources', 'orientation.generator')
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    await clickButton('Claim 25 caps')
    expect(document.querySelector('.onboarding-error')).not.toBeNull()

    await clickButton('Skip step')
    expect(document.querySelector('.onboarding-error')).toBeNull()
    wrapper.unmount()
  })

  it('ignores a hidden anchor and offers navigation', async () => {
    const hidden = document.createElement('div')
    hidden.setAttribute('data-onboarding', 'nav-dwellers')
    hidden.getBoundingClientRect = () =>
      ({
        width: 0,
        height: 0,
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        x: 0,
        y: 0,
        toJSON: () => ({}),
      }) as DOMRect
    document.body.appendChild(hidden)
    acknowledgeLessons('orientation.resources', 'orientation.generator')
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    expect(document.body.textContent).toContain('Understand SPECIAL staffing')
    expect(document.querySelector('.onboarding-cutout')).toBeNull()
    expect(findButton('Open Dwellers')).toBeDefined()
    wrapper.unmount()
  })
})
