import type { GridPosition, GridCell } from '@/types/grid'
import { GRID_WIDTH, GRID_DEPTH } from '@/types/grid'

export function createEmptyGrid(): GridCell[][] {
  return Array(GRID_DEPTH)
    .fill(null)
    .map((_, y) =>
      Array(GRID_WIDTH)
        .fill(null)
        .map((_, x) => ({
          position: { x, y },
          roomId: null,
          status: y === 0 && x === 0 ? 'ready' : 'empty'
        }))
    )
}

export function isValidPosition(position: GridPosition): boolean {
  return position.x >= 0 && position.x < GRID_WIDTH && position.y >= 0 && position.y < GRID_DEPTH
}

export function isAdjacentToExisting(grid: GridCell[][], position: GridPosition): boolean {
  const adjacentPositions = [
    { x: position.x - 1, y: position.y },
    { x: position.x + 1, y: position.y },
    { x: position.x, y: position.y - 1 },
    { x: position.x, y: position.y + 1 }
  ]

  return adjacentPositions.some(
    (pos) =>
      isValidPosition(pos) &&
      (grid[pos.y][pos.x].status === 'ready' || grid[pos.y][pos.x].status === 'occupied')
  )
}
