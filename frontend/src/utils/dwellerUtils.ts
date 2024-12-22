import type { Dweller } from '@/types/vault'

export function generateDwellerId(): string {
  return crypto.randomUUID()
}

export function getDwellerFullName(dweller: Dweller): string {
  return `${dweller.first_name} ${dweller.last_name}`
}

export function getDwellerImageUrl(dweller: Dweller): string {
  if (dweller.image_url) {
    return `http://${dweller.image_url}`
  }
  return `https://placehold.co/150x150/00ff00/000000.png?text=${encodeURIComponent(getDwellerFullName(dweller))}`
}

export function getDwellerThumbnailUrl(dweller: Dweller): string {
  if (dweller.thumbnail_url) {
    return `http://${dweller.thumbnail_url}`
  }
  return getDwellerImageUrl(dweller)
}

export function createNewDweller(firstName: string, lastName: string, level = 1): Dweller {
  return {
    id: generateDwellerId(),
    first_name: firstName,
    last_name: lastName,
    level,
    experience: 0,
    health: 100,
    max_health: 100,
    radiation: 0,
    happiness: 50,
    stimpack: 0,
    radaway: 0,
    assigned: false,
    special: {
      strength: Math.floor(Math.random() * 5) + 3,
      perception: Math.floor(Math.random() * 5) + 3,
      endurance: Math.floor(Math.random() * 5) + 3,
      charisma: Math.floor(Math.random() * 5) + 3,
      intelligence: Math.floor(Math.random() * 5) + 3,
      agility: Math.floor(Math.random() * 5) + 3,
      luck: Math.floor(Math.random() * 5) + 3
    },
    is_adult: true,
    gender: Math.random() > 0.5 ? 'male' : 'female',
    rarity: 'common',
    bio: `A vault dweller named ${firstName} ${lastName}`,
    visual_attributes: {
      age: 'adult',
      build: 'average',
      height: 'average',
      eye_color: 'brown',
      skin_tone: 'fair',
      appearance: 'average',
      hair_color: 'brown',
      hair_style: 'short',
      clothing_style: 'vault_suit'
    }
  }
}
