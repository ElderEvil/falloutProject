<script setup lang="ts">
import { computed } from 'vue'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import DwellerDetailContainer from '../DwellerDetailContainer.vue'

const props = defineProps<{ dwellerId: string; vaultId: string }>()
const emit = defineEmits<{ close: [] }>()
const fullscreenTo = computed(() => ({
  name: 'dwellerDetail',
  params: { id: props.vaultId, dwellerId: props.dwellerId },
  query: {},
}))
</script>

<template>
  <TerminalModal
    :open="true"
    title="Dweller details"
    size="6xl"
    max-height="90"
    body-class="min-h-0 flex-1 overflow-y-auto"
    :fullscreen-to="fullscreenTo"
    @close="emit('close')"
  >
    <div class="p-5">
      <DwellerDetailContainer
        :dweller-id="dwellerId"
        :vault-id="vaultId"
        embedded
        @close="emit('close')"
      />
    </div>
  </TerminalModal>
</template>
