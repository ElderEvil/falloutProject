import { describe, it, expect } from 'vitest'
import {
  DWELLER_TABLE_COLUMNS,
  DWELLER_TABLE_PRESETS,
  DEFAULT_TABLE_COLUMNS,
  canonicalColumnOrder,
  normalizeTableColumns,
  orderedVisibleColumns,
} from '@/modules/dwellers/models/dwellerTable'

describe('dwellerTable model', () => {
  it('defaults to the columns flagged defaultVisible', () => {
    expect(DEFAULT_TABLE_COLUMNS).toEqual(
      DWELLER_TABLE_COLUMNS.filter((column) => column.defaultVisible).map((column) => column.id)
    )
  })

  it('orders visible columns by the catalog, not the input order', () => {
    expect(orderedVisibleColumns(['room', 'name', 'level']).map((column) => column.id)).toEqual([
      'name',
      'level',
      'room',
    ])
  })

  it('ignores unknown column ids', () => {
    expect(orderedVisibleColumns(['name', 'bogus' as never]).map((column) => column.id)).toEqual([
      'name',
    ])
  })

  it('defines non-empty presets that only reference known columns', () => {
    const known = new Set(DWELLER_TABLE_COLUMNS.map((column) => column.id))

    expect(DWELLER_TABLE_PRESETS.length).toBeGreaterThan(0)
    for (const preset of DWELLER_TABLE_PRESETS) {
      expect(preset.columns.length).toBeGreaterThan(0)
      for (const id of preset.columns) expect(known.has(id)).toBe(true)
    }
  })

  it('sorts columns into catalog order', () => {
    expect(canonicalColumnOrder(['room', 'name', 'level'])).toEqual(['name', 'level', 'room'])
  })

  it('normalizes persisted columns, dropping unknown and duplicate ids', () => {
    expect(normalizeTableColumns(['room', 'room', 'bogus', 'name'])).toEqual(['name', 'room'])
  })

  it('falls back to the defaults for an empty persisted array', () => {
    expect(normalizeTableColumns([])).toEqual(DEFAULT_TABLE_COLUMNS)
  })

  it('falls back to the defaults when only retired ids are persisted', () => {
    expect(normalizeTableColumns(['retired-a', 'retired-b'])).toEqual(DEFAULT_TABLE_COLUMNS)
  })

  it('falls back to the defaults for a non-array value', () => {
    expect(normalizeTableColumns(null)).toEqual(DEFAULT_TABLE_COLUMNS)
  })
})
