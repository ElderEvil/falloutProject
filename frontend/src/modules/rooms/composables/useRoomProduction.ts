import { computed, type Ref } from 'vue'
import type { Room } from '../models/room'
import type { DwellerShort, SpecialKey } from '@/modules/dwellers/models/dweller'
import { getAbilityConfig } from '@/modules/dwellers/models/dweller'
import { API_BASE_URL } from '@/core/config/api'

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

  const roomImageUrl = computed(() => {
    if (!room.value?.image_url) return null
    const baseUrl = API_BASE_URL
    const normalizedBase = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl
    const imagePath = room.value.image_url.startsWith('/')
      ? room.value.image_url.slice(1)
      : room.value.image_url
    return `${normalizedBase}/${imagePath}`
  })

  const productionInfo = computed(() => {
    if (!room.value || !room.value.ability || room.value.category?.toLowerCase() !== 'production') {
      return null
    }

    const r = room.value
    const dwellers = assignedDwellers.value

    const abilityKey = r.ability!.toLowerCase() as SpecialKey
    const abilitySum = dwellers.reduce((sum, dweller) => {
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
    const efficiency = Math.round((dwellers.length / capacity) * 100)

    return {
      resourceType,
      abilitySum,
      productionPerMinute: productionPerMinute.toFixed(2),
      productionPerSecond: productionPerSecond.toFixed(2),
      efficiency,
      isFullyStaffed: dwellers.length >= capacity,
    }
  })

  return {
    resourceIcon,
    resourceName,
    roomImageUrl,
    productionInfo,
  }
}
