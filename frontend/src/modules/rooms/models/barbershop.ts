import type { components } from '@/core/types/api.generated'

export type BarbershopStatus = components['schemas']['BarbershopStatus']
export type BarbershopChangeRequest = components['schemas']['BarbershopChangeRequest']
export type BarbershopChangeResponse = components['schemas']['BarbershopChangeResponse']

/** Fallback swatches for the adult portrait set; the API owns the live list. */
export const BARBERSHOP_SKIN_TONES = ['Pale', 'Tan', 'Brown', 'Ebony'] as const
export const BARBERSHOP_HAIR_COLORS = [
  'Blonde',
  'Brunette',
  'Black',
  'Brown',
  'Red',
  'Gray',
] as const

const SKIN_TONE_BY_KEY: Record<string, string> = {
  fair: 'Pale',
  light: 'Pale',
  pale: 'Pale',
  tan: 'Tan',
  brown: 'Brown',
  'dark brown': 'Brown',
  ebony: 'Ebony',
}

const HAIR_COLOR_BY_KEY: Record<string, string> = {
  blonde: 'Blonde',
  brunette: 'Brunette',
  black: 'Black',
  brown: 'Brown',
  red: 'Red',
  gray: 'Gray',
}

const GENDER_BY_KEY: Record<string, string> = {
  male: 'Male',
  female: 'Female',
}

/** Map a stored skin tone onto a curated preset, case-insensitively. */
export function normalizeSkinTone(value: string | null | undefined): string {
  const key = String(value ?? '')
    .trim()
    .toLowerCase()
  return SKIN_TONE_BY_KEY[key] ?? 'Pale'
}

/** Map a stored hair colour onto a curated preset; elders always keep silver. */
export function normalizeHairColor(
  value: string | null | undefined,
  ageGroup: string | null | undefined
): string {
  if (String(ageGroup ?? '').toLowerCase() === 'elder') return 'Gray'
  const key = String(value ?? '')
    .trim()
    .toLowerCase()
  return HAIR_COLOR_BY_KEY[key] ?? 'Brown'
}

export interface HumanPortraitVariantUrls {
  imageUrl: string
  thumbnailUrl: string
}

/**
 * Curated portrait URLs for the default human portrait set. Only adults and
 * elders have variant art; anything else falls back to the dweller's own image.
 */
export function humanPortraitVariantUrls(
  gender: string | null | undefined,
  ageGroup: string | null | undefined,
  skinTone: string | null | undefined,
  hairColor: string | null | undefined
): HumanPortraitVariantUrls | null {
  const sex = GENDER_BY_KEY[String(gender ?? '').toLowerCase()]
  const age = String(ageGroup ?? '').toLowerCase()
  if (!sex || (age !== 'adult' && age !== 'elder')) return null

  const skin = normalizeSkinTone(skinTone)
  const file =
    age === 'elder'
      ? `FOS_Dw_Default_Human_Elder_${sex}_Skin${skin}_HairGray.webp`
      : `FOS_Dw_Default_Human_${sex}_Skin${skin}_Hair${normalizeHairColor(hairColor, age)}.webp`

  return {
    imageUrl: `/static/dweller_images/variants/${age}/${file}`,
    thumbnailUrl: `/static/dweller_thumbnails/variants/${age}/${file}`,
  }
}
