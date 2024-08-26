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

interface Special {
  strength: number
  perception: number
  endurance: number
  charisma: number
  intelligence: number
  agility: number
  luck: number
}

interface Dweller extends DwellerShort {
  bio: string
  image_url: string
  // stats
  strength: number
  perception: number
  endurance: number
  charisma: number
  intelligence: number
  agility: number
  luck: number
}
