import { ref } from 'vue'
import { useToast } from '@/core/composables/useToast'

export function useChatAudio() {
  const toast = useToast()
  const currentlyPlayingAudio = ref<HTMLAudioElement | null>(null)
  const currentlyPlayingUrl = ref<string | null>(null)

  const stopAudio = () => {
    if (currentlyPlayingAudio.value) {
      currentlyPlayingAudio.value.pause()
      currentlyPlayingAudio.value.currentTime = 0
      currentlyPlayingAudio.value = null
    }
    currentlyPlayingUrl.value = null
  }

  const playAudio = (url: string) => {
    if (currentlyPlayingAudio.value) {
      currentlyPlayingAudio.value.pause()
      currentlyPlayingAudio.value = null
    }

    const audio = new Audio(url)
    currentlyPlayingAudio.value = audio
    currentlyPlayingUrl.value = url

    audio.play().catch(() => {
      toast.error('Unable to play audio')
      currentlyPlayingAudio.value = null
      currentlyPlayingUrl.value = null
    })

    audio.onended = () => {
      currentlyPlayingAudio.value = null
      currentlyPlayingUrl.value = null
    }
  }

  return {
    currentlyPlayingAudio,
    currentlyPlayingUrl,
    stopAudio,
    playAudio,
  }
}
