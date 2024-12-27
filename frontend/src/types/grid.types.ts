import z from 'zod';
import { GridPosition } from '@/validators/grid.validators';

export type GridPosition = z.infer<typeof GridPosition>;

export interface GridCell {
  coordinate_x: number;
  coordinate_y: number;
  roomId: number | null;
  status: string;
  progress?: number;
}

export function getDigTime(y: number): number {
  return (y + 1) * 1000;
}
