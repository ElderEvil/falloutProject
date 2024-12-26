import { z } from 'zod'
import {
  VaultCreateSchema,
  VaultResourceUpdateSchema,
  VaultSchema
} from '@/validators/vaults.validator'
import type { Room } from '@/types/room.types'
import type { DwellerFull, DwellerShort } from '@/types/dweller.types'
import type { GridCell } from '@/types/grid.types'

type Vault = z.infer<typeof VaultSchema> & { rooms: Room[] } & {
  dwellers: DwellerShort[] | (DwellerFull[] & GridCell)
}
type VaultCreate = z.infer<typeof VaultCreateSchema>
type VaultResourceUpdate = z.infer<typeof VaultResourceUpdateSchema>

export { type Vault, type VaultCreate, type VaultResourceUpdate }
