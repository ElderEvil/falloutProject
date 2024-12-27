import { z } from 'zod';
import { GRID_DEPTH, GRID_WIDTH } from '@/constants';

export const GridPosition = z.object({
  x: z.number().min(0).max(GRID_WIDTH),
  y: z.number().min(0).max(GRID_DEPTH)
});

export const RoomCellStatusEnum = z.enum(['empty', 'digging', 'ready', 'constructing', 'occupied']);

export const RoomCellSchema = z.object({
  status: RoomCellStatusEnum,
  roomId: z.string().uuid().nullable(),
  progress: z.number().min(0).max(100).optional()
});

export const RoomGridSchema = z.array(z.array(RoomCellSchema));
