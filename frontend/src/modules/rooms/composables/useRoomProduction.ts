import { computed, type Ref } from 'vue'
import type { Room } from '../models/room'
import type { DwellerShort, SpecialKey } from '@/modules/dwellers/models/dweller'
import { getAbilityConfig } from '@/modules/dwellers/models/dweller'
import { getRoomImageUrl } from '@/core/utils/image'

export function useRoomProduction(
  room: Ref<Room | null>,
  assignedDwellers: Ref<DwellerShort[]>,
  dwellerCapacity: Ref<number>
) {
  const resourceIcon = computed(() => {
    return getAbilityConfig(room.value?.ability)?.icon ?? 'mdi:home'
  })

  const resourceName = computed(() => {
    return getAbilityConfig(room.value?.ability)?.resourceName ?? 'Resources'
  })

  const roomImageUrl = computed(() => getRoomImageUrl(room.value?.image_url))

  const productionInfo = computed(() => {
    if (!room.value || !room.value.ability || room.value.category?.toLowerCase() !== 'production') {
      return null
    }

    const r = room.value
    const workers = assignedDwellers.value.filter((dweller) => !dweller.apprentice_stat)

    const abilityKey = r.ability!.toLowerCase() as SpecialKey
    const abilitySum = workers.reduce((sum, dweller) => {
      const value = dweller[abilityKey]
      return sum + (typeof value === 'number' ? value : 0)
    }, 0)

    const BASE_PRODUCTION_RATE = 0.1
    const TIER_MULTIPLIER: Record<number, number> = { 1: 1.0, 2: 1.5, 3: 2.0 }
    const tierMult = TIER_MULTIPLIER[r.tier] || 1.0
    const productionPerSecond = (r.output || 0) * abilitySum * BASE_PRODUCTION_RATE * tierMult
    const productionPerMinute = productionPerSecond * 60

    const resourceType = getAbilityConfig(r.ability)?.resourceName ?? 'Resources'

    const capacity = dwellerCapacity.value || 1
    const efficiency = Math.round((workers.length / capacity) * 100)

    return {
      resourceType,
      abilitySum,
      productionPerMinute: productionPerMinute.toFixed(2),
      productionPerSecond: productionPerSecond.toFixed(2),
      efficiency,
      isFullyStaffed: workers.length >= capacity,
    }
  })

  return {
    resourceIcon,
    resourceName,
    roomImageUrl,
    productionInfo,
  }
}
