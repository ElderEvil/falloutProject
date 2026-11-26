import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
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
  jev: {
    enabled: true,
    configured: true,
    model: 'jev-latest',
    timeout_seconds: 2,
  },
  ...overrides,
})

/** A workspace saved on a local provider; `model`/`base_url` are the persisted columns. */
const localSettings = (
  model: string | null = 'google/gemma-4-e4b',
  baseUrl: string | null = null
) =>
  settings({
    profile: {
      id: 'profile-1',
      provider: 'lmstudio',
      model,
      base_url: baseUrl,
      gateway_route: null,
      updated_at: '2026-09-22T00:00:00Z',
    },
  })

/** Mounts the panel and lets its initial settings load settle. */
async function render() {
  const wrapper = mountWithSetup(AISettingsPanel)
  await flushPromises()
  return wrapper
}

const baseUrlValue = (wrapper: ReturnType<typeof mountWithSetup>) =>
  (wrapper.find('input[id="ai-base-url"]').element as HTMLInputElement).value

const findButton = (wrapper: ReturnType<typeof mountWithSetup>, label: string) =>
  wrapper.findAll('button').find((b) => b.text().includes(label))!

async function selectProvider(wrapper: ReturnType<typeof mountWithSetup>, label: string) {
  // reka-ui opens the listbox on pointerdown and selects on pointerup (not click);
  // jsdom's synthetic events carry no button, so dispatch real MouseEvents.
  wrapper
    .find('[role="combobox"]')
    .element.dispatchEvent(new MouseEvent('pointerdown', { button: 0, bubbles: true }))
  await flushPromises()
  const option = Array.from(document.body.querySelectorAll('[role="option"]')).find((o) =>
    o.textContent?.includes(label)
  ) as HTMLElement
  option.dispatchEvent(new MouseEvent('pointerup', { button: 0, bubbles: true }))
  await flushPromises()
}

