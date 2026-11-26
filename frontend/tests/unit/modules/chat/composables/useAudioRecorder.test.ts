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
  static failOnStop = false
  static failConstruct = false
  static failStart = false

  state: 'inactive' | 'recording' | 'paused' = 'inactive'
  ondataavailable: ((event: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null
  onerror: ((error: unknown) => void) | null = null
  readonly stream: { getTracks: () => { stop: () => void }[] }

  start = vi.fn(() => {
    if (MediaRecorderStub.failStart) {
      throw new Error('start failed')
    }
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
    if (MediaRecorderStub.failOnStop) {
      this.onerror?.(new Error('recorder failed'))
      return
    }
    this.onstop?.()
  })

  constructor(stream: { getTracks: () => { stop: () => void }[] }) {
    if (MediaRecorderStub.failConstruct) {
      throw new Error('no recorder for you')
    }
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

  /** The composable inside its own scope, so disposal can be exercised. */
  const setup = () => {
    const scope = effectScope()
    return { scope, recorder: scope.run(() => useAudioRecorder())! }
  }

  afterEach(() => {
    MediaRecorderStub.failOnStop = false
    MediaRecorderStub.failConstruct = false
    MediaRecorderStub.failStart = false
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('stops the microphone and the duration timer when the scope is disposed mid-recording', async () => {
    const { scope, recorder } = setup()

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
    const { scope, recorder } = setup()

    expect(() => scope.stop()).not.toThrow()
    expect(trackStop).not.toHaveBeenCalled()
    expect(recorder.recordingState.value).toBe('idle')
  })

  it('cancelRecording still releases the stream and resets the clock', async () => {
    const { scope, recorder } = setup()

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

  it('stops the acquired stream when the scope is disposed while permission is pending', async () => {
    let resolveMedia!: (value: unknown) => void
    const getUserMedia = navigator.mediaDevices.getUserMedia as unknown as ReturnType<typeof vi.fn>
    getUserMedia.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveMedia = resolve
        })
    )
    const { scope, recorder } = setup()

    const starting = recorder.startRecording()
    scope.stop()
    resolveMedia(stream)
    await starting

    expect(trackStop).toHaveBeenCalledTimes(1)
    expect(recorder.recordingState.value).toBe('idle')
    expect(recorder.recordingDuration.value).toBe(0)
    vi.advanceTimersByTime(5000)
    expect(recorder.recordingDuration.value).toBe(0)
  })

  it('releases the microphone and the timer when the recorder errors mid-stop', async () => {
    MediaRecorderStub.failOnStop = true
    const { scope, recorder } = setup()

    await recorder.startRecording()
    vi.advanceTimersByTime(2000)

    await expect(recorder.stopRecording()).rejects.toThrow('recorder failed')

    expect(trackStop).toHaveBeenCalledTimes(1)
    expect(recorder.recordingState.value).toBe('idle')
    vi.advanceTimersByTime(5000)
    expect(recorder.recordingDuration.value).toBe(2)

    scope.stop()
    // Disposal after an error release must not double-stop the tracks.
    expect(trackStop).toHaveBeenCalledTimes(1)
  })
  it('stops the acquired stream when the recorder cannot be constructed', async () => {
    MediaRecorderStub.failConstruct = true
    const { scope, recorder } = setup()

    await expect(recorder.startRecording()).rejects.toThrow('Failed to access microphone')

    expect(trackStop).toHaveBeenCalledTimes(1)
    expect(recorder.recordingState.value).toBe('idle')
    vi.advanceTimersByTime(5000)
    expect(recorder.recordingDuration.value).toBe(0)
  })

  it('releases the recorder and the stream when start throws', async () => {
    MediaRecorderStub.failStart = true
    const { scope, recorder } = setup()

    await expect(recorder.startRecording()).rejects.toThrow('Failed to access microphone')

    // release() stops the recorder's stream and the catch stops the acquired
    // one; they are the same track here, and stops are idempotent.
    expect(trackStop).toHaveBeenCalledTimes(2)
    expect(recorder.recordingState.value).toBe('idle')
    vi.advanceTimersByTime(5000)
    expect(recorder.recordingDuration.value).toBe(0)
  })

  it('stops the second acquired stream when a retry fails after a completed recording', async () => {
    const secondTrackStop = vi.fn()
    const secondStream = { getTracks: () => [{ stop: secondTrackStop }] }
    const getUserMedia = navigator.mediaDevices.getUserMedia as unknown as ReturnType<typeof vi.fn>
    getUserMedia
      .mockImplementationOnce(async () => stream)
      .mockImplementationOnce(async () => secondStream)

    const { scope, recorder } = setup()

    await recorder.startRecording()
    await recorder.stopRecording()
    expect(trackStop).toHaveBeenCalledTimes(1)

    MediaRecorderStub.failConstruct = true
    await expect(recorder.startRecording()).rejects.toThrow('Failed to access microphone')

    expect(secondTrackStop).toHaveBeenCalledTimes(1)
    // release() re-stops the stale recorder's already-stopped track (idempotent).
    expect(trackStop).toHaveBeenCalledTimes(2)
    expect(recorder.recordingState.value).toBe('idle')
    vi.advanceTimersByTime(5000)
    expect(recorder.recordingDuration.value).toBe(0)
  })
})
