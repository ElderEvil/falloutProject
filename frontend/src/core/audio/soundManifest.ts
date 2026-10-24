/**
 * Sound asset manifest — the single map from sound key to asset URL.
 *
 * Files are served statically from `frontend/public/audio/` (URLs start with
 * `/audio/`). The source library lives in the git-ignored `/assets/audio/` —
 * curated copies land in `public/audio/` with clean names. A key whose file is
 * missing fails silently at play time, so the manifest can list sounds before
 * the assets are copied.
 */
export const SOUND_MANIFEST = {
  notification: '/audio/ui/notification.wav',
  objectiveReady: '/audio/ui/objective-ready.wav',
  objectiveClaim: '/audio/ui/objective-claim.wav',
  levelUp: '/audio/ui/level-up.wav',
  trainingComplete: '/audio/ui/training-complete.wav',
  radioRecruit: '/audio/ui/radio-recruit.wav',
  // Curated from the library: an air-raid style invasion siren, looped while an
  // incident is active (was a gentle synthesized two-note ping).
  alarm: '/audio/ui/incident-alarm.wav',
  success: '/audio/ui/success.wav',
  rushSuccess: '/audio/ui/success.wav',
  rushFail: '/audio/ui/incident-defeat.wav',
  select: '/audio/ui/select.wav',
  tabSwitch: '/audio/ui/tab-switch.wav',
  upgrade: '/audio/ui/upgrade.wav',
  cardDrop: '/audio/ui/card-drop.wav',
  modalOpen: '/audio/ui/modal-open.wav',
  typeKey: '/audio/ui/typewriter-key.mp3',
  messageReceive: '/audio/ui/message-receive.wav',
  lunchboxOpen: '/audio/ui/lunchbox-open.wav',
  cardWeapon: '/audio/ui/card-weapon.wav',
  cardOutfit: '/audio/ui/card-outfit.wav',
  cardCommon: '/audio/ui/card-common.mp3',
  cardRare: '/audio/ui/card-rare.mp3',
  cardLegendary: '/audio/ui/card-legendary.mp3',
  craftStart: '/audio/ui/craft-start.wav',
  vaultBuild: '/audio/ui/vault-build.wav',
  incidentRaider: '/audio/ui/incident-raider.wav',
  incidentRadroach: '/audio/ui/incident-radroach.wav',
  incidentMolerat: '/audio/ui/incident-molerat.wav',
  incidentFeralGhoul: '/audio/ui/incident-feral-ghoul.wav',
  incidentRadscorpion: '/audio/ui/incident-radscorpion.wav',
  incidentDeathclaw: '/audio/ui/incident-deathclaw.wav',
  incidentFire: '/audio/ui/incident-fire.wav',
  incidentDefeat: '/audio/ui/incident-defeat.wav',
  incidentHit: '/audio/ui/incident-hit.wav',
  // Curated from the source library's combat/critical interface cues.
  arenaCountdown: '/audio/ui/arena-countdown.mp3',
  arenaStart: '/audio/ui/arena-start.mp3',
  arenaReady: '/audio/ui/arena-ready.mp3',
  arenaSkill: '/audio/ui/arena-skill.mp3',
  arenaFinish: '/audio/ui/arena-finish.mp3',
  explorationLoot: '/audio/ui/exploration-loot.mp3',
  explorationComplete: '/audio/ui/exploration-complete.mp3',
  trainingStart: '/audio/ui/training-start.mp3',
  craftComplete: '/audio/ui/craft-complete.mp3',
  recipeUnlocked: '/audio/ui/recipe-unlocked.mp3',
  relationshipFormed: '/audio/ui/relationship-formed.mp3',
  pregnancyDetected: '/audio/ui/pregnancy-detected.mp3',
  babyBorn: '/audio/ui/baby-born.mp3',
  arenaMorale: '/audio/ui/arena-morale.mp3',
  dwellerInjured: '/audio/ui/dweller-injured.mp3',
  dwellerDied: '/audio/ui/dweller-died.mp3',
  dwellerExit: '/audio/ui/dweller-exit.mp3',
  hazardTeamJoined: '/audio/ui/hazard-team-joined.mp3',
  resourceLow: '/audio/ui/resource-low.mp3',
  resourceCritical: '/audio/ui/resource-critical.mp3',
  powerOutage: '/audio/ui/power-outage.mp3',
  questComplete: '/audio/ui/quest-complete.mp3',
  objectivesRefreshed: '/audio/ui/objectives-refreshed.mp3',
  mapRegistrationFailed: '/audio/ui/map-registration-failed.mp3',
  locationCleared: '/audio/ui/location-cleared.mp3',
  locationReady: '/audio/ui/location-ready.mp3',
} as const

export type SoundKey = keyof typeof SOUND_MANIFEST

/**
 * Music playlists, keyed for `audioManager.playLoop`. Entries cycle in order —
 * the next track crossfades in as one ends, wrapping after the last entry.
 */
export const MUSIC_MANIFEST = {
  vaultAmbient: [
    '/audio/music/vault-ambient-1.mp3',
    '/audio/music/vault-ambient-2.mp3',
    '/audio/music/vault-ambient-3.mp3',
    '/audio/music/vault-ambient-4.mp3',
  ],
  exploration: [
    '/audio/music/exploration-1.mp3',
    '/audio/music/exploration-2.mp3',
    '/audio/music/exploration-3.mp3',
    '/audio/music/exploration-4.mp3',
  ],
} as const

export type MusicKey = keyof typeof MUSIC_MANIFEST

