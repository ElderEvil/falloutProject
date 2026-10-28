import { describe, expect, it } from 'vite-plus/test'
import { isFlyingPet } from '@/modules/pets/models/pet'

describe('flying pet presentation', () => {
  it.each([
    'Trained parrot',
    'Pirate parrot',
    'Vault-Tec parrot',
    'Butch',
    'Polly',
    'Vinnie',
    'Wanderer',
    'Alien Drone',
    ' POLLY ',
  ])('keeps %s airborne even without an image', (name) => {
    expect(isFlyingPet({ name, image_url: null })).toBe(true)
  })

  it.each(['FOS%20Trained%20parrot.png', 'FOS Alien Drone.png'])(
    'recognizes flying breed artwork %s for a named companion',
    (asset) => {
      expect(isFlyingPet({ name: 'Companion', image_url: `/static/pet_images/${asset}` })).toBe(
        true
      )
    }
  )

  it.each(['Dogmeat', 'CX404', 'Rollerbrain', 'Baby Deathclaw', 'Yao Guai Cub'])(
    'keeps %s on the floor',
    (name) => {
      expect(isFlyingPet({ name, image_url: null })).toBe(false)
    }
  )
})
