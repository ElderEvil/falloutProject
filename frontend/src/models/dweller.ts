interface DwellerShort {
  id: string
  first_name: string
  last_name: string
  level: number
  health: number
  max_health: number
  happiness: number
  thumbnail_url: string
}

interface Dweller extends DwellerShort {
  image_url: string
  bio: string
  strength: number
  perception: number
  endurance: number
  charisma: number
  intelligence: number
  agility: number
  luck: number
}
