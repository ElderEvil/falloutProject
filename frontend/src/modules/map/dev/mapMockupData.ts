/**
 * THROWAWAY DEV FIXTURES — `/dev/map-mockup` decision artifact (delete or
 * promote after the map-improvement release is decided). Never imported by
 * production code; no API calls, no auth, fully deterministic (no Math.random).
 *
 * The place-group catalog mirrors `backend/app/data/places/place_groups.json`
 * verbatim so the mockup renders the real icon set the backend serves.
 */
import type { components } from '@/core/types/api.generated'
import type {
  DiscoveryRouteRead,
  DwellerRef,
  ExpeditionSiteMarkerRead,
  ExplorerTrack,
  PlaceGroup,
  PlayerVaultMarkerRead,
  VaultMarkerRead,
  WastelandLocationWithDwellers,
  WorldSnapshotRead,
} from '../models/map'
import type { TerrainType } from '../models/terrain'
import { ATLAS_TILES } from '../utils/atlasProjection'

type LocationClearStateRead = components['schemas']['LocationClearStateRead']

/** Fixed vault id every fixture location belongs to. */
export const MOCK_HOME_VAULT_ID = '00000000-0000-4000-8000-000000000001'

/** The single discovery left unviewed, so the unseen pulse stays visible. */
export const MOCK_UNSEEN_DISCOVERY_ID = 'mock-region'

const MOCK_CREATED_AT = '2180-08-17T09:00:00Z'

// ── Place-group catalog (mirrors place_groups.json) ─────────────────────

export const PLACE_GROUPS: PlaceGroup[] = [
  {
    key: 'settlement',
    label: 'Settlement',
    icon: 'mdi:home-group',
    risk: 'low',
    description:
      'A lived-in community: traders, scavengers, and the odd hired gun. Safer than the open wastes, never truly safe.',
    clearable: false,
    reclear_hours: null,
    loot_table: null,
    base_difficulty: null,
  },
  {
    key: 'city',
    label: 'City',
    icon: 'mdi:city',
    risk: 'medium',
    description:
      'A dense pre-war metropolis, rebuilt in the rubble. Everything is for sale, including information.',
    clearable: false,
    reclear_hours: null,
    loot_table: null,
    base_difficulty: null,
  },
  {
    key: 'gas_station',
    label: 'Gas Station',
    icon: 'mdi:gas-station',
    risk: 'low',
    description: 'A roadside fuel stop, picked over a hundred times but never quite empty.',
    clearable: true,
    reclear_hours: 168,
    loot_table: 'low',
    base_difficulty: 2,
  },
  {
    key: 'supermarket',
    label: 'Supermarket',
    icon: 'mdi:cart',
    risk: 'low',
    description:
      'A pre-war grocery with aisles of salvage and a stockroom nobody has fully cleared.',
    clearable: true,
    reclear_hours: 168,
    loot_table: 'low',
    base_difficulty: 2,
  },
  {
    key: 'factory',
    label: 'Factory',
    icon: 'mdi:factory',
    risk: 'medium',
    description:
      'Industrial machinery and raw scrap, guarded by whatever moved in after the bombs.',
    clearable: true,
    reclear_hours: 168,
    loot_table: 'medium',
    base_difficulty: 3,
  },
  {
    key: 'metro',
    label: 'Metro',
    icon: 'mdi:subway-variant',
    risk: 'medium',
    description: 'Collapsed transit tunnels: a shortcut for the bold and a den for everything else.',
    clearable: true,
    reclear_hours: 168,
    loot_table: 'medium',
    base_difficulty: 3,
  },
  {
    key: 'military',
    label: 'Military Site',
    icon: 'mdi:tank',
    risk: 'high',
    description: 'Armored remnants of the old world, still holding ordnance worth dying for.',
    clearable: true,
    reclear_hours: 168,
    loot_table: 'high',
    base_difficulty: 4,
  },
  {
    key: 'brotherhood_outpost',
    label: 'Brotherhood Outpost',
    icon: 'mdi:shield',
    risk: 'high',
    description: 'A steel-and-lasers chapter holding, jealous of its technology and its borders.',
    clearable: true,
    reclear_hours: 168,
    loot_table: 'high',
    base_difficulty: 4,
  },
  {
    key: 'research',
    label: 'Research Facility',
    icon: 'mdi:flask',
    risk: 'high',
    description:
      'Labs and think tanks where the pre-war world experimented on things it could not control.',
    clearable: true,
    reclear_hours: 168,
    loot_table: 'high',
    base_difficulty: 4,
  },
  {
    key: 'power',
    label: 'Power Facility',
    icon: 'mdi:lightning-bolt',
    risk: 'medium',
    description: 'Reactors and substations humming with a current that never learned to stop.',
    clearable: true,
    reclear_hours: 168,
    loot_table: 'medium',
    base_difficulty: 3,
  },
  {
    key: 'entertainment',
    label: 'Entertainment',
    icon: 'mdi:ferris-wheel',
    risk: 'low',
    description: "Theatres, parks, and drive-ins — the old world's amusements, now quieter.",
    clearable: true,
    reclear_hours: 168,
    loot_table: 'low',
    base_difficulty: 2,
  },
  {
    key: 'landmark',
    label: 'Landmark',
    icon: 'mdi:bank',
    risk: 'medium',
    description: 'A monument the wasteland still navigates by, for whatever it is worth now.',
    clearable: false,
    reclear_hours: null,
    loot_table: null,
    base_difficulty: null,
  },
  {
    key: 'vault_tec',
    label: 'Vault-Tec Site',
    icon: 'mdi:radioactive',
    risk: 'medium',
    description: 'Vault-Tec property. The door is the only honest part of it.',
    clearable: true,
    reclear_hours: 168,
    loot_table: 'medium',
    base_difficulty: 3,
  },
  {
    key: 'ruin',
    label: 'Ruins',
    icon: 'mdi:wall',
    risk: 'medium',
    description: 'A settlement that did not make it — bones of a town, loot for whoever braves them.',
    clearable: true,
    reclear_hours: 168,
    loot_table: 'medium',
    base_difficulty: 3,
  },
  {
    key: 'region',
    label: 'Wasteland Region',
    icon: 'mdi:map',
    risk: 'high',
    description: 'A stretch of the wastes too large to cross in one trip and too hostile to forget.',
    clearable: false,
    reclear_hours: null,
    loot_table: null,
    base_difficulty: null,
  },
  {
    key: 'exclusion_zone',
    label: 'Restricted Exclusion Site',
    icon: 'mdi:fence',
    risk: 'high',
    description:
      'A chain of rusted fences around an abandoned industrial complex. Scavengers insist the air bends after radstorms and that shiny things appear where nobody left them. Engineers insist the scavengers drink too much.',
    clearable: true,
    reclear_hours: 168,
    loot_table: 'high',
    base_difficulty: 4,
  },
  {
    key: 'wasteland_site',
    label: 'Wasteland Site',
    icon: 'mdi:map-marker-alert',
    risk: 'low',
    description:
      'An unmapped ruin of the old world. Nobody wrote down what it was, and nobody who went in came back with a straight answer.',
    clearable: true,
    reclear_hours: 168,
    loot_table: 'low',
    base_difficulty: 2,
  },
]

