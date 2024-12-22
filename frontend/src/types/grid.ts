export interface GridPosition {
  x: number
  y: number
}

export interface GridCell {
  position: GridPosition
  roomId: number | null
  status: 'empty' | 'digging' | 'ready' | 'occupied' | 'constructing'
  progress?: number
}

export const GRID_WIDTH = 4
export const GRID_DEPTH = 12

export function getDigTime(y: number): number {
  return (y + 1) * 1000
}

export const CONSTRUCTION_TIME = 3000
