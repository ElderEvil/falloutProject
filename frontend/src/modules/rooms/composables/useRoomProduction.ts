import { computed, type Ref } from 'vue'
import type { Room } from '../models/room'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'

type SpecialKey =
  | 'strength'
  | 'perception'
  | 'endurance'
  | 'charisma'
  | 'intelligence'
  | 'agility'
  | 'luck'

const getResourceName = (ability?: string | null) => {
  if (!ability) return 'Resources'
  switch (ability.toUpperCase()) {
    case 'STRENGTH':
      return 'Power'
    case 'PERCEPTION':
      return 'Water'
    case 'AGILITY':
      return 'Food'
    case 'ENDURANCE':
      return 'All Resources'
    default:
      return 'Resources'
  }
}

export function useRoomProduction(
  room: Ref<Room | null>,
  assignedDwellers: Ref<DwellerShort[]>,
  dwellerCapacity: Ref<number>
) {
  const resourceIcon = computed(() => {
    if (!room.value?.ability) return 'mdi:home'
    const ability = room.value.ability.toUpperCase()
    switch (ability) {
      case 'STRENGTH':
        return 'mdi:lightning-bolt'
      case 'PERCEPTION':
        return 'mdi:water'
      case 'AGILITY':
        return 'mdi:food-drumstick'
      case 'ENDURANCE':
        return 'mdi:flash'
      default:
        return 'mdi:home'
    }
  })

  const resourceName = computed(() => {
    return getResourceName(room.value?.ability)
  })

  const roomImageUrl = computed(() => {
    if (!room.value?.image_url) return null
    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
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

    const resourceType = getResourceName(r.ability)

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