const GROUP_BY_KEY = new Map(PLACE_GROUPS.map((group) => [group.key, group]))

function placeGroup(key: string): PlaceGroup {
  const found = GROUP_BY_KEY.get(key)
  if (!found) throw new Error(`Unknown mock place group: ${key}`)
  return found
}

// ── Location fixtures ────────────────────────────────────────────────────

function mockLocation(input: {
  id: string
  name: string
  type: WastelandLocationWithDwellers['type']
  coordX: number
  coordY: number
  groupKey?: string | null
  description?: string | null
  dwellers?: DwellerRef[]
  isUnlocked?: boolean
  clearState?: LocationClearStateRead | null
}): WastelandLocationWithDwellers {
  return {
    id: input.id,
    name: input.name,
    normalized_name: input.name.toLowerCase(),
    type: input.type,
    coord_x: input.coordX,
    coord_y: input.coordY,
    description: input.description ?? null,
    group_key: input.groupKey ?? null,
    vault_id: MOCK_HOME_VAULT_ID,
    exploration_id: null,
    created_at: MOCK_CREATED_AT,
    clear_state: input.clearState ?? null,
    dwellers: input.dwellers ?? [],
    is_unlocked: input.isUnlocked ?? true,
  }
}

function mockClearState(
  group: PlaceGroup,
  overrides: Partial<LocationClearStateRead> = {},
): LocationClearStateRead {
  return {
    clearable: true,
    cleared: false,
    clear_count: 1,
    tier: group.base_difficulty ?? 1,
    time_remaining_seconds: 0,
    loot_table: group.loot_table ?? null,
    ...overrides,
  }
}

function discovery(
  group: PlaceGroup,
  name: string,
  coordX: number,
  coordY: number,
  options: {
    description?: string
    dwellers?: DwellerRef[]
    clearState?: Partial<LocationClearStateRead>
  } = {},
): WastelandLocationWithDwellers {
  return mockLocation({
    id: `mock-${group.key}`,
    name,
    type: 'discovery',
    coordX,
    coordY,
    groupKey: group.key,
    description: options.description ?? group.description,
    dwellers: options.dwellers,
    clearState: group.clearable ? mockClearState(group, options.clearState) : null,
  })
}

