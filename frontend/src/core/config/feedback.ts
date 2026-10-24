export const FEEDBACK_TIMING = {
  rushDelaySeconds: 1.5,
  rushDurationSeconds: 1.6,
  vaultBoyDurationSeconds: 4.2,
  vaultBoyFrameSeconds: 0.18,
} as const

export const secondsToMs = (seconds: number): number => Math.round(seconds * 1000)

export const FEEDBACK_TIMING_MS = {
  rushDelay: secondsToMs(FEEDBACK_TIMING.rushDelaySeconds),
  rushDuration: secondsToMs(FEEDBACK_TIMING.rushDurationSeconds),
  vaultBoyDuration: secondsToMs(FEEDBACK_TIMING.vaultBoyDurationSeconds),
  vaultBoyFrame: secondsToMs(FEEDBACK_TIMING.vaultBoyFrameSeconds),
} as const
