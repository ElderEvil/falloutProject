import { z } from 'zod'

/**
 * Vault number validation schema
 * Following Fallout lore: Vaults are numbered 1-999
 * Using Zod v4 best practices: top-level validators and unified error parameter
 */
export const vaultNumberSchema = z.object({
  number: z.number({
    error: 'Vault number must be a number',
  }).int({ error: 'Vault number must be a whole number' }).min(1, { error: 'Vault number must be at least 1' }).max(999, { error: 'Vault number must be 999 or less' }),
  boosted: z.boolean().default(false),
})

export type VaultNumberData = z.infer<typeof vaultNumberSchema>

/**
 * Helper to parse and validate vault number from string input
 * Using Zod v4 safeParse for error handling
 */
export function parseVaultNumber(value: string | number): number {
  const parsed = typeof value === 'string' ? parseInt(value, 10) : value
  if (isNaN(parsed)) {
    throw new Error('Invalid vault number')
  }
  const result = vaultNumberSchema.safeParse({ number: parsed })
  if (!result.success) {
    const error = result.error
    const firstError = error.errors[0]
    throw new Error(firstError?.message ?? 'Invalid vault number')
  }
  return parsed
}