export const MOCK_LOCATIONS: WastelandLocationWithDwellers[] = [
  // One discovery per catalog group, spread across the 0-160 wire space.
  discovery(placeGroup('settlement'), 'Junction Creek Settlement', 22, 26, {
    dwellers: [
      {
        dweller_id: 'mock-dweller-piper',
        first_name: 'Piper',
        last_name: 'Wright',
        relation: 'origin',
        is_unlocked: true,
      },
      {
        dweller_id: 'mock-dweller-nick',
        first_name: 'Nick',
        last_name: 'Valentine',
        relation: 'visited',
        is_unlocked: true,
      },
    ],
  }),
  discovery(placeGroup('city'), 'New Adytum', 54, 18),
  discovery(placeGroup('gas_station'), 'Red Rocket Route 9', 88, 28, {
    dwellers: [
      {
        dweller_id: 'mock-dweller-cait',
        first_name: 'Cait',
        last_name: null,
        relation: 'visited',
        is_unlocked: true,
      },
    ],
  }),
  discovery(placeGroup('supermarket'), 'Super Duper Mart', 120, 22, {
    // The one cleared fixture: dimmed marker + shield-check badge + cooldown.
    clearState: { cleared: true, clear_count: 2, time_remaining_seconds: 61200 },
  }),
  discovery(placeGroup('factory'), 'Corvega Assembly Plant', 24, 60),
  discovery(placeGroup('metro'), 'Scollay Square Station', 56, 50),
  discovery(placeGroup('military'), 'Fort Hagen', 92, 62),
  discovery(placeGroup('brotherhood_outpost'), 'Outpost Echo', 130, 52),
  discovery(placeGroup('research'), 'CIT Ruins Laboratory', 18, 94),
  discovery(placeGroup('power'), 'Mass Fusion Substation', 52, 86),
  discovery(placeGroup('entertainment'), 'Nuka-World Drive-In', 86, 98),
  discovery(placeGroup('landmark'), 'Bunker Hill Monument', 124, 86),
  discovery(placeGroup('vault_tec'), 'Vault-Tec Regional Office', 22, 130),
  discovery(placeGroup('ruin'), 'Quincy Ruins', 56, 124),
  // Left unviewed on mount: proves the unseen discovery pulse still reads.
  discovery(placeGroup('region'), 'Glowing Sea Fringe', 92, 136),
  discovery(placeGroup('exclusion_zone'), 'Restricted Zone 12', 128, 126),
  discovery(placeGroup('wasteland_site'), 'Unmarked Overpass', 146, 70),

  // Anchor locations.
  mockLocation({
    id: 'mock-home-vault',
    name: 'Vault 42',
    type: 'home_vault',
    coordX: 80,
    coordY: 80,
    description: 'The fixture home vault — route anchor and fog origin.',
  }),
  mockLocation({
    id: 'mock-origin',
    name: 'Scavenger Origin',
    type: 'origin',
    coordX: 70,
    coordY: 92,
    description: 'Where the first scout crew came from.',
  }),
  mockLocation({
    id: 'mock-visited-radio',
    name: 'Radio Tower Camp',
    type: 'visited',
    coordX: 44,
    coordY: 66,
  }),
  mockLocation({
    id: 'mock-visited-depot',
    name: 'Abandoned Depot',
    type: 'visited',
    coordX: 108,
    coordY: 108,
  }),

  // Locked pair: both render as the dimmed "Unknown Location" hint state.
  mockLocation({
    id: 'mock-locked-discovery',
    name: 'Locked Signal',
    type: 'discovery',
    coordX: 36,
    coordY: 36,
    groupKey: 'ruin',
    isUnlocked: false,
  }),
  mockLocation({
    id: 'mock-locked-visited',
    name: 'Locked Camp',
    type: 'visited',
    coordX: 136,
    coordY: 100,
    groupKey: 'wasteland_site',
    isUnlocked: false,
  }),
]

// ── Companion marker fixtures ────────────────────────────────────────────

export const MOCK_VAULT_MARKERS: VaultMarkerRead[] = [
  {
    name: 'Vault 101 Signal',
    coord_x: 12,
    coord_y: 12,
    type: 'vault',
    description: 'A repeating Vault-Tec beacon from the north-west.',
  },
  {
    name: 'Vault 87 Signal',
    coord_x: 150,
    coord_y: 148,
    type: 'vault',
    description: 'A faint carrier wave from the far south-east.',
  },
]

export const MOCK_PLAYER_VAULTS: PlayerVaultMarkerRead[] = [
  {
    vault_id: '00000000-0000-4000-8000-000000000002',
    number: 76,
    coord_x: 148,
    coord_y: 12,
    is_mine: false,
  },
  {
    vault_id: '00000000-0000-4000-8000-000000000003',
    number: 111,
    coord_x: 90,
    coord_y: 150,
    is_mine: true,
  },
]

