import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { mountWithSetup } from '../../helpers/mountWithSetup'
import AISettingsPanel from '@/modules/ai-settings/components/AISettingsPanel.vue'
import { aiSettingsService } from '@/modules/ai-settings/services/aiSettingsService'
import type { AISettingsRead } from '@/modules/ai-settings/models/aiSettings'

const mockToast = { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() }

vi.mock('@/core/composables/useToast', () => ({ useToast: () => mockToast }))
vi.mock('@/modules/ai-settings/services/aiSettingsService', () => ({
  aiSettingsService: {
    get: vi.fn(),
    update: vi.fn(),
    test: vi.fn(),
  },
}))

const settings = (overrides: Partial<AISettingsRead> = {}): AISettingsRead => ({
  profile: {
    id: 'profile-1',
    provider: 'openai',
    model: 'gpt-4o-mini',
    base_url: null,
    gateway_route: null,
    updated_at: '2026-09-22T00:00:00Z',
  },
  effective: {
    provider: 'openai',
    model: 'gpt-4o-mini',
    base_url: null,
    gateway_route: null,
    mode: 'gateway',
  },
  ...overrides,
})

const findButton = (wrapper: ReturnType<typeof mountWithSetup>, label: string) =>
  wrapper.findAll('button').find((b) => b.text().includes(label))!

describe('AISettingsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(aiSettingsService.get).mockResolvedValue(settings())
    vi.mocked(aiSettingsService.update).mockResolvedValue(settings())
    vi.mocked(aiSettingsService.test).mockResolvedValue({ status: 'ok', latency_ms: 12, model: 'gpt-4o-mini' })
  })

  it('loads settings on mount and populates the form', async () => {
    const wrapper = mountWithSetup(AISettingsPanel)
    await flushPromises()

    expect(aiSettingsService.get).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[role="combobox"]').text()).toContain('OpenAI')
    expect((wrapper.find('input[id="ai-model"]').element as HTMLInputElement).value).toBe('gpt-4o-mini')
    expect(wrapper.text()).toContain('Effective Configuration')
    expect(wrapper.text()).toContain('gateway')
  })

  it('keeps save disabled until a field changes', async () => {
    const wrapper = mountWithSetup(AISettingsPanel)
    await flushPromises()

    const saveButton = findButton(wrapper, 'Save & Apply')
    expect((saveButton.element as HTMLButtonElement).disabled).toBe(true)
    expect(wrapper.text()).toContain('No unsaved changes')

    await wrapper.find('input[id="ai-model"]').setValue('claude-3-haiku')
    expect((saveButton.element as HTMLButtonElement).disabled).toBe(false)
  })

  it('saves only the changed fields through the service', async () => {
    const wrapper = mountWithSetup(AISettingsPanel)
    await flushPromises()

    await wrapper.find('input[id="ai-model"]').setValue('claude-3-haiku')
    await findButton(wrapper, 'Save & Apply').trigger('click')
    await flushPromises()

    expect(aiSettingsService.update).toHaveBeenCalledWith({ model: 'claude-3-haiku' })
    expect(mockToast.success).toHaveBeenCalledWith('AI configuration applied')
  })

  it('tests the connection with the dirty payload and shows the result', async () => {
    const wrapper = mountWithSetup(AISettingsPanel)
    await flushPromises()

    await wrapper.find('input[id="ai-model"]').setValue('claude-3-haiku')
    await findButton(wrapper, 'Test Connection').trigger('click')
    await flushPromises()

    expect(aiSettingsService.test).toHaveBeenCalledWith({ model: 'claude-3-haiku' })
    expect(wrapper.text()).toContain('Connected in 12 ms')
  })

  it('resets to environment defaults after a two-step confirm', async () => {
    const wrapper = mountWithSetup(AISettingsPanel)
    await flushPromises()

    const resetButton = findButton(wrapper, 'Reset to Env Defaults')
    await resetButton.trigger('click')
    expect(resetButton.text()).toContain('Confirm Reset?')

    await resetButton.trigger('click')
    await flushPromises()

    expect(aiSettingsService.update).toHaveBeenCalledWith({
      provider: null,
      model: null,
      base_url: null,
      gateway_route: null,
    })
    expect(mockToast.success).toHaveBeenCalledWith('AI configuration reset to environment defaults')
  })

  it('reveals the base URL field when a local provider is selected', async () => {
    const wrapper = mountWithSetup(AISettingsPanel)
    await flushPromises()

    expect(wrapper.find('input[id="ai-base-url"]').exists()).toBe(false)

    // reka-ui opens the listbox on pointerdown (not click); jsdom's synthetic
    // events carry no button, so dispatch a real MouseEvent.
    wrapper.find('[role="combobox"]').element.dispatchEvent(
      new MouseEvent('pointerdown', { button: 0, bubbles: true })
    )
    await flushPromises()

    const ollamaOption = Array.from(document.body.querySelectorAll('[role="option"]')).find(
      (option) => option.textContent?.includes('Ollama')
    ) as HTMLElement
    // reka-ui selects items on pointerup (not click).
    ollamaOption.dispatchEvent(new MouseEvent('pointerup', { button: 0, bubbles: true }))
    await flushPromises()

    expect(wrapper.find('input[id="ai-base-url"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Required for Ollama / LM Studio')
  })

  it('copies the effective configuration to the clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })

    const wrapper = mountWithSetup(AISettingsPanel)
    await flushPromises()

    const copyButton = findButton(wrapper, 'Copy')
    await copyButton.trigger('click')

    expect(writeText).toHaveBeenCalledWith(
      'Provider: openai\nModel: gpt-4o-mini\nBase URL: —\nGateway Route: —\nMode: gateway'
    )
    expect(copyButton.text()).toContain('Copied')
  })
})
