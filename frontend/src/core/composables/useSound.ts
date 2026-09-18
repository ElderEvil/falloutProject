import { audioManager, type AudioBus } from '../audio/audioManager'
import type { MusicKey, SoundKey } from '../audio/soundManifest'

/** Play a manifest sound and control music loops via the audio manager. */
export function useSound() {
  const playSound = (key: SoundKey, bus: AudioBus = 'ui') => audioManager.play(key, bus)
  const playMusic = (key: MusicKey) => audioManager.playLoop(key)
  const stopMusic = () => audioManager.stopLoop()

  return { playSound, playMusic, stopMusic }
}
