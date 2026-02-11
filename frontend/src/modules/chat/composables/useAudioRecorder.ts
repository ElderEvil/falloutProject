import { ref, computed } from 'vue'

export type RecordingState = 'idle' | 'recording' | 'paused' | 'processing'

export function useAudioRecorder() {
  const mediaRecorder = ref<MediaRecorder | null>(null)
  const audioChunks = ref<Blob[]>([])
  const recordingState = ref<RecordingState>('idle')
  const recordingDuration = ref(0)
  const recordingTimer = ref<number | null>(null)

  const isRecording = computed(() => recordingState.value === 'recording')
  const isPaused = computed(() => recordingState.value === 'paused')
  const isProcessing = computed(() => recordingState.value === 'processing')
  const isIdle = computed(() => recordingState.value === 'idle')

  const startRecording = async () => {
    try {
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })

      // Create MediaRecorder with WebM format (widely supported)
      const options = { mimeType: 'audio/webm;codecs=opus' }

      // Fallback for browsers that don't support webm
      if (!MediaRecorder.isTypeSupported(options.mimeType)) {
        console.warn('WebM not supported, trying mp4')
        options.mimeType = 'audio/mp4'
      }

      mediaRecorder.value = new MediaRecorder(stream, options)
      audioChunks.value = []

      // Collect audio data
      mediaRecorder.value.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.value.push(event.data)
        }
      }

      // Start recording
      mediaRecorder.value.start()
      recordingState.value = 'recording'
      recordingDuration.value = 0

      // Start duration timer
      recordingTimer.value = window.setInterval(() => {
        recordingDuration.value += 1
      }, 1000)
    } catch (error) {
      console.error('Error starting recording:', error)
      throw new Error('Failed to access microphone. Please grant permission.')
    }
  }

  const stopRecording = (): Promise<Blob> => {
    return new Promise((resolve, reject) => {
      if (!mediaRecorder.value || recordingState.value === 'idle') {
        reject(new Error('No active recording'))
        return
      }

      recordingState.value = 'processing'

      mediaRecorder.value.onstop = () => {
        // Stop all tracks
        mediaRecorder.value?.stream.getTracks().forEach((track) => track.stop())

        // Create blob from chunks
        const audioBlob = new Blob(audioChunks.value, { type: 'audio/webm' })

        // Clear timer
        if (recordingTimer.value) {
          clearInterval(recordingTimer.value)
          recordingTimer.value = null
        }

        recordingState.value = 'idle'
        audioChunks.value = []

        resolve(audioBlob)
      }

      mediaRecorder.value.onerror = (error) => {
        console.error('MediaRecorder error:', error)
        recordingState.value = 'idle'
        reject(error)
      }

      mediaRecorder.value.stop()
    })
  }

  const pauseRecording = () => {
    if (mediaRecorder.value && recordingState.value === 'recording') {
      mediaRecorder.value.pause()
      recordingState.value = 'paused'

      if (recordingTimer.value) {
        clearInterval(recordingTimer.value)
        recordingTimer.value = null
      }
    }
  }

  const resumeRecording = () => {
    if (mediaRecorder.value && recordingState.value === 'paused') {
      mediaRecorder.value.resume()
      recordingState.value = 'recording'

      recordingTimer.value = window.setInterval(() => {
        recordingDuration.value += 1
      }, 1000)
    }
  }

  const cancelRecording = () => {
    if (mediaRecorder.value) {
      mediaRecorder.value.stop()
      mediaRecorder.value.stream.getTracks().forEach((track) => track.stop())
      mediaRecorder.value = null
    }

    if (recordingTimer.value) {
      clearInterval(recordingTimer.value)
      recordingTimer.value = null
    }

    audioChunks.value = []
    recordingState.value = 'idle'
    recordingDuration.value = 0
  }

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  return {
    // State
    recordingState,
    recordingDuration,
    isRecording,
    isPaused,
    isProcessing,
    isIdle,

    // Methods
    startRecording,
    stopRecording,
    pauseRecording,
    resumeRecording,
    cancelRecording,
    formatDuration,
  }
}
