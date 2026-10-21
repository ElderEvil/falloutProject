import { describe, expect, it } from 'vitest'
import {
  BARBERSHOP_HAIR_COLORS,
  BARBERSHOP_SKIN_TONES,
  humanPortraitVariantUrls,
  normalizeHairColor,
  normalizeSkinTone,
} from '@/modules/rooms/models/barbershop'

describe('barbershop presets', () => {
  it('exposes the curated fallback swatches', () => {
    expect([...BARBERSHOP_SKIN_TONES]).toEqual(['Pale', 'Tan', 'Brown', 'Ebony'])
    expect([...BARBERSHOP_HAIR_COLORS]).toEqual([
      'Blonde',
      'Brunette',
      'Black',
      'Brown',
      'Red',
      'Gray',
    ])
  })

  it('normalizes skin tones case-insensitively and through aliases', () => {
    expect(normalizeSkinTone('pale')).toBe('Pale')
    expect(normalizeSkinTone('TAN')).toBe('Tan')
    expect(normalizeSkinTone('fair')).toBe('Pale')
    expect(normalizeSkinTone('light')).toBe('Pale')
    expect(normalizeSkinTone('dark brown')).toBe('Brown')
    expect(normalizeSkinTone('unknown')).toBe('Pale')
    expect(normalizeSkinTone(null)).toBe('Pale')
  })

  it('normalizes hair colors and forces silver on elders', () => {
    expect(normalizeHairColor('blonde', 'adult')).toBe('Blonde')
    expect(normalizeHairColor('BLACK', 'adult')).toBe('Black')
    expect(normalizeHairColor('unknown', 'adult')).toBe('Brown')
    expect(normalizeHairColor(null, 'adult')).toBe('Brown')
    expect(normalizeHairColor('red', 'elder')).toBe('Gray')
    expect(normalizeHairColor('blonde', 'elder')).toBe('Gray')
    expect(normalizeHairColor(null, 'ELDER')).toBe('Gray')
  })
})

describe('humanPortraitVariantUrls', () => {
  it('builds the adult image and thumbnail paths with canonical casing', () => {
    expect(humanPortraitVariantUrls('male', 'adult', 'pale', 'blonde')).toEqual({
      imageUrl:
        '/static/dweller_images/variants/adult/FOS_Dw_Default_Human_Male_SkinPale_HairBlonde.webp',
      thumbnailUrl:
        '/static/dweller_thumbnails/variants/adult/FOS_Dw_Default_Human_Male_SkinPale_HairBlonde.webp',
    })
    expect(humanPortraitVariantUrls('female', 'adult', 'Tan', 'Black')).toEqual({
      imageUrl:
        '/static/dweller_images/variants/adult/FOS_Dw_Default_Human_Female_SkinTan_HairBlack.webp',
      thumbnailUrl:
        '/static/dweller_thumbnails/variants/adult/FOS_Dw_Default_Human_Female_SkinTan_HairBlack.webp',
    })
  })

  it('builds elder paths with gray hair regardless of the requested color', () => {
    expect(humanPortraitVariantUrls('female', 'elder', 'Brown', 'red')).toEqual({
      imageUrl:
        '/static/dweller_images/variants/elder/FOS_Dw_Default_Human_Elder_Female_SkinBrown_HairGray.webp',
      thumbnailUrl:
        '/static/dweller_thumbnails/variants/elder/FOS_Dw_Default_Human_Elder_Female_SkinBrown_HairGray.webp',
    })
  })

  it('returns null for ages and genders without variant art', () => {
    expect(humanPortraitVariantUrls('male', 'child', 'Pale', 'Blonde')).toBeNull()
    expect(humanPortraitVariantUrls('male', 'teen', 'Pale', 'Blonde')).toBeNull()
    expect(humanPortraitVariantUrls('other', 'adult', 'Pale', 'Blonde')).toBeNull()
    expect(humanPortraitVariantUrls(null, 'adult', 'Pale', 'Blonde')).toBeNull()
  })
})
