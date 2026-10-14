import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { reactive, ref } from 'vue'
import OnboardingSpotlight from '@/modules/progression/components/OnboardingSpotlight.vue'
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

const objective = (id: string, sequence: number, progress = 0): Objective => ({
  id,
  vault_id: 'v1',
  challenge: `Step ${sequence}`,
  description: 'Do the thing.',
  progress,
  total: 2,
  reward: '25 caps',
  is_completed: false,
  category: 'starter',
  sequence,
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
})

describe('OnboardingSpotlight', () => {
  it('shows the welcome card first for a new vault', async () => {
    useObjectivesStore().objectives = [objective('first', 0)]
    const wrapper = mountSpotlight()
    await flushPromises()
    expect(document.body.textContent).toContain('Welcome, Overseer')
    wrapper.unmount()
  })

  it('starts the tour on the lowest unclaimed starter step', async () => {
    useObjectivesStore().objectives = [objective('second', 1), objective('first', 0)]
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    expect(document.body.textContent).toContain('Step 0')
    expect(document.body.textContent).not.toContain('Step 1')
    wrapper.unmount()
  })

  it('skips, hides the tour, and persists the skip per vault', async () => {
    useObjectivesStore().objectives = [objective('first', 0)]
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Skip tour')
    expect(document.body.textContent).not.toContain('Welcome, Overseer')
    expect(localStorage.getItem('onboarding:v1')).toContain('skipped')
    wrapper.unmount()
  })

  it('shows the card without a cut-out when the step anchor is absent', async () => {
    useObjectivesStore().objectives = [objective('first', 0)]
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    expect(document.body.textContent).toContain('Step 0')
    expect(document.querySelector('.onboarding-cutout')).toBeNull()
    wrapper.unmount()
  })

  it('claims the current step once from the card', async () => {
    const store = useObjectivesStore()
    store.objectives = [objective('first', 0, 2)]
    const claim = vi.spyOn(store, 'completeObjective').mockResolvedValue(objective('first', 0, 2))
    const wrapper = mountSpotlight()
    await flushPromises()
    await clickButton('Start')
    await clickButton('Claim 25 caps')
    expect(claim).toHaveBeenCalledTimes(1)
    expect(claim).toHaveBeenCalledWith('v1', 'first')
    wrapper.unmount()
  })
})
