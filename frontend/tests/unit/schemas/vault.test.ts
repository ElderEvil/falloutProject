import { describe, it, expect } from 'vite-plus/test'
import { vaultNumberSchema, parseVaultNumber } from '@/modules/vault/schemas/vault'
import { ZodError } from 'zod'

const parse = (number: unknown) => vaultNumberSchema.parse({ number })

/** Every rejection is a ZodError carrying the schema's own message. */
function expectRejection(number: unknown, message: string): void {
  expect(() => parse(number)).toThrow(ZodError)
  expect(() => parse(number)).toThrow(message)
}

describe('Vault Number Validation', () => {
  describe('vaultNumberSchema', () => {
    it.each([1, 13, 76, 101, 111, 500, 999])('accepts the vault number %i', (number) => {
      expect(parse(number).number).toBe(number)
    })

    describe('Vault Mode', () => {
      it.each(['standard', 'survival'])('accepts %s mode', (vaultMode) => {
        expect(
          vaultNumberSchema.parse({ number: 100, vaultMode: vaultMode as 'standard' }).vaultMode
        ).toBe(vaultMode)
      })

      it('should default to standard mode when omitted', () => {
        expect(parse(100).vaultMode).toBe('standard')
      })

      it('should reject an unknown mode', () => {
        expect(() =>
          vaultNumberSchema.parse({ number: 100, vaultMode: 'hardcore' as 'standard' })
        ).toThrow(ZodError)
      })
    })

    describe('Edge Cases - Invalid Values', () => {
      it.each([
        ['just below the minimum', -1, 'Vault number must be at least 1'],
        ['zero', 0, 'Vault number must be at least 1'],
        ['above the maximum', 1000, 'Vault number must be 999 or less'],
        ['a decimal', 100.5, 'Vault number must be a whole number'],
      ])('rejects a number %s', (_label, number, message) => {
        expectRejection(number, message)
      })

      it.each([
        ['a string value', '100'],
        ['null', null],
        ['undefined', undefined],
      ])('rejects %s', (_label, number) => {
        expect(() => parse(number)).toThrow(ZodError)
      })

      it('should reject missing number field', () => {
        expect(() => vaultNumberSchema.parse({})).toThrow(ZodError)
      })
    })
  })

  describe('parseVaultNumber helper', () => {
    it.each([
      ['100', 'a string number'],
      [200, 'a numeric value'],
      ['1', 'the minimum as a string'],
      ['999', 'the maximum as a string'],
    ])('parses %s (%s)', (input) => {
      expect(parseVaultNumber(input)).toBe(Number(input))
    })

    it.each(['abc', ''])('throws on the invalid string %j', (input) => {
      expect(() => parseVaultNumber(input)).toThrow('Invalid vault number')
    })

    it.each(['-5', '1000'])('throws on the out-of-range string %s', (input) => {
      expect(() => parseVaultNumber(input)).toThrow()
    })

    it('should parse decimal string as integer (parseInt behavior)', () => {
      // parseInt('100.5') returns 100, which is valid
      expect(parseVaultNumber('100.5')).toBe(100)
    })

    it('should trim and parse valid string with whitespace', () => {
      expect(parseVaultNumber('  100  ')).toBe(100)
    })
  })

  describe('Fallout Lore Validation', () => {
    it('should reject Vault 1000 (non-canon)', () => {
      expect(() => parse(1000)).toThrow()
    })
  })
})
