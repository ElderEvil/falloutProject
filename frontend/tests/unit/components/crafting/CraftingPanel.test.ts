import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
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
    stat: 'agility',
    junk_types: ['circuitry', 'steel'],
    junk_materials: { common: 3 },
    available_junk: { common: 5 },
    ability_sum: 0,
    duration_seconds: 3600,
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
    required_stat: 'agility',
    ability_sum_at_start: 0,
    ...overrides,
  }) as CraftingOrder

const mountPanel = () =>
  mount(CraftingPanel, { props: { vaultId: 'vault-1', itemType: 'weapon' } })

// The filter bar's shadcn SelectTrigger is also a <button>, so target the Start
// action by its label rather than by DOM position.
const findButton = (wrapper: VueWrapper, label: string) =>
  wrapper.findAll('button').find((button) => button.text().includes(label))!

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
    expect(wrapper.text()).toContain('5/3 common')
    expect(wrapper.text()).toContain('1h')
  })

  it('flags a material shortfall and explains the recipe', async () => {
    vi.mocked(craftingService.listRecipes).mockResolvedValue([
      recipe({ can_craft: false, junk_materials: { common: 3, rare: 3 }, available_junk: { common: 3, rare: 0 }, missing_junk: 3 }),
    ])
    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.text()).toContain('0/3 rare')
    expect(findButton(wrapper, 'Start').attributes('disabled')).toBeDefined()
  })

  it('filters schematics by rarity, craftability and name', async () => {
    vi.mocked(craftingService.listRecipes).mockResolvedValue([
      recipe({ name: 'Pipe pistol', rarity: 'common', can_craft: true }),
      recipe({ name: 'Baseball bat', rarity: 'rare', can_craft: false, junk_materials: { common: 3, rare: 3 } }),
    ])
    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.text()).toContain('Pipe pistol')
    expect(wrapper.text()).toContain('Baseball bat')

    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    await checkboxes[0].setValue(true)
    expect(wrapper.text()).toContain('Pipe pistol')
    expect(wrapper.text()).not.toContain('Baseball bat')

    await wrapper.find('input[type="search"]').setValue('baseball')
    expect(wrapper.text()).toContain('No schematics match those filters')
  })

  it('shows the stat each schematic keys off, and the crew total in the queue', async () => {
    vi.mocked(craftingService.listRecipes).mockResolvedValue([recipe({ stat: 'perception' })])
    vi.mocked(craftingService.listOrders).mockResolvedValue([
      order({ required_stat: 'agility', ability_sum_at_start: 14 }),
    ])
    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.text()).toContain('PER')
    expect(wrapper.find('[data-icon="mdi:run-fast"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('AGI 14')
  })

  it('disables starting when the recipe cannot be afforded', async () => {
    vi.mocked(craftingService.listRecipes).mockResolvedValue([
      recipe({ can_craft: false, junk_materials: { common: 3, rare: 3 }, available_junk: { common: 3, rare: 0 }, missing_junk: 3 }),
    ])
    const wrapper = mountPanel()
    await flushPromises()

    expect(findButton(wrapper, 'Start').attributes('disabled')).toBeDefined()
  })

  it('queues an order, refreshes and reports it', async () => {
    const wrapper = mountPanel()
    await flushPromises()

    await findButton(wrapper, 'Start').trigger('click')
    await flushPromises()

    expect(craftingService.startOrder).toHaveBeenCalledWith('vault-1', 'Pipe pistol', 'weapon')
    expect(mockToast.success).toHaveBeenCalledWith(expect.stringContaining('Pipe pistol'))
    expect(wrapper.emitted('crafted')).toHaveLength(1)
  })

  it('surfaces a failed start without emitting crafted', async () => {
    vi.mocked(craftingService.startOrder).mockRejectedValue(new Error('Storage is full'))
    const wrapper = mountPanel()
    await flushPromises()

    await findButton(wrapper, 'Start').trigger('click')
    await flushPromises()

    expect(mockToast.error).toHaveBeenCalled()
    expect(wrapper.emitted('crafted')).toBeUndefined()
  })

  it('shows only this workshop type in the queue', async () => {
    vi.mocked(craftingService.listOrders).mockResolvedValue([
      order({ id: 'w-1', item_type: 'weapon', item_name: 'Pipe pistol' }),
      order({ id: 'o-1', item_type: 'outfit', item_name: 'Mechanic jumpsuit' }),
    ])
    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.text()).toContain('Pipe pistol')
    expect(wrapper.text()).not.toContain('Mechanic jumpsuit')
  })

  it('only offers Collect for a finished order', async () => {
    vi.mocked(craftingService.listOrders).mockResolvedValue([order({ status: 'active' })])
    const wrapper = mountPanel()
    await flushPromises()

    expect(wrapper.text()).toContain('Queue')
    expect(wrapper.text()).not.toContain('Collect')
  })

  it('renders the queue progress bar with the live percentage', async () => {
    vi.mocked(craftingService.listOrders).mockResolvedValue([order({ status: 'active', progress: 0.5 })])
    const wrapper = mountPanel()
    await flushPromises()

    const bar = wrapper.find('[role="progressbar"]')
    expect(bar.exists()).toBe(true)
    expect(bar.attributes('aria-valuenow')).toBe('50')
    expect(wrapper.text()).toContain('50%')
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
