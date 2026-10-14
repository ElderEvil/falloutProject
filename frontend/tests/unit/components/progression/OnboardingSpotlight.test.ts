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
vi.mock('@/modules/auth/stores/auth', () => ({ useAuthStore: () => ({ token: 't' }) }))
vi.mock('@/modules/vault/stores/vault', () => ({
  useVaultStore: () => ({ refreshVault: vi.fn().mockResolvedValue(undefined) }),
}))
vi.mock('@vueuse/core', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@vueuse/core')>()),
  usePreferredReducedMotion: () => ref('no-preference'),
}))

const route = reactive({ path: '/vault/v1', params: { id: 'v1' } })
vi.mock('vue-router', () => ({ useRoute: () => route }))

const arc = {
  assign: { key: 'starter:assign a dweller correctly', sequence: 0, challenge: 'Match a dweller to their room' },
  build: { key: 'starter:build a living quarters', sequence: 1, challenge: 'Build a Living Quarters' },
  explore: { key: 'starter:send a dweller exploring', sequence: 2, challenge: 'Send a dweller exploring' },
  reach18: { key: 'starter:reach 18 dwellers', sequence: 4, challenge: 'Reach 18 Dwellers' },
} as const

const objective = (id: string, step: keyof typeof arc, progress = 0): Objective => ({
  id,
  vault_id: 'v1',
  challenge: arc[step].challenge,
  description: 'Do the thing.',
  progress,
  total: 2,
  reward: '25 caps',
  is_completed: false,
  category: 'starter',
  sequence: arc[step].sequence,
  template_key: arc[step].key,
  objective_type: 'collect',
  target_entity: { resource_type: 'caps' },
  created_at: '',
})

const mountSpotlight = () => mount(OnboardingSpotlight, { attachTo: document.body })

const clickButton = async (label: string) => {
  const button = [
    ...document.querySelectorAll<HTMLButtonElement>('.onboarding-actions button'),
  ].find((element) => element.textContent?.trim() === label)
  button?.click()
  await flushPromises()
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  document.body.innerHTML = ''
  setActivePinia(createPinia())
  route.path = '/vault/v1'
  route.params.id = 'v1'
  vi.spyOn(useObjectivesStore(), 'fetchObjectives').mockResolvedValue()
  // A vault created through the standard creation flow; the marker opts it into the welcome.
  useOnboardingState().patch('v1', { created: true })
})

describe('OnboardingSpotlight', () => {
  it('shows the welcome card first for a new vault', async () => {
    useObjectivesStore().objectives = [objective('first', 'assign')]
    const wrapper = mountSpotlight()
    await flushPromises()
    expect(document.body.textContent).toContain('Welcome, Overseer')
    wrapper.unmount()
  })

  it('does not auto-welcome a vault that was not created through the flow', async () => {
    useOnboardingState().reset('v1')
    useObjectivesStore().objectives = [objective('first', 'assign')]
    const wrapper = mountSpotlight()
    await flushPromises()
    expect(document.body.textContent).not.toContain('Welcome, Overseer')
    expect(document.body.textContent).toContain(arc.assign.challenge)
    wrapper.unmount()
  })

  it('starts the tour on the first unclaimed orientation step', async () => {
    useObjectivesStore().objectives = [objective('second', 'build'), objective('first', 'assign')]
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    expect(document.body.textContent).toContain(arc.assign.challenge)
    expect(document.body.textContent).not.toContain(arc.build.challenge)
    wrapper.unmount()
  })

  it('hands off instead of dimming a population wait after the orientation', async () => {
    useObjectivesStore().objectives = [objective('wait', 'reach18')]
    const wrapper = mountSpotlight()
    await flushPromises()
    expect(document.body.querySelector('.onboarding-card')).toBeNull()
    expect(document.body.querySelector('.onboarding-cutout')).toBeNull()
    expect(document.body.textContent).not.toContain(arc.reach18.challenge)
    wrapper.unmount()
  })

  it('shows the guide again once the skip is re-armed', async () => {
    const { patch, reset } = useOnboardingState()
    patch('v1', { skipped: true })
    reset('v1')
    useObjectivesStore().objectives = [objective('first', 'assign')]
    const wrapper = mountSpotlight()
    await flushPromises()
    expect(document.body.textContent).toContain(arc.assign.challenge)
    wrapper.unmount()
  })

  it('skips, hides the tour, and persists the skip per vault', async () => {
    useObjectivesStore().objectives = [objective('first', 'assign')]
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Skip tour')
    expect(document.body.textContent).not.toContain('Welcome, Overseer')
    expect(localStorage.getItem('onboarding:v1')).toContain('skipped')
    wrapper.unmount()
  })

  it('shows the card without a cut-out when the step anchor is absent', async () => {
    useObjectivesStore().objectives = [objective('first', 'assign')]
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    expect(document.body.textContent).toContain(arc.assign.challenge)
    expect(document.querySelector('.onboarding-cutout')).toBeNull()
    wrapper.unmount()
  })

  it('claims the current step once from the card', async () => {
    const store = useObjectivesStore()
    store.objectives = [objective('first', 'assign', 2)]
    const claim = vi.spyOn(store, 'completeObjective').mockResolvedValue(objective('first', 'assign', 2))
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    await clickButton('Claim 25 caps')
    expect(claim).toHaveBeenCalledTimes(1)
    expect(claim).toHaveBeenCalledWith('v1', 'first')
    wrapper.unmount()
  })
})
