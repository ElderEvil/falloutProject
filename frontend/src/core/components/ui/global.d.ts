export {}

declare module '@vue/runtime-core' {
  export interface GlobalComponents {
    UAlert: typeof import('./UAlert.vue')['default']
    UBadge: typeof import('./UBadge.vue')['default']
    UButton: typeof import('./UButton.vue')['default']
    UCard: typeof import('./UCard.vue')['default']
    UInput: typeof import('./UInput.vue')['default']
    UModal: typeof import('./UModal.vue')['default']
    UProgressBar: typeof import('./UProgressBar.vue')['default']
    USelect: typeof import('./USelect.vue')['default']
    USkeleton: typeof import('./USkeleton.vue')['default']
    UTabs: typeof import('./UTabs.vue')['default']
    UTooltip: typeof import('./UTooltip.vue')['default']
  }
}
