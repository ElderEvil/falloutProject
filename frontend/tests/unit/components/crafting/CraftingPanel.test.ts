import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import CraftingPanel from '@/modules/crafting/components/CraftingPanel.vue'
import { craftingService } from '@/modules/crafting/services/craftingService'
import type { CraftingRecipe } from '@/modules/crafting/models/crafting'

const mockToast = { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() }

vi.mock('@/core/composables/useToast', () => ({ useToast: () => mockToast }))
vi.mock('@/modules/crafting/services/craftingService', () => ({
  craftingService: { listRecipes: vi.fn(), craft: vi.fn() },
}))
vi.mock('@iconify/vue', () => ({
  Icon: { name: 'Icon', props: ['icon'], template: '<i class="icon" :data-icon="icon" />' },
}))

const recipe = (overrides: Partial<CraftingRecipe> = {}): CraftingRecipe =>
  ({
    name: 'Pipe pistol',
    item_type: 'weapon',
    rarity: 'common',
    value: 20,
    junk_cost: 3,
    caps_cost: 0,
    can_craft: true,
    missing_junk: 0,
    ...overrides,
  }) as CraftingRecipe

const mountPanel = () =>
  mount(CraftingPanel, { props: { vaultId: 'vault-1', itemType: 'weapon' } })

describe('CraftingPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(craftingService.listRecipes).mockResolvedValue([recipe()])
    vi.mocked(craftingService.craft).mockResolvedValue({
      item_type: 'weapon',
      item_id: 'item-1',
      name: 'Pipe pistol',
      rarity: 'common',
      junk_spent: 3,
      caps_spent: 0,
    })
  })

  it('loads and renders recipes for the workshop', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    expect(craftingService.listRecipes).toHaveBeenCalledWith('vault-1', 'weapon')
    expect(wrapper.text()).toContain('Pipe pistol')
    expect(wrapper.text()).toContain('3 junk')
  })

  it('disables crafting and shows the shortfall when materials are missing', async () => {
    vi.mocked(craftingService.listRecipes).mockResolvedValue([
      recipe({ can_craft: false, junk_cost: 6, missing_junk: 4 }),
    ])
    const wrapper = mountPanel()
    await flushPromises()

    const button = wrapper.get('button')
    expect(button.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('missing 4 scrap')
  })

  it('crafts the item, refreshes the list and reports the result', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(craftingService.craft).toHaveBeenCalledWith('vault-1', 'Pipe pistol', 'weapon')
    expect(mockToast.success).toHaveBeenCalledWith(expect.stringContaining('Pipe pistol'))
    expect(craftingService.listRecipes).toHaveBeenCalledTimes(2)
    expect(wrapper.emitted('crafted')).toHaveLength(1)
  })

  it('surfaces a craft failure without emitting crafted', async () => {
    vi.mocked(craftingService.craft).mockRejectedValue(new Error('Storage is full'))
    const wrapper = mountPanel()
    await flushPromises()

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(mockToast.error).toHaveBeenCalled()
    expect(wrapper.emitted('crafted')).toBeUndefined()
  })

  it('shows the empty state when nothing is craftable', async () => {
    vi.mocked(craftingService.listRecipes).mockResolvedValue([])
    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.text()).toContain('No craftable weapons are catalogued')
  })
})
