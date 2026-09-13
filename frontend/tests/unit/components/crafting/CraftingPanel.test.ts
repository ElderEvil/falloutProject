import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import CraftingPanel from '@/modules/crafting/components/CraftingPanel.vue'
import { craftingService } from '@/modules/crafting/services/craftingService'
import type { CraftingOrder, CraftingRecipe } from '@/modules/crafting/models/crafting'

const mockToast = { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() }

vi.mock('@/core/composables/useToast', () => ({ useToast: () => mockToast }))
vi.mock('@/modules/crafting/services/craftingService', () => ({
  craftingService: {
    listRecipes: vi.fn(),
    listOrders: vi.fn(),
    startOrder: vi.fn(),
    collectOrder: vi.fn(),
  },
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

const order = (overrides: Partial<CraftingOrder> = {}): CraftingOrder =>
  ({
    id: 'order-1',
    room_id: 'room-1',
    item_name: 'Pipe pistol',
    item_type: 'weapon',
    rarity: 'common',
    status: 'active',
    progress: 0,
    started_at: new Date(Date.now() - 10_000).toISOString(),
    estimated_completion_at: new Date(Date.now() + 60_000).toISOString(),
    completed_at: null,
    junk_spent: 3,
    caps_spent: 0,
    workers_at_start: 0,
    ...overrides,
  }) as CraftingOrder

const mountPanel = () =>
  mount(CraftingPanel, { props: { vaultId: 'vault-1', itemType: 'weapon' } })

describe('CraftingPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(craftingService.listRecipes).mockResolvedValue([recipe()])
    vi.mocked(craftingService.listOrders).mockResolvedValue([])
    vi.mocked(craftingService.startOrder).mockResolvedValue(order())
    vi.mocked(craftingService.collectOrder).mockResolvedValue({
      item_type: 'weapon',
      item_id: 'item-1',
      name: 'Pipe pistol',
      rarity: 'common',
      junk_spent: 3,
      caps_spent: 0,
    })
  })

  it('loads recipes for the workshop', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    expect(craftingService.listRecipes).toHaveBeenCalledWith('vault-1', 'weapon')
    expect(wrapper.text()).toContain('Pipe pistol')
    expect(wrapper.text()).toContain('3 junk')
  })

  it('disables starting and shows the shortfall when materials are missing', async () => {
    vi.mocked(craftingService.listRecipes).mockResolvedValue([
      recipe({ can_craft: false, junk_cost: 6, missing_junk: 4 }),
    ])
    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('missing 4 scrap')
  })

  it('queues an order, refreshes and reports it', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(craftingService.startOrder).toHaveBeenCalledWith('vault-1', 'Pipe pistol', 'weapon')
    expect(mockToast.success).toHaveBeenCalledWith(expect.stringContaining('Pipe pistol'))
    expect(wrapper.emitted('crafted')).toHaveLength(1)
  })

  it('surfaces a failed start without emitting crafted', async () => {
    vi.mocked(craftingService.startOrder).mockRejectedValue(new Error('Storage is full'))
    const wrapper = mountPanel()
    await flushPromises()

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(mockToast.error).toHaveBeenCalled()
    expect(wrapper.emitted('crafted')).toBeUndefined()
  })

  it('only offers Collect for a finished order', async () => {
    vi.mocked(craftingService.listOrders).mockResolvedValue([order({ status: 'active' })])
    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.text()).toContain('Queue')
    expect(wrapper.text()).not.toContain('Collect')
  })

  it('collects a finished order', async () => {
    vi.mocked(craftingService.listOrders).mockResolvedValue([order({ status: 'completed', progress: 1 })])
    const wrapper = mountPanel()
    await flushPromises()

    const collect = wrapper.findAll('button').find(button => button.text().includes('Collect'))
    expect(collect?.exists()).toBe(true)
    await collect!.trigger('click')
    await flushPromises()

    expect(craftingService.collectOrder).toHaveBeenCalledWith('vault-1', 'order-1')
    expect(wrapper.emitted('crafted')).toHaveLength(1)
  })

  it('shows the empty state when nothing is craftable', async () => {
    vi.mocked(craftingService.listRecipes).mockResolvedValue([])
    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.text()).toContain('No craftable weapons are catalogued')
  })

  it('ignores a stale response when the workshop changes mid-flight', async () => {
    let resolveFirst: (value: CraftingRecipe[]) => void = () => {}
    vi.mocked(craftingService.listRecipes)
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve }))
      .mockImplementationOnce(async () => [recipe({ name: 'Assault rifle' })])

    const wrapper = mountPanel()
    await wrapper.setProps({ itemType: 'outfit' })
    await flushPromises()

    resolveFirst([recipe({ name: 'Pipe pistol' })])
    await flushPromises()

    expect(wrapper.text()).toContain('Assault rifle')
    expect(wrapper.text()).not.toContain('Pipe pistol')
  })
})
