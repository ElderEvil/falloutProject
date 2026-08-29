import { inject, type InjectionKey } from 'vue'
import type { UseDwellerDetailReturn } from '../composables/useDwellerDetail'

export type DwellerDetailContext = UseDwellerDetailReturn

export const dwellerDetailKey: InjectionKey<DwellerDetailContext> = Symbol('dwellerDetail')

export function useDwellerDetailContext(): DwellerDetailContext {
  const ctx = inject(dwellerDetailKey)
  if (!ctx) throw new Error('useDwellerDetailContext must be used within DwellerDetailContainer')
  return ctx
}
