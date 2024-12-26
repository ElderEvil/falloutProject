import { z } from 'zod'

export const RoomCellStatusEnum = z.enum(['empty', 'digging', 'ready', 'constructing', 'occupied'])

export const RoomCellSchema = z.object({
  status: RoomCellStatusEnum,
  roomId: z.string().uuid().nullable(),
  progress: z.number().min(0).max(100).optional()
})

export const RoomGridSchema = z.array(z.array(RoomCellSchema))
