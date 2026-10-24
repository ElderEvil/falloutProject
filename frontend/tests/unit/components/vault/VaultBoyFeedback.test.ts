import { afterEach, describe, expect, it, vi } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import VaultBoyFeedback from '@/core/components/common/VaultBoyFeedback.vue'
import { useVaultBoyFeedback } from '@/core/composables/useVaultBoyFeedback'
import type { VaultBoyFeedbackEvent } from '@/core/composables/useVaultBoyFeedback'

const success: VaultBoyFeedbackEvent = {
  animation: 'ok',
  title: 'Objective complete',
  message: 'Collected +120 Caps',
  vaultId: 'vault-1',
}

function showResult(result: VaultBoyFeedbackEvent) {
  useVaultBoyFeedback().show(result)
}

function mountFeedback(result: VaultBoyFeedbackEvent | null) {
  useVaultBoyFeedback().clear()
  if (result) showResult(result)
  const wrapper = mount(VaultBoyFeedback, {
    props: { vaultId: 'vault-1' },
    global: { stubs: { Teleport: true, Transition: true } },
  })
  if (wrapper.find('image').exists()) wrapper.get('image').element.dispatchEvent(new Event('load'))
  return wrapper
}

describe('VaultBoyFeedback', () => {
  afterEach(() => {
    useVaultBoyFeedback().clear()
    vi.useRealTimers()
  })

  it('shows a celebration with its message and sprite', () => {
    const wrapper = mountFeedback(success)

    expect(wrapper.text()).toContain('Objective complete')
    expect(wrapper.text()).toContain('Collected +120 Caps')
    expect(wrapper.get('.vault-boy-feedback image').attributes('href')).toContain(
      'VaultBoy_AnimationsOk.webp'
    )

    wrapper.unmount()
  })

  it('shows a warning with its message and sprite', () => {
    const wrapper = mountFeedback({
      ...success,
      animation: 'happiness-low',
      title: 'Happiness is low',
      message: 'Check food, water, and room assignments.',
    })

    expect(wrapper.text()).toContain('Happiness is low')
    expect(wrapper.text()).toContain('Check food, water, and room assignments.')
    expect(wrapper.get('.vault-boy-feedback image').attributes('href')).toContain(
      'VaultBoy_AnimationsHappynessLow.webp'
    )

    wrapper.unmount()
  })

  it.each(['ok', 'baby'] as const)(
    'plays seven distinct poses once and holds the final pose for %s',
    async (animation) => {
      vi.useFakeTimers()
      const wrapper = mountFeedback({ ...success, animation })
      const poses = new Set<string>()
      for (let step = 0; step < 7; step += 1) {
        poses.add(wrapper.get('.vault-boy-feedback > svg > svg').attributes('viewBox')!)
        await vi.advanceTimersByTimeAsync(180)
      }
      expect(poses.size).toBe(7)
      const finalPose = wrapper.get('.vault-boy-feedback > svg > svg').attributes('viewBox')
      await vi.advanceTimersByTimeAsync(1000)
      expect(wrapper.get('.vault-boy-feedback > svg > svg').attributes('viewBox')).toBe(finalPose)
      wrapper.unmount()
    }
  )

  it('hides itself after the feedback window', async () => {
    vi.useFakeTimers()
    const wrapper = mountFeedback(success)
    expect(wrapper.find('.vault-boy-feedback').exists()).toBe(true)

    await vi.advanceTimersByTimeAsync(4300)

    expect(wrapper.find('.vault-boy-feedback').exists()).toBe(false)
    wrapper.unmount()
  })

  it('stays hidden without a result', () => {
    const wrapper = mountFeedback(null)

    expect(wrapper.find('.vault-boy-feedback').exists()).toBe(false)
    wrapper.unmount()
  })

  it('queues consecutive celebrations without dropping the next message', async () => {
    vi.useFakeTimers()
    const wrapper = mountFeedback(success)
    const previousPopup = wrapper.get('.vault-boy-feedback').element
    await vi.advanceTimersByTimeAsync(4000)

    showResult({ ...success, message: 'Collected +140 Caps' })
    await vi.advanceTimersByTimeAsync(300)

    expect(wrapper.get('.vault-boy-feedback').element).not.toBe(previousPopup)
    expect(wrapper.text()).toContain('+140 Caps')
    wrapper.get('image').element.dispatchEvent(new Event('load'))
    await vi.advanceTimersByTimeAsync(300)
    expect(wrapper.find('.vault-boy-feedback').exists()).toBe(true)
    await vi.advanceTimersByTimeAsync(4300)
    expect(wrapper.find('.vault-boy-feedback').exists()).toBe(false)
    wrapper.unmount()
  })
})

it('lets the player dismiss an animation', async () => {
  const wrapper = mountFeedback(success)
  await wrapper.get('button[aria-label="Dismiss animation"]').trigger('click')
  expect(wrapper.find('.vault-boy-feedback').exists()).toBe(false)
  wrapper.unmount()
})

it('clears pending feedback on a vault change', async () => {
  const wrapper = mountFeedback(success)
  showResult(success)
  await wrapper.setProps({ vaultId: 'vault-2' })
  expect(useVaultBoyFeedback().current.value).toBeNull()
  wrapper.unmount()
})

it('waits for the sprite to load before starting its playback and timeout', async () => {
  vi.useFakeTimers()
  useVaultBoyFeedback().clear()
  showResult(success)
  const wrapper = mount(VaultBoyFeedback, {
    props: { vaultId: 'vault-1' },
    global: { stubs: { Teleport: true, Transition: true } },
  })
  const first = wrapper.get('.vault-boy-feedback > svg > svg').attributes('viewBox')
  await vi.advanceTimersByTimeAsync(5000)
  expect(wrapper.get('.vault-boy-feedback > svg > svg').attributes('viewBox')).toBe(first)
  await wrapper.get('image').trigger('load')
  await vi.advanceTimersByTimeAsync(180)
  expect(wrapper.get('.vault-boy-feedback > svg > svg').attributes('viewBox')).not.toBe(first)
  await vi.advanceTimersByTimeAsync(4300)
  expect(wrapper.find('.vault-boy-feedback').exists()).toBe(false)
  wrapper.unmount()
  vi.useRealTimers()
})
