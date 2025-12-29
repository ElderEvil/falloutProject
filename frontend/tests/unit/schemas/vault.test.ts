import { describe, it, expect } from 'vitest'
import { vaultNumberSchema, parseVaultNumber } from '@/schemas/vault'
import { ZodError } from 'zod'

describe('Vault Number Validation', () => {
  describe('vaultNumberSchema', () => {
    describe('Happy Path', () => {
      it('should accept valid vault number 0', () => {
        const result = vaultNumberSchema.parse({ number: 0 })
        expect(result.number).toBe(0)
      })

      it('should accept valid vault number 999', () => {
        const result = vaultNumberSchema.parse({ number: 999 })
        expect(result.number).toBe(999)
      })

      it('should accept valid vault number in middle range', () => {
        const result = vaultNumberSchema.parse({ number: 500 })
        expect(result.number).toBe(500)
      })

      it('should accept vault number 13 (unlucky vault)', () => {
        const result = vaultNumberSchema.parse({ number: 13 })
        expect(result.number).toBe(13)
      })

      it('should accept vault number 101 (famous vault)', () => {
        const result = vaultNumberSchema.parse({ number: 101 })
        expect(result.number).toBe(101)
      })
    })

    describe('Edge Cases - Invalid Values', () => {
      it('should reject negative numbers', () => {
        expect(() => vaultNumberSchema.parse({ number: -1 })).toThrow(ZodError)
        expect(() => vaultNumberSchema.parse({ number: -1 })).toThrow('Vault number must be at least 0')
      })

      it('should reject numbers above 999', () => {
        expect(() => vaultNumberSchema.parse({ number: 1000 })).toThrow(ZodError)
        expect(() => vaultNumberSchema.parse({ number: 1000 })).toThrow('Vault number must be 999 or less')
      })

      it('should reject decimal numbers', () => {
        expect(() => vaultNumberSchema.parse({ number: 100.5 })).toThrow(ZodError)
        expect(() => vaultNumberSchema.parse({ number: 100.5 })).toThrow('Vault number must be a whole number')
      })

      it('should reject string values', () => {
        expect(() => vaultNumberSchema.parse({ number: '100' as any })).toThrow(ZodError)
      })

      it('should reject null', () => {
        expect(() => vaultNumberSchema.parse({ number: null as any })).toThrow(ZodError)
      })

      it('should reject undefined', () => {
        expect(() => vaultNumberSchema.parse({ number: undefined as any })).toThrow(ZodError)
      })

      it('should reject missing number field', () => {
        expect(() => vaultNumberSchema.parse({} as any)).toThrow(ZodError)
      })
    })

    describe('Boundary Values', () => {
      it('should accept minimum boundary (0)', () => {
        const result = vaultNumberSchema.parse({ number: 0 })
        expect(result.number).toBe(0)
      })

      it('should accept maximum boundary (999)', () => {
        const result = vaultNumberSchema.parse({ number: 999 })
        expect(result.number).toBe(999)
      })

      it('should reject just below minimum (-1)', () => {
        expect(() => vaultNumberSchema.parse({ number: -1 })).toThrow(ZodError)
      })

      it('should reject just above maximum (1000)', () => {
        expect(() => vaultNumberSchema.parse({ number: 1000 })).toThrow(ZodError)
      })
    })
  })

  describe('parseVaultNumber helper', () => {
    describe('Happy Path', () => {
      it('should parse valid string number', () => {
        const result = parseVaultNumber('100')
        expect(result).toBe(100)
      })

      it('should parse valid numeric value', () => {
        const result = parseVaultNumber(200)
        expect(result).toBe(200)
      })

      it('should parse string "0"', () => {
        const result = parseVaultNumber('0')
        expect(result).toBe(0)
      })

      it('should parse string "999"', () => {
        const result = parseVaultNumber('999')
        expect(result).toBe(999)
      })
    })

    describe('Edge Cases', () => {
      it('should throw on invalid string', () => {
        expect(() => parseVaultNumber('abc')).toThrow('Invalid vault number')
      })

      it('should throw on empty string', () => {
        expect(() => parseVaultNumber('')).toThrow('Invalid vault number')
      })

      it('should throw on negative string number', () => {
        expect(() => parseVaultNumber('-5')).toThrow()
      })

      it('should throw on out of range string', () => {
        expect(() => parseVaultNumber('1000')).toThrow()
      })

      it('should parse decimal string as integer (parseInt behavior)', () => {
        // parseInt('100.5') returns 100, which is valid
        const result = parseVaultNumber('100.5')
        expect(result).toBe(100)
      })

      it('should trim and parse valid string with whitespace', () => {
        const result = parseVaultNumber('  100  ')
        expect(result).toBe(100)
      })
    })
  })

  describe('Fallout Lore Validation', () => {
    it('should accept Vault 13 (Fallout 1)', () => {
      const result = vaultNumberSchema.parse({ number: 13 })
      expect(result.number).toBe(13)
    })

    it('should accept Vault 101 (Fallout 3)', () => {
      const result = vaultNumberSchema.parse({ number: 101 })
      expect(result.number).toBe(101)
    })

    it('should accept Vault 111 (Fallout 4)', () => {
      const result = vaultNumberSchema.parse({ number: 111 })
      expect(result.number).toBe(111)
    })

    it('should accept Vault 76 (Fallout 76)', () => {
      const result = vaultNumberSchema.parse({ number: 76 })
      expect(result.number).toBe(76)
    })

    it('should reject Vault 1000 (non-canon)', () => {
      expect(() => vaultNumberSchema.parse({ number: 1000 })).toThrow()
    })
  })
})
