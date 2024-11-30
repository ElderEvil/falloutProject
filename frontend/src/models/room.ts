interface Room {
  id: string
  number: number
  category: string
  ability: string
  population_required: number
  base_cost: number
  incremental_cost: number
  t2_upgrade_cost: number
  t3_upgrade_cost: number
  capacity: number
  output: string
  size_min: number
  size_max: number
  size: number
  tier: number
  coordinate_x: number
  coordinate_y: number
  created_at: string
  updated_at: string
  thumbnail_url: string
}

interface RoomCreate {
  coordinate_x: number
  coordinate_y: number
  type: string
}
