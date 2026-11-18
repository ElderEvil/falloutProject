import { notifyErrorOnce } from '@/core/utils/errorHandler'
import { ref, computed, onScopeDispose } from 'vue'
import { useToast } from '@/core/composables/useToast'
import { formatClock } from '@/core/utils/format'

export type RecordingState = 'idle' | 'recording' | 'paused' | 'processing'

export function useAudioRecorder() {
  const toast = useToast()
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
        toast.info('WebM is unavailable; recording as MP4 instead')
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
      notifyErrorOnce(error, 'Failed to access microphone')
      throw new Error('Failed to access microphone. Please grant permission.', { cause: error })
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
        toast.error('Audio recording failed')
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
    teardown()
    recordingDuration.value = 0
  }

  function clearRecordingTimer(): void {
    if (recordingTimer.value) {
      clearInterval(recordingTimer.value)
      recordingTimer.value = null
    }
  }

  /**
   * Release the microphone and the duration timer.
   *
   * Called by cancelRecording and by scope disposal: closing the chat mid-recording
   * unmounts the host with a live MediaRecorder, so without this the interval keeps
   * ticking and the browser keeps capturing audio after the dialog is gone.
   */
  function teardown(): void {
    clearRecordingTimer()

    const recorder = mediaRecorder.value
    if (recorder) {
      // Detach first: a discarded recorder must not push chunks into a disposed
      // scope or resolve a pending stopRecording promise.
      recorder.ondataavailable = null
      recorder.onstop = null
      recorder.onerror = null
      if (recorder.state !== 'inactive') {
        try {
          recorder.stop()
        } catch {
          // Recorder already stopped itself; nothing to release.
        }
      }
      recorder.stream.getTracks().forEach((track) => track.stop())
      mediaRecorder.value = null
    }

    audioChunks.value = []
    recordingState.value = 'idle'
  }

  onScopeDispose(teardown)

  const formatDuration = (seconds: number): string =>
    formatClock(seconds, { showHours: false, padMinutes: false })

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
