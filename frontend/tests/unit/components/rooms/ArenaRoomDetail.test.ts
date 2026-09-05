import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ArenaRoomDetail from '@/modules/rooms/components/ArenaRoomDetail.vue'

describe('ArenaRoomDetail', () => {
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
        isRushing: false,
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
    expect(wrapper.text()).toContain('Management')
    expect(wrapper.text()).toContain('Upgrade to Tier 2')
    expect(wrapper.text()).toContain('Unassign All Dwellers')
    expect(wrapper.text()).toContain('Destroy Room')
  })
})
