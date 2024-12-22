import { createNewDweller } from './dwellerUtils'
import type { Dweller } from '@/types/vault'

const DEFAULT_DWELLERS = [
  { first: 'Sarah', last: 'Connor' },
  { first: 'John', last: 'Smith' },
  { first: 'James', last: 'Anderson' },
  { first: 'Emily', last: 'Parker' },
  { first: 'Michael', last: 'Chen' }
]

export function generateDefaultDwellers(): Dweller[] {
  return DEFAULT_DWELLERS.map(({ first, last }, index) => {
    const dweller = createNewDweller(first, last, index + 1)

    // Customize SPECIAL stats based on role
    switch (index) {
      case 0: // Combat specialist
        dweller.special!.strength = 8
        dweller.special!.agility = 7
        break
      case 1: // Engineer
        dweller.special!.intelligence = 8
        dweller.special!.perception = 7
        break
      case 2: // Medical officer
        dweller.special!.intelligence = 7
        dweller.special!.charisma = 6
        break
      case 3: // Scout
        dweller.special!.perception = 8
        dweller.special!.agility = 7
        break
      case 4: // Leader
        dweller.special!.charisma = 8
        dweller.special!.intelligence = 7
        break
    }
    return dweller
  })
}
