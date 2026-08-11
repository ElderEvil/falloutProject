export interface DeathStatistics {
  total_dwellers_born: number
  total_dwellers_died: number
  deaths_by_cause: {
    health: number
    radiation: number
    incident: number
    exploration: number
    combat: number
  }
  revivable_count: number
  permanently_dead_count: number
}