export const MOCK_DISCOVERY_ROUTES: DiscoveryRouteRead[] = [
  {
    exploration_id: '00000000-0000-4000-8000-0000000000e1',
    points: [
      {
        location_id: 'mock-settlement',
        coord_x: 22,
        coord_y: 26,
        timestamp: '2180-08-17T09:05:00Z',
      },
      { location_id: 'mock-city', coord_x: 54, coord_y: 18, timestamp: '2180-08-17T09:20:00Z' },
      { location_id: 'mock-power', coord_x: 52, coord_y: 86, timestamp: '2180-08-17T09:45:00Z' },
    ],
    is_active: true,
  },
]

export const MOCK_EXPEDITION_SITES: ExpeditionSiteMarkerRead[] = [
  {
    id: 'red_rocket',
    name: 'Red Rocket Fuel Depot',
    flavor: 'A crumbling service station still leaking fumes and salvage.',
    coord_x: 132,
    coord_y: 32,
    min_dweller_level: 5,
    room_total: 3,
    cleared: false,
    cooldown_remaining_seconds: 0,
    block_reason: null,
    exploration_id: null,
  },
  {
    id: 'super_duper_mart',
    name: 'Super Duper Mart',
    flavor: 'Empty shelves, full stockroom, and something nesting in the freezers.',
    coord_x: 20,
    coord_y: 136,
    min_dweller_level: 8,
    room_total: 4,
    cleared: true,
    cooldown_remaining_seconds: 7200,
    block_reason: 'cooldown',
    exploration_id: null,
  },
]

export const MOCK_EXPLORER_TRACKS: ExplorerTrack[] = [
  {
    explorationId: '00000000-0000-4000-8000-0000000000e2',
    dwellerName: 'Sarah Lyons',
    targetLocationId: null,
    lastKnown: { coord_x: 64, coord_y: 118 },
    dwellerThumbnailUrl: null,
  },
]

/** Proposed dweller-popover content (read-only copy for the preview section). */
export const MOCK_DWELLER_PREVIEW = {
  name: 'Sarah Lyons',
  status: 'exploring',
  task: 'Free-roaming the Glowing Sea Fringe',
  hitPoints: 78,
  radiation: 24,
} as const

// ── Deterministic terrain snapshot ───────────────────────────────────────

/** Integer hash → deterministic value in [0, 1). */
function hash01(x: number, y: number): number {
  let h = Math.imul(x, 0x27d4eb2d) ^ Math.imul(y, 0x165667b1)
  h = Math.imul(h ^ (h >>> 15), 0x85ebca6b)
  h = Math.imul(h ^ (h >>> 13), 0xc2b2ae35)
  h ^= h >>> 16
  return (h >>> 0) / 4294967296
}

function smooth(t: number): number {
  return t * t * (3 - 2 * t)
}

/** Bilinear-interpolated value noise over a square lattice of `cell` tiles. */
function valueNoise(x: number, y: number, cell: number): number {
  const gx = Math.floor(x / cell)
  const gy = Math.floor(y / cell)
  const fx = smooth((x - gx * cell) / cell)
  const fy = smooth((y - gy * cell) / cell)
  const n00 = hash01(gx, gy)
  const n10 = hash01(gx + 1, gy)
  const n01 = hash01(gx, gy + 1)
  const n11 = hash01(gx + 1, gy + 1)
  const top = n00 + (n10 - n00) * fx
  const bottom = n01 + (n11 - n01) * fx
  return top + (bottom - top) * fy
}

/** Three decorrelated octaves → one of the five persisted terrain kinds. */
function terrainAt(x: number, y: number): TerrainType {
  const wide = valueNoise(x, y, 17)
  const mid = valueNoise(x + 31, y + 17, 7)
  const fine = valueNoise(x + 101, y + 53, 3)
  const n = wide * 0.55 + mid * 0.3 + fine * 0.15
  if (n < 0.3) return 'water'
  if (n < 0.44) return 'wasteland'
  if (n < 0.53) return 'hills'
  if (n < 0.65) return 'forest'
  return 'ruins'
}

/**
 * Square 80x80 snapshot matching `WorldSnapshotRead`, row-major like the
 * backend's payload. Pure function of (x, y) — every render is identical.
 */
export function buildMockWorldSnapshot(): WorldSnapshotRead {
  const terrain: string[] = []
  for (let y = 0; y < ATLAS_TILES; y++) {
    for (let x = 0; x < ATLAS_TILES; x++) {
      terrain.push(terrainAt(x, y))
    }
  }
  return {
    world_id: 'dev-mockup-atlas',
    generator_version: 0,
    recipe_fingerprint: 'dev-mockup-fixture',
    snapshot_checksum: 'dev-mockup-fixture',
    width: ATLAS_TILES,
    height: ATLAS_TILES,
    terrain,
    slots: [],
  }
}
