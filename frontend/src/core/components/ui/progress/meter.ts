/**
 * Shared terminal-meter presentation.
 *
 * One track/frame language for every meter: `Progress` (generic fill) and the
 * domain composites (`HealthRadiationBar`) resolve their track through these
 * classes, so a meter looks like the same instrument everywhere. The frame
 * carries no semantics and no domain arithmetic — owners keep their own ARIA.
 */

export type MeterSize = 'xs' | 'sm' | 'md'

export const METER_SIZE_CLASS: Record<MeterSize, string> = {
  xs: 'h-1',
  sm: 'h-1.5',
  md: 'h-2.5',
}

/** Dark recessed pill track shared by every meter. */
export const METER_TRACK_BASE =
  'relative flex w-full items-center overflow-x-hidden rounded-full bg-muted'

/** The bordered, recessed terminal treatment the domain meters share. */
export const METER_FRAME_TERMINAL =
  'border border-[var(--color-theme-glow)] bg-surface-sunken shadow-[inset_0_0_8px_var(--color-surface-canvas)]'

/** Decorative terminal divisions; never changes the announced numeric value. */
export const METER_TICKS_CLASS = 'pointer-events-none absolute inset-0'

export const METER_TICKS_STYLE =
  'background: repeating-linear-gradient(90deg, transparent 0, transparent calc(12.5% - 1px), rgb(0 0 0 / 0.5) calc(12.5% - 1px), rgb(0 0 0 / 0.5) 12.5%)'
