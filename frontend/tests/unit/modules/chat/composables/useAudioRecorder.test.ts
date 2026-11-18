import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { effectScope } from 'vue'
import { useAudioRecorder } from '@/modules/chat/composables/useAudioRecorder'

/**
 * Closing the chat while a recording is in flight unmounts the host component.
 * Without scope disposal the 1s duration interval kept running and the
 * MediaStream tracks were never stopped, leaving the microphone capturing.
 *
 * NOTE: the stub must be a real class — `new MediaRecorder(stream, options)` is
 * called by the composable, and a vi.fn() returning an object is not constructable.
 */
class MediaRecorderStub {
  static isTypeSupported = () => true

  state: 'inactive' | 'recording' | 'paused' = 'inactive'
  ondataavailable: ((event: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null
  onerror: ((error: unknown) => void) | null = null
  readonly stream: { getTracks: () => { stop: () => void }[] }

  start = vi.fn(() => {
    this.state = 'recording'
  })

  pause = vi.fn(() => {
    this.state = 'paused'
  })

  resume = vi.fn(() => {
    this.state = 'recording'
  })

  stop = vi.fn(() => {
    this.state = 'inactive'
    this.onstop?.()
  })

  constructor(stream: { getTracks: () => { stop: () => void }[] }) {
    this.stream = stream
  }
}

describe('useAudioRecorder scope disposal', () => {
  let trackStop: ReturnType<typeof vi.fn>
  let stream: { getTracks: () => { stop: () => void }[] }

  beforeEach(() => {
    vi.useFakeTimers()
    trackStop = vi.fn()
    stream = { getTracks: () => [{ stop: trackStop }] }
    vi.stubGlobal('MediaRecorder', MediaRecorderStub)
    Object.defineProperty(navigator, 'mediaDevices', {
      value: { getUserMedia: vi.fn(async () => stream) },
      configurable: true,
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('stops the microphone and the duration timer when the scope is disposed mid-recording', async () => {
    const scope = effectScope()
    const recorder = scope.run(() => useAudioRecorder())!

    await recorder.startRecording()
    expect(recorder.recordingState.value).toBe('recording')

    vi.advanceTimersByTime(3000)
    expect(recorder.recordingDuration.value).toBe(3)

    scope.stop()

    expect(trackStop).toHaveBeenCalledTimes(1)
    expect(recorder.recordingState.value).toBe('idle')

    const durationAtDisposal = recorder.recordingDuration.value
    vi.advanceTimersByTime(5000)
    expect(recorder.recordingDuration.value).toBe(durationAtDisposal)
  })

  it('is a no-op when the scope is disposed while idle', () => {
    const scope = effectScope()
    const recorder = scope.run(() => useAudioRecorder())!

    expect(() => scope.stop()).not.toThrow()
    expect(trackStop).not.toHaveBeenCalled()
    expect(recorder.recordingState.value).toBe('idle')
  })

  it('cancelRecording still releases the stream and resets the clock', async () => {
    const scope = effectScope()
    const recorder = scope.run(() => useAudioRecorder())!

    await recorder.startRecording()
    vi.advanceTimersByTime(2000)
    recorder.cancelRecording()

    expect(trackStop).toHaveBeenCalledTimes(1)
    expect(recorder.recordingState.value).toBe('idle')
    expect(recorder.recordingDuration.value).toBe(0)

    scope.stop()
    // Disposing after a cancel must not double-stop the tracks.
    expect(trackStop).toHaveBeenCalledTimes(1)
  })
})
