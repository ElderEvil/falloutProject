<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import RewardItemCard from '@/core/components/common/RewardItemCard.vue'
import { getPetStats } from '@/core/models/items'
import type { components } from '@/core/types/api.generated'

type PetCarrierOpened = components['schemas']['PetCarrierOpened']

interface Props {
  show: boolean
  result: PetCarrierOpened | null
  opening?: boolean
  error?: string | null
}

const props = withDefaults(defineProps<Props>(), { opening: false, error: null })

const emit = defineEmits<{
  close: []
  reveal: []
}>()

const pet = computed(() => props.result?.pet ?? null)
const stats = computed(() => (pet.value ? getPetStats(pet.value.effect) : []))
</script>

<template>
  <TerminalModal
    :open="show"
    title="Pet carrier"
    icon="mdi:package-variant-closed"
    size="xl"
    max-height="80"
    :show-close="!opening"
    @close="!opening && emit('close')"
  >
    <div class="flex min-h-0 flex-1 flex-col items-center gap-4 overflow-y-auto p-6">
      <RewardItemCard
        v-if="pet"
        :name="pet.name"
        :rarity="pet.rarity"
        label="Companion"
        kind="item"
        item-type="pet"
        :image-url="pet.image_url"
        layout="column"
        class="w-full max-w-xs"
      />
      <div
        v-else
        class="flex h-52 w-full max-w-xs items-center justify-center rounded-lg border border-dashed border-theme-primary/30 bg-surface-sunken"
      >
        <Icon icon="mdi:paw" class="size-12 text-theme-primary/40" />
      </div>

      <p v-if="error" class="text-center text-sm text-danger" role="status">{{ error }}</p>
      <p v-else-if="opening" class="text-center text-sm text-theme-primary/70" role="status">
        Opening the carrier…
      </p>
      <template v-else-if="pet">
        <p v-if="pet.description" class="max-w-prose text-center text-sm text-theme-primary/80">
          {{ pet.description }}
        </p>
        <ul v-if="stats.length" class="flex flex-wrap justify-center gap-2">
          <li
            v-for="stat in stats"
            :key="stat.label"
            class="rounded border border-theme-primary/20 px-2 py-1 text-xs text-theme-primary"
          >
            {{ stat.label }} {{ stat.value }}
          </li>
        </ul>
        <p class="text-sm text-theme-primary/70">Added to Storage.</p>
      </template>
      <p v-else class="text-center text-sm text-theme-primary/70" role="status">
        A companion waits inside.
      </p>
    </div>

    <template #footer>
      <Button
        variant="default"
        class="w-full"
        :disabled="opening"
        @click="pet ? emit('close') : emit('reveal')"
      >
        {{ pet ? 'Done' : opening ? 'Opening…' : 'Reveal Pet' }}
      </Button>
    </template>
  </TerminalModal>
</template>
