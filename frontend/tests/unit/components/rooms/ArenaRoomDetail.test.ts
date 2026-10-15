import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useArenaStore } from '@/modules/rooms/stores/arena'
import { mount } from '@vue/test-utils'
import ArenaRoomDetail from '@/modules/rooms/components/ArenaRoomDetail.vue'

describe('ArenaRoomDetail', () => {
  beforeEach(() => setActivePinia(createPinia()))
  it.each([
    [0, false, false],
    [6, false, true],
    [2, true, true],
  ])('guards assignment with %i dwellers and fighting=%s', (count, fighting, disabled) => {
    useArenaStore().rooms.set('arena-1', { fight_started: fighting, match_done: false } as never)
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
      global: { stubs: { ArenaModal: true, RoomPreviewSection: true } },
    })
    const assign = wrapper.findAll('button').find((button) => button.text() === 'Assign dwellers')!
    expect(assign.attributes('disabled') !== undefined).toBe(disabled)
    expect(wrapper.getComponent({ name: 'RoomPreviewSection' }).props('assignEnabled')).toBe(
      !fighting
    )
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
          RoomPreviewSection: { template: '<div />' },
        },
      },
    })

    expect(wrapper.text()).toContain('Battle UI')
    expect(wrapper.find('.room-management').text()).toContain('Management')
    expect(wrapper.text()).toContain('Upgrade to Tier 2')
    expect(wrapper.text()).toContain('Unassign All Dwellers')
    expect(wrapper.text()).toContain('Destroy Room')
  })
})
