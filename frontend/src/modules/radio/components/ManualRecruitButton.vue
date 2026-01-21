<script setup lang="ts">
import { computed } from 'vue';
import { useRadioStore } from '../stores/radio';
import UButton from '@/core/components/ui/UButton.vue';

interface Props {
  vaultId: string;
  cost: number;
  currentCaps: number;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  recruited: [dwellerId: string]
}>();

const radioStore = useRadioStore();

const isRecruiting = computed(() => radioStore.isRecruiting);
const canAfford = computed(() => props.currentCaps >= props.cost);

async function handleRecruit() {
  if (!canAfford.value) {
    return;
  }

  const result = await radioStore.manualRecruit(props.vaultId);
  if (result) {
    emit('recruited', result.dweller.id);
  }
}
</script>


<template>
  <div class="manual-recruit-button">
    <UButton
      @click="handleRecruit"
      :disabled="isRecruiting || !canAfford"
      variant="primary"
      :class="{ 'opacity-50': !canAfford }"
    >
      <span v-if="isRecruiting">Recruiting...</span>
      <span v-else>
        Recruit for {{ cost }} caps
        <span v-if="!canAfford" class="text-red-400">(Insufficient caps)</span>
      </span>
    </UButton>

    <p v-if="!canAfford" class="text-sm text-red-400 mt-2">
      You need {{ cost - currentCaps }} more caps
    </p>
  </div>
</template>