describe('AISettingsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(aiSettingsService.get).mockResolvedValue(settings())
    vi.mocked(aiSettingsService.update).mockResolvedValue(settings())
    vi.mocked(aiSettingsService.test).mockResolvedValue({
      status: 'ok',
      latency_ms: 12,
      model: 'gpt-4o-mini',
    })
  })

  it('loads settings on mount and populates the form', async () => {
    const wrapper = await render()

    expect(aiSettingsService.get).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[role="combobox"]').text()).toContain('OpenAI')
    expect((wrapper.find('input[id="ai-model"]').element as HTMLInputElement).value).toBe(
      'gpt-4o-mini'
    )
    expect(wrapper.text()).toContain('Effective configuration')
    expect(wrapper.text()).toContain('gateway')
  })

  it('reloads a local provider without marking the prefilled base URL as an override', async () => {
    vi.mocked(aiSettingsService.get).mockResolvedValue(localSettings())
    const wrapper = await render()

    const saveButton = findButton(wrapper, 'Save & Apply')
    expect((saveButton.element as HTMLButtonElement).disabled).toBe(true)
    expect(wrapper.text()).toContain('No unsaved changes')
  })

  it('marks the base URL dirty only after an explicit edit', async () => {
    vi.mocked(aiSettingsService.get).mockResolvedValue(localSettings())
    const wrapper = await render()

    await wrapper.find('input[id="ai-base-url"]').setValue('http://localhost:9999/v1')
    await flushPromises()

    await findButton(wrapper, 'Save & Apply').trigger('click')
    await flushPromises()

    expect(aiSettingsService.update).toHaveBeenCalledWith({ base_url: 'http://localhost:9999/v1' })
  })

  it('shows the Jev decision model status', async () => {
    const wrapper = await render()

    expect(wrapper.text()).toContain('Jev decision model')
    expect(wrapper.text()).toContain('jev-latest')
    expect(wrapper.text()).toContain('Enabled')
    expect(wrapper.text()).toContain('configured')
  })

  it('does not mark Base URL required when the model field is empty', async () => {
    vi.mocked(aiSettingsService.get).mockResolvedValue(localSettings(null))
    const wrapper = await render()

    expect(wrapper.text()).toContain('Not configured')
    expect(wrapper.text()).not.toContain('Required for Ollama / LM Studio')
  })

  it('keeps save disabled until a field changes', async () => {
    const wrapper = await render()

    const saveButton = findButton(wrapper, 'Save & Apply')
    expect((saveButton.element as HTMLButtonElement).disabled).toBe(true)
    expect(wrapper.text()).toContain('No unsaved changes')

    await wrapper.find('input[id="ai-model"]').setValue('claude-3-haiku')
    expect((saveButton.element as HTMLButtonElement).disabled).toBe(false)
  })

  it('saves only the changed fields through the service', async () => {
    const wrapper = await render()

    await wrapper.find('input[id="ai-model"]').setValue('claude-3-haiku')
    await findButton(wrapper, 'Save & Apply').trigger('click')
    await flushPromises()

    expect(aiSettingsService.update).toHaveBeenCalledWith({ model: 'claude-3-haiku' })
    expect(mockToast.success).toHaveBeenCalledWith('AI configuration applied')
  })

  it('tests the connection with the dirty payload and shows the result', async () => {
    const wrapper = await render()

    await wrapper.find('input[id="ai-model"]').setValue('claude-3-haiku')
    await findButton(wrapper, 'Test Connection').trigger('click')
    await flushPromises()

    expect(aiSettingsService.test).toHaveBeenCalledWith({ model: 'claude-3-haiku' })
    expect(wrapper.text()).toContain('Connected in 12 ms')
  })

  it('resets to environment defaults after a two-step confirm', async () => {
    const wrapper = await render()

    const resetButton = findButton(wrapper, 'Reset to Defaults')
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
    const wrapper = await render()

    expect(wrapper.find('input[id="ai-base-url"]').exists()).toBe(false)

    // reka-ui opens the listbox on pointerdown (not click); jsdom's synthetic
    // events carry no button, so dispatch a real MouseEvent.
    wrapper
      .find('[role="combobox"]')
      .element.dispatchEvent(new MouseEvent('pointerdown', { button: 0, bubbles: true }))
    await flushPromises()

    const ollamaOption = Array.from(document.body.querySelectorAll('[role="option"]')).find(
      (option) => option.textContent?.includes('Ollama')
    ) as HTMLElement
    // reka-ui selects items on pointerup (not click).
    ollamaOption.dispatchEvent(new MouseEvent('pointerup', { button: 0, bubbles: true }))
    await flushPromises()

    expect(wrapper.find('input[id="ai-base-url"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Required for Ollama / LM Studio')
    expect(baseUrlValue(wrapper)).toBe('http://localhost:11434/v1')
  })

  it('updates the base URL port when switching between local providers', async () => {
    const wrapper = await render()

    await selectProvider(wrapper, 'LM Studio')
    expect(baseUrlValue(wrapper)).toBe('http://localhost:1234/v1')

    await selectProvider(wrapper, 'Ollama')
    expect(baseUrlValue(wrapper)).toBe('http://localhost:11434/v1')
  })

  it('updates the base URL port when loaded already on a local provider', async () => {
    vi.mocked(aiSettingsService.get).mockResolvedValue(localSettings())
    const wrapper = await render()

    expect(baseUrlValue(wrapper)).toBe('http://localhost:1234/v1')

    await selectProvider(wrapper, 'Ollama')
    expect(baseUrlValue(wrapper)).toBe('http://localhost:11434/v1')
  })

  it('clears the base URL when switching from a local provider to a cloud one', async () => {
    const wrapper = await render()

    await selectProvider(wrapper, 'Ollama')
    expect(baseUrlValue(wrapper)).toBe('http://localhost:11434/v1')

    await selectProvider(wrapper, 'OpenAI')
    expect(wrapper.find('input[id="ai-base-url"]').exists()).toBe(false)
  })

  it('does not flag Base URL red until a local-provider submit is attempted', async () => {
    vi.mocked(aiSettingsService.get).mockResolvedValue(localSettings())
    const wrapper = await render()

    expect(wrapper.find('.border-danger\\/50').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('(Required)')

    await wrapper.find('input[id="ai-base-url"]').setValue('')
    await findButton(wrapper, 'Test Connection').trigger('click')
    await flushPromises()

    expect(aiSettingsService.test).not.toHaveBeenCalled()
    expect(wrapper.find('.border-danger\\/50').exists()).toBe(true)
  })

  it('copies the effective configuration to the clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })

    const wrapper = await render()

    const copyButton = findButton(wrapper, 'Copy')
    await copyButton.trigger('click')

    expect(writeText).toHaveBeenCalledWith(
      'Provider: openai\nModel: gpt-4o-mini\nBase URL: —\nGateway Route: —\nMode: gateway\nJev: enabled (jev-latest)'
    )
    expect(copyButton.text()).toContain('Copied')
  })
})
