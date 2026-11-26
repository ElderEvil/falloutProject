import { describe, it, expect } from 'vite-plus/test'
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

  it.each([
    [
      'orders visible columns by the catalog, not the input order',
      ['room', 'name', 'level'],
      ['name', 'level', 'room'],
    ],
    ['drops unknown column ids', ['name', 'bogus'], ['name']],
  ] as const)('%s', (_name, input, expected) => {
    expect(orderedVisibleColumns([...input] as never).map((column) => column.id)).toEqual(expected)
  })

  it('sorts columns into catalog order via canonicalColumnOrder', () => {
    expect(canonicalColumnOrder(['room', 'name', 'level'])).toEqual(['name', 'level', 'room'])
  })

  it('defines non-empty presets that only reference known columns', () => {
    const known = new Set(DWELLER_TABLE_COLUMNS.map((column) => column.id))

    expect(DWELLER_TABLE_PRESETS.length).toBeGreaterThan(0)
    for (const preset of DWELLER_TABLE_PRESETS) {
      expect(preset.columns.length).toBeGreaterThan(0)
      for (const id of preset.columns) expect(known.has(id)).toBe(true)
    }
  })

  it('offers roster, vitals and demographics presets', () => {
    expect(DWELLER_TABLE_PRESETS.map((preset) => preset.id)).toEqual([
      'roster',
      'vitals',
      'demographics',
    ])
  })

  it('offers race as a column and in the demographics preset', () => {
    expect(DWELLER_TABLE_COLUMNS.map((column) => column.id)).toContain('race')
    expect(DWELLER_TABLE_PRESETS.find((preset) => preset.id === 'demographics')?.columns).toContain(
      'race'
    )
  })

  it.each([
    ['drops unknown and duplicate ids', ['room', 'room', 'bogus', 'name'], ['name', 'room']],
    ['falls back to the defaults for an empty array', [], DEFAULT_TABLE_COLUMNS],
    [
      'falls back to the defaults when only retired ids persist',
      ['retired-a', 'retired-b'],
      DEFAULT_TABLE_COLUMNS,
    ],
    ['falls back to the defaults for a non-array value', null, DEFAULT_TABLE_COLUMNS],
  ] as const)('normalizes persisted columns: %s', (_name, persisted, expected) => {
    expect(normalizeTableColumns(persisted as never)).toEqual(expected)
  })
})
