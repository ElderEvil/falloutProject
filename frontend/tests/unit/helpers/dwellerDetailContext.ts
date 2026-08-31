import { defineComponent, h, provide, ref, type Ref } from 'vue'
import { mount, type MountingOptions, type VueWrapper } from '@vue/test-utils'
import { vi } from 'vitest'
import {
  dwellerDetailKey,
  type DwellerDetailContext,
} from '@/modules/dwellers/components/DwellerDetailContext'
import type { Dweller, MapPlaceLink, RevivalCostResponse } from '@/modules/dwellers/models/dweller'
import type { DwellerDetailActions } from '@/modules/dwellers/composables/useDwellerDetail'

function createDefaultActions(): DwellerDetailActions {
  return {
    assign: vi.fn(),
    unassign: vi.fn(),
    recall: vi.fn(),
    openSendToWasteland: vi.fn(),
    confirmSendToWasteland: vi.fn(),
    cancelSendToWasteland: vi.fn(),
    useStimpak: vi.fn(),
    useRadAway: vi.fn(),
    issueMedicalSupply: vi.fn(),
    rename: vi.fn(),
    confirmRename: vi.fn(),
    openRenameDialog: vi.fn(),
    revive: vi.fn(),
    generateBio: vi.fn(),
    extendBio: vi.fn(),
    generatePortrait: vi.fn(),
    generateAppearance: vi.fn(),
    generateAll: vi.fn(),
    editAppearance: vi.fn(),
    saveAppearance: vi.fn(),
    onTrainingStarted: vi.fn(),
    refresh: vi.fn(),
    onBack: vi.fn(),
    navigateToChat: vi.fn(),
    navigateToDweller: vi.fn(),
    onHeaderNameClick: vi.fn(),
  }
}

/**
 * Build a full `DwellerDetailContext` mock. Every state field is a `ref` and
 * every action is a `vi.fn()`, so a component-under-test can read state and spy
 * on the actions it calls through `inject` instead of props/emits.
 */
export function createMockDwellerDetailContext(
  overrides: Partial<DwellerDetailContext> = {},
): DwellerDetailContext {
  const base: DwellerDetailContext = {
    dweller: ref<Dweller | null | undefined>(null),
    loading: ref(false),
    placeLinks: ref<MapPlaceLink[]>([]),
    revivalCost: ref<RevivalCostResponse | null>(null),
    revivalLoading: ref(false),
    generatingBio: ref(false),
    generatingAppearance: ref(false),
    generatingPortrait: ref(false),
    generatingAI: ref(false),
    usingStimpak: ref(false),
    usingRadAway: ref(false),
    issuingMedicalSupply: ref(false),
    assigning: ref(false),
    unassigning: ref(false),
    isAnyGenerating: ref(false),
    cardLoading: ref(false),
    availableStimpaks: ref<number | undefined>(0),
    availableRadaways: ref<number | undefined>(0),
    vaultId: ref<string>(''),
    dwellerId: ref<string>(''),
    initialTab: ref<string | undefined>(undefined),
    highlightStat: ref<string | undefined>(undefined),
    appearanceEditorOpen: ref(false),
    trainingModalOpen: ref(false),
    renameDialogOpen: ref(false),
    renameDialogName: ref(''),
    wastelandModalOpen: ref(false),
    wastelandPendingDweller: ref<{ firstName: string; lastName?: string } | null>(null),
    actions: createDefaultActions(),
  }
  return { ...base, ...overrides }
}

/**
 * Mount `Component` with the dweller-detail context provided, so components that
 * call `useDwellerDetailContext()` work without a full `DwellerDetailContainer`.
 */
export function mountWithDwellerContext(
  Component: unknown,
  options: MountingOptions<unknown> & { context?: DwellerDetailContext } = {},
): VueWrapper {
  const { context, props: _props, ...mountOptions } = options
  const ctx = context ?? createMockDwellerDetailContext()
  const Wrapper = defineComponent({
    setup() {
      provide(dwellerDetailKey, ctx)
      return () => h(Component as never)
    },
  })
  return mount(Wrapper, mountOptions as never)
}