/**
 * Room-category ambience loops, keyed by the room's lowercased category.
 * The fallback for rooms that have no per-room loop of their own.
 */
export const AMBIENCE_MANIFEST = {
  production: '/audio/ambience/production.wav',
  crafting: '/audio/ambience/crafting.wav',
  capacity: '/audio/ambience/capacity.wav',
  training: '/audio/ambience/training.wav',
} as const

/**
 * Per-room ambience loops, keyed by the room's lowercased name. A key must match
 * the room name modulo case, or the lookup misses and the room falls back to its category.
 */
export const ROOM_AMBIENCE_MANIFEST = {
  'living room': '/audio/ambience/living-room.mp3',
  'storage room': '/audio/ambience/storage-room.mp3',
  'outfit workshop': '/audio/ambience/outfit-workshop.mp3',
  'weapon workshop': '/audio/ambience/weapon-workshop.mp3',
  barbershop: '/audio/ambience/barbershop.mp3',
  elevator: '/audio/ambience/elevator.mp3',
  'vault door': '/audio/ambience/vault-door.mp3',
  diner: '/audio/ambience/diner.mp3',
  garden: '/audio/ambience/garden.mp3',
  medbay: '/audio/ambience/medbay.mp3',
  'nuclear reactor': '/audio/ambience/nuclear-reactor.mp3',
  'nuka-cola bottler': '/audio/ambience/nuka-cola-bottler.mp3',
  'power generator': '/audio/ambience/power-generator.mp3',
  'radio studio': '/audio/ambience/radio-studio.mp3',
  'science lab': '/audio/ambience/science-lab.mp3',
  'water treatment': '/audio/ambience/water-treatment.mp3',
  'water purification': '/audio/ambience/water-purification.mp3',
  "overseer's office": '/audio/ambience/overseers-office.mp3',
  'theme workshop': '/audio/ambience/theme-workshop.mp3',
  armory: '/audio/ambience/armory.mp3',
  'athletics room': '/audio/ambience/athletics-room.mp3',
  classroom: '/audio/ambience/classroom.mp3',
  'fitness room': '/audio/ambience/fitness-room.mp3',
  'game room': '/audio/ambience/game-room.mp3',
  lounge: '/audio/ambience/lounge.mp3',
  'weight room': '/audio/ambience/weight-room.mp3',
  arena: '/audio/ambience/arena.mp3',
  'response station': '/audio/ambience/response-station.mp3',
} as const

/** Curated themed-room loops. Party and Thanksgiving intentionally fall back
 * to the room's standard ambience until those themes have source audio. */
export const THEMED_ROOM_AMBIENCE = {
  'diner:brotherhood': '/audio/ambience/themed/diner-brotherhood.mp3',
  'diner:halloween': '/audio/ambience/themed/diner-halloween.mp3',
  'diner:institute': '/audio/ambience/themed/diner-institute.mp3',
  'diner:minutemen': '/audio/ambience/themed/diner-minutemen.mp3',
  'diner:railroad': '/audio/ambience/themed/diner-railroad.mp3',
  'diner:xmas': '/audio/ambience/themed/diner-xmas.mp3',
  'living:brotherhood': '/audio/ambience/themed/living-brotherhood.mp3',
  'living:halloween': '/audio/ambience/themed/living-halloween.mp3',
  'living:institute': '/audio/ambience/themed/living-institute.mp3',
  'living:minutemen': '/audio/ambience/themed/living-minutemen.mp3',
  'living:railroad': '/audio/ambience/themed/living-railroad.mp3',
  'living:xmas': '/audio/ambience/themed/living-xmas.mp3',
} as const

export type AmbienceKey =
  | keyof typeof AMBIENCE_MANIFEST
  | keyof typeof ROOM_AMBIENCE_MANIFEST
  | keyof typeof THEMED_ROOM_AMBIENCE

/** Resolve an ambience key to its asset URL across every ambience map. */
export function getAmbienceSrc(key: AmbienceKey): string | undefined {
  if (key in THEMED_ROOM_AMBIENCE) {
    return THEMED_ROOM_AMBIENCE[key as keyof typeof THEMED_ROOM_AMBIENCE]
  }
  return key in ROOM_AMBIENCE_MANIFEST
    ? ROOM_AMBIENCE_MANIFEST[key as keyof typeof ROOM_AMBIENCE_MANIFEST]
    : AMBIENCE_MANIFEST[key as keyof typeof AMBIENCE_MANIFEST]
}

const THEMED_ROOM_PREFIX: Record<string, string> = {
  diner: 'diner',
  'living room': 'living',
}

/**
 * Pick the ambience key for a room: its own loop when the library has one,
 * otherwise the room's category loop.
 */
export function getRoomAmbienceKey(
  room:
    | { name?: string | null; category?: string | null; room_style?: string | null }
    | null
    | undefined
): AmbienceKey | undefined {
  const name = room?.name?.trim().toLowerCase()
  const style = room?.room_style?.trim().toLowerCase()
  if (name && style && style !== 'default') {
    const themedKey = `${THEMED_ROOM_PREFIX[name] ?? name}:${style}`
    if (themedKey in THEMED_ROOM_AMBIENCE) {
      return themedKey as keyof typeof THEMED_ROOM_AMBIENCE
    }
  }
  if (name && name in ROOM_AMBIENCE_MANIFEST) return name as AmbienceKey
  const category = room?.category?.trim().toLowerCase()
  return category && category in AMBIENCE_MANIFEST ? (category as AmbienceKey) : undefined
}
