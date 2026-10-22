import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useArenaStore } from '@/modules/rooms/stores/arena'
import { mount, flushPromises } from '@vue/test-utils'
import ArenaRoomDetail from '@/modules/rooms/components/ArenaRoomDetail.vue'

vi.mock('@/modules/rooms/composables/useArenaRoom', async () => {
  const { computed, ref } = await import('vue')
  const { useArenaStore } = await import('@/modules/rooms/stores/arena')
  return {
    useArenaRoom: (_vaultId: string, roomId: string) => ({
      roomState: computed(() => useArenaStore().getRoom(roomId)),
      isLoading: ref(false),
      loadFailed: ref(false),
      pendingSkills: ref(new Set<string>()),
      damageNumbers: ref([]),
      attackingTeam: ref(null),
      attackingFighterId: ref(null),
      skillBurst: ref(null),
      load: () => Promise.resolve(),
      retry: () => Promise.resolve(),
      refresh: () => Promise.resolve(),
      queueSkill: () => Promise.resolve(),
      startFight: () => Promise.resolve(true),
      stopFight: () => Promise.resolve(true),
      resetDamageTracking: () => {},
    }),
  }
})

describe('ArenaRoomDetail', () => {
  beforeEach(() => setActivePinia(createPinia()))
  it.each([
    [0, false],
    [6, false],
    [2, true],
  ])('guards assignment with %i dwellers and fighting=%s', (count, fighting) => {
    useArenaStore().rooms.set('arena-1', {
      fight_started: fighting,
      match_done: false,
      team_a: [],
      team_b: [],
    } as never)
    const wrapper = mount(ArenaRoomDetail, {
      props: {
        room: { id: 'arena-1', name: 'Arena', tier: 1, category: 'ARENA', ability: null } as never,
        vaultId: 'vault-1',
        assignedDwellers: Array.from({ length: count }, (_, i) => ({
          id: `dweller-${i}`,
        })) as never,
        dwellerCapacity: 6,
        roomImageUrl: null,
        upgradeInfo: null,
        isUpgrading: false,
        isDestroying: false,
        isVaultDoor: false,
      },
      global: { stubs: { ArenaModal: true, ArenaPreview: true } },
    })
    const assign = wrapper
      .findAll('button')
      .find((button) => button.text().includes('Assign Dwellers'))
    expect(Boolean(assign)).toBe(!fighting && count < 6)
    expect(
      wrapper.findAll('button').some((button) => button.text().includes('Stop Fight'))
    ).toBe(fighting)
    expect(wrapper.text()).not.toMatch(/\d+ \/ \d+ assigned/)
    expect(wrapper.find('[aria-label="Arena preview"]').exists()).toBe(false)
  })

  it('locks management until match state is known and while a match is running', async () => {
    const arenaStore = useArenaStore()
    const wrapper = mount(ArenaRoomDetail, {
      props: {
        room: { id: 'arena-1', name: 'Arena', tier: 1, category: 'ARENA', ability: null } as never,
        vaultId: 'vault-1',
        assignedDwellers: [{ id: 'dweller-1' }] as never,
        dwellerCapacity: 4,
        roomImageUrl: null,
        upgradeInfo: { canUpgrade: true, upgradeCost: 500, nextTier: 2, maxTier: 3 },
        isUpgrading: false,
        isDestroying: false,
        isVaultDoor: false,
      },
      global: { stubs: { ArenaModal: true, ArenaPreview: true } },
    })
    const buttons = () => wrapper.findAll('.room-management button')
    expect(buttons()).toHaveLength(3)
    expect(buttons().every((button) => button.attributes('disabled') !== undefined)).toBe(true)
    expect(
      wrapper.findAll('button').some((button) => button.text().includes('Assign Dwellers'))
    ).toBe(false)
    expect(wrapper.text()).toContain('Room management is unavailable until match state loads.')

    arenaStore.rooms.set('arena-1', {
      fight_started: false,
      match_done: false,
      team_a: [],
      team_b: [],
    } as never)
    await flushPromises()
    expect(buttons().every((button) => button.attributes('disabled') === undefined)).toBe(true)
    expect(
      wrapper.findAll('button').some((button) => button.text().includes('Assign Dwellers'))
    ).toBe(true)

    arenaStore.rooms.set('arena-1', {
      fight_started: true,
      match_done: false,
      team_a: [],
      team_b: [],
    } as never)
    await flushPromises()
    expect(
      wrapper.findAll('button').some((button) => button.text().includes('Assign Dwellers'))
    ).toBe(false)
    for (const button of buttons()) {
      expect(button.attributes('disabled')).toBeDefined()
      await button.trigger('click')
    }
    expect(wrapper.emitted('upgrade')).toBeUndefined()
    expect(wrapper.emitted('unassignAll')).toBeUndefined()
    expect(wrapper.emitted('destroy')).toBeUndefined()

    arenaStore.rooms.set('arena-1', {
      fight_started: true,
      match_done: true,
      team_a: [],
      team_b: [],
    } as never)
    await flushPromises()
    expect(buttons().every((button) => button.attributes('disabled') === undefined)).toBe(true)
    for (const button of buttons()) await button.trigger('click')
    expect(wrapper.emitted('upgrade')).toHaveLength(1)
    expect(wrapper.emitted('unassignAll')).toHaveLength(1)
    expect(wrapper.emitted('destroy')).toHaveLength(1)
  })

  it('uses the shared room-management section below the battle panel', () => {
    const wrapper = mount(ArenaRoomDetail, {
      props: {
        room: {
          id: 'arena-1',
          name: 'Arena',
          tier: 1,
          category: 'ARENA',
          ability: null,
          t2_upgrade_cost: 500,
          t3_upgrade_cost: 1000,
        } as never,
        vaultId: 'vault-1',
        assignedDwellers: [{ id: 'dweller-1' }] as never,
        dwellerCapacity: 6,
        roomImageUrl: null,
        upgradeInfo: { canUpgrade: true, upgradeCost: 500, nextTier: 2, maxTier: 3 },
        isUpgrading: false,
        isDestroying: false,
        isVaultDoor: false,
      },
      global: {
        stubs: {
          ArenaModal: { template: '<div class="battle-panel">Battle UI</div>' },
          ArenaPreview: { template: '<div class="preview-panel" />' },
        },
      },
    })

    expect(wrapper.get('.arena-room-detail').element.firstElementChild).toBe(
      wrapper.get('.preview-panel').element
    )
    expect(wrapper.text()).not.toMatch(/[12] ·/)
    expect(wrapper.text()).toContain('Battle UI')
    expect(wrapper.find('.room-management').text()).toContain('Management')
    expect(wrapper.text()).toContain('Upgrade to Tier 2')
    expect(wrapper.text()).toContain('Unassign All Dwellers')
    expect(wrapper.text()).toContain('Destroy Room')
  })
})
