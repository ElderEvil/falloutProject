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
  // Curated from the library: an air-raid style invasion siren, looped while an
  // incident is active (was a gentle synthesized two-note ping).
  alarm: '/audio/ui/incident-alarm.wav',
  success: '/audio/ui/success.wav',
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
} as const

export type SoundKey = keyof typeof SOUND_MANIFEST

/** Looping music tracks, keyed for `audioManager.playLoop`. */
export const MUSIC_MANIFEST = {
  vaultAmbient: '/audio/music/vault-ambient-1.mp3',
  exploration: '/audio/music/exploration-1.mp3',
} as const

export type MusicKey = keyof typeof MUSIC_MANIFEST

/** Room-category ambience loops, keyed by the room's lowercased category. */
export const AMBIENCE_MANIFEST = {
  production: '/audio/ambience/production.wav',
  crafting: '/audio/ambience/crafting.wav',
  capacity: '/audio/ambience/capacity.wav',
  training: '/audio/ambience/training.wav',
} as const

export type AmbienceKey = keyof typeof AMBIENCE_MANIFEST

export function getRoomAmbienceKey(category: string | null | undefined): AmbienceKey | undefined {
  const key = String(category ?? '').toLowerCase()
  return key in AMBIENCE_MANIFEST ? (key as AmbienceKey) : undefined
}
