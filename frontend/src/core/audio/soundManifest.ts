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
  success: '/audio/ui/success.wav',
  select: '/audio/ui/select.wav',
  tabSwitch: '/audio/ui/tab-switch.wav',
  upgrade: '/audio/ui/upgrade.wav',
  cardDrop: '/audio/ui/card-drop.wav',
} as const

export type SoundKey = keyof typeof SOUND_MANIFEST

/** Looping music tracks, keyed for `audioManager.playLoop`. */
export const MUSIC_MANIFEST = {
  vaultAmbient: '/audio/music/vault-ambient-1.mp3',
  exploration: '/audio/music/exploration-1.mp3',
} as const

export type MusicKey = keyof typeof MUSIC_MANIFEST
