import { onScopeDispose, watch } from 'vue'
import { audioManager } from '@/core/audio/audioManager'
import { useProfileStore } from '../stores/profile'

const SAVE_DEBOUNCE_MS = 400

/**
 * Hydrates sound settings from the profile's `sound` preference and saves local
 * mute/volume edits back to it. The 400ms debounce collapses a slider drag into
 * one write; hydration never echoes because `applySettings` is silent.
 */
export function useSoundProfileSync(): void {
  const profileStore = useProfileStore()
  let timer: ReturnType<typeof setTimeout> | null = null

  watch(
    () => profileStore.profile?.preferences?.sound,
    (sound) => audioManager.applySettings(sound)
  )

  audioManager.setChangeHandler(() => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      const profile = profileStore.profile
      if (!profile) return
      const sound = { muted: audioManager.muted, volumes: { ...audioManager.volumes } }
      void profileStore.savePreferences({ ...profile.preferences, sound }).catch(() => {})
    }, SAVE_DEBOUNCE_MS)
  })

  onScopeDispose(() => {
    if (timer) clearTimeout(timer)
    audioManager.setChangeHandler(null)
  })
}
