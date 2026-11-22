import { api } from '@/core/utils/api'
import type { components } from '@/core/types/api.generated'

export type DwellerCollectible = components['schemas']['DwellerCollectibleRead']

export function getDwellerCollectibles(dwellerId: string): Promise<DwellerCollectible[]> {
  return api.get<DwellerCollectible[]>(`/api/v1/dwellers/${dwellerId}/collectibles`)
}
