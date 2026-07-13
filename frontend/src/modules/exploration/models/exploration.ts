export const EVENT_ICON_MAP: Record<string, string> = {
  combat: 'mdi:sword-cross',
  loot: 'mdi:treasure-chest',
  exploration: 'mdi:map-marker',
  discovery: 'mdi:eye',
  encounter: 'mdi:account-alert',
  danger: 'mdi:alert',
  rest: 'mdi:sleep',
  default: 'mdi:circle-medium',
}

export const EVENT_COLOR_MAP: Record<string, string> = {
  combat: '#ff4444',
  loot: '#FFD700',
  exploration: 'var(--color-theme-primary)',
  discovery: '#4169E1',
  encounter: '#ff9900',
  danger: '#ff0000',
  rest: '#00ced1',
  default: 'var(--color-theme-primary)',
}

export function getEventIcon(eventType: string): string {
  return EVENT_ICON_MAP[eventType] ?? EVENT_ICON_MAP.default!
}

export function getEventColor(eventType: string): string {
  return EVENT_COLOR_MAP[eventType] ?? EVENT_COLOR_MAP.default!
}
