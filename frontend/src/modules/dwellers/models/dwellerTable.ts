export type DwellerTableColumnId =
  | 'portrait'
  | 'name'
  | 'level'
  | 'rarity'
  | 'gender'
  | 'age'
  | 'status'
  | 'health'
  | 'happiness'
  | 'room'

export interface DwellerTableColumn {
  id: DwellerTableColumnId
  label: string
  icon: string
  defaultVisible: boolean
  align?: 'left' | 'right'
}

export const DWELLER_TABLE_COLUMNS: readonly DwellerTableColumn[] = [
  { id: 'portrait', label: 'Portrait', icon: 'mdi:account-box-outline', defaultVisible: true },
  { id: 'name', label: 'Name', icon: 'mdi:account', defaultVisible: true },
  { id: 'level', label: 'Level', icon: 'mdi:star', defaultVisible: true, align: 'right' },
  { id: 'rarity', label: 'Rarity', icon: 'mdi:star-four-points', defaultVisible: false },
  { id: 'gender', label: 'Gender', icon: 'mdi:gender-male-female', defaultVisible: false },
  { id: 'age', label: 'Age', icon: 'mdi:account-group', defaultVisible: false },
  { id: 'status', label: 'Status', icon: 'mdi:progress-clock', defaultVisible: true },
  { id: 'health', label: 'HP', icon: 'mdi:heart', defaultVisible: true, align: 'right' },
  {
    id: 'happiness',
    label: 'Happiness',
    icon: 'mdi:emoticon-happy',
    defaultVisible: true,
    align: 'right',
  },
  { id: 'room', label: 'Room', icon: 'mdi:door-closed', defaultVisible: true },
]

export const DEFAULT_TABLE_COLUMNS: DwellerTableColumnId[] = DWELLER_TABLE_COLUMNS.filter(
  (column) => column.defaultVisible
).map((column) => column.id)

export interface DwellerTablePreset {
  id: string
  label: string
  icon: string
  columns: DwellerTableColumnId[]
}

export const DWELLER_TABLE_PRESETS: readonly DwellerTablePreset[] = [
  {
    id: 'roster',
    label: 'Roster',
    icon: 'mdi:format-list-bulleted',
    columns: ['portrait', 'name', 'level', 'status', 'room'],
  },
  {
    id: 'vitals',
    label: 'Vitals',
    icon: 'mdi:heart-pulse',
    columns: ['portrait', 'name', 'health', 'happiness', 'status'],
  },
  {
    id: 'assignments',
    label: 'Assignments',
    icon: 'mdi:door-closed',
    columns: ['portrait', 'name', 'room', 'status'],
  },
  {
    id: 'demographics',
    label: 'Demographics',
    icon: 'mdi:account-group',
    columns: ['portrait', 'name', 'gender', 'age', 'rarity'],
  },
]

/** Enabled columns in the canonical catalog order, so toggling never reorders the table. */
export function orderedVisibleColumns(
  visible: readonly DwellerTableColumnId[]
): DwellerTableColumn[] {
  const enabled = new Set(visible)
  return DWELLER_TABLE_COLUMNS.filter((column) => enabled.has(column.id))
}
