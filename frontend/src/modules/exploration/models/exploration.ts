export const EXPLORATION_EVENT_TYPES = [
  'combat',
  'loot',
  'danger',
  'rest',
  'discovery',
  'item_use',
  'equip',
] as const

export type ExplorationEventType = (typeof EXPLORATION_EVENT_TYPES)[number]

type EventMap = Record<ExplorationEventType | 'default', string>

export const EVENT_ICON_MAP: EventMap = {
  combat: 'mdi:sword-cross',
  loot: 'mdi:treasure-chest',
  discovery: 'mdi:compass',
  danger: 'mdi:alert',
  rest: 'mdi:sleep',
  item_use: 'mdi:medical-bag',
  equip: 'mdi:sword-cross',
  default: 'mdi:circle-medium',
}

export const EVENT_COLOR_MAP: EventMap = {
  combat: 'var(--color-danger)',
  loot: 'var(--color-rarity-legendary)',
  discovery: 'var(--color-info)',
  danger: 'var(--color-danger)',
  rest: 'var(--color-rarity-rare)',
  item_use: 'var(--color-rarity-rare)',
  equip: 'var(--color-warning)',
  default: 'var(--color-theme-primary)',
}

const DEFAULT_ICON = EVENT_ICON_MAP.default
const DEFAULT_COLOR = EVENT_COLOR_MAP.default

export function getEventIcon(eventType: string): string {
  return EVENT_ICON_MAP[eventType as ExplorationEventType] ?? DEFAULT_ICON
}

export function getEventColor(eventType: string): string {
  return EVENT_COLOR_MAP[eventType as ExplorationEventType] ?? DEFAULT_COLOR
}

// Rarity color lives in the shared item-display module
export { getRarityColor } from '@/core/models/items'
