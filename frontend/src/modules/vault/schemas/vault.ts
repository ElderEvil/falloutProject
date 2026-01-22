import { z } from 'zod'

/**
 * Vault number validation schema
 * Following Fallout lore: Vaults are numbered 0-999
 */
export const vaultNumberSchema = z.object({
  number: z
    .number({
      message: 'Vault number must be a number'
    })
    .int('Vault number must be a whole number')
    .min(0, 'Vault number must be at least 0')
    .max(999, 'Vault number must be 999 or less')
})

export type VaultNumberData = z.infer<typeof vaultNumberSchema>

/**
 * Helper to parse and validate vault number from string input
 */
export function parseVaultNumber(value: string | number): number {
  const parsed = typeof value === 'string' ? parseInt(value, 10) : value
  if (isNaN(parsed)) {
    throw new Error('Invalid vault number')
  }
  vaultNumberSchema.parse({ number: parsed })
  return parsed
}
