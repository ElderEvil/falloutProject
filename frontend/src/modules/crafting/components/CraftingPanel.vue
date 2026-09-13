<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { UButton, UCard } from '@/core/components/ui'
import { getRarityTextClass } from '@/core/models/items'
import { useToast } from '@/core/composables/useToast'
import { getErrorMessage } from '@/core/utils/errorHandler'
import { craftingService } from '../services/craftingService'
import type { CraftableItemType, CraftingRecipe } from '../models/crafting'

interface Props {
  vaultId: string
  itemType: CraftableItemType
}

const props = defineProps<Props>()

const emit = defineEmits<{
  crafted: []
}>()

const toast = useToast()

const recipes = ref<CraftingRecipe[]>([])
const isLoading = ref(false)
const craftingName = ref<string | null>(null)

const itemIcon = computed(() => (props.itemType === 'weapon' ? 'mdi:sword-cross' : 'mdi:tshirt-crew'))
const workshopLabel = computed(() => (props.itemType === 'weapon' ? 'Weapon workshop' : 'Outfit workshop'))
const materialCount = computed(() => recipes.value.reduce((total, recipe) => total + recipe.junk_cost, 0))
const craftableCount = computed(() => recipes.value.filter(recipe => recipe.can_craft).length)

async function loadRecipes() {
  if (!props.vaultId) return
  isLoading.value = true
  try {
    recipes.value = await craftingService.listRecipes(props.vaultId, props.itemType)
  } catch (error) {
    toast.error(getErrorMessage(error) || 'Failed to load crafting recipes')
    recipes.value = []
  } finally {
    isLoading.value = false
  }
}

async function handleCraft(recipe: CraftingRecipe) {
  if (!props.vaultId || craftingName.value) return
  craftingName.value = recipe.name
  try {
    const result = await craftingService.craft(props.vaultId, recipe.name, props.itemType)
    toast.success(`Crafted ${result.name} (${result.junk_spent} materials, ${result.caps_spent} caps)`)
    await loadRecipes()
    emit('crafted')
  } catch (error) {
    toast.error(getErrorMessage(error) || `Failed to craft ${recipe.name}`)
  } finally {
    craftingName.value = null
  }
}

function costLabel(recipe: CraftingRecipe): string {
  const parts = [`${recipe.junk_cost} junk`]
  if (recipe.caps_cost > 0) parts.push(`${recipe.caps_cost} caps`)
  return parts.join(' · ')
}

onMounted(loadRecipes)
watch(() => [props.vaultId, props.itemType], loadRecipes)
</script>

<template>
  <UCard padding="sm" class="crafting-panel font-mono">
    <div class="mb-3 flex items-center gap-3 border-b border-theme-primary/30 pb-2">
      <Icon :icon="itemIcon" class="h-5 w-5 shrink-0 text-theme-primary" />
      <span class="text-xs font-semibold uppercase tracking-wider text-theme-primary">
        {{ workshopLabel }}
      </span>
      <span class="ml-auto text-xs text-theme-accent/80">
        {{ craftableCount }}/{{ recipes.length }} craftable
      </span>
    </div>

    <p v-if="isLoading" class="py-6 text-center text-sm text-theme-primary/70">Loading schematics…</p>

    <p v-else-if="recipes.length === 0" class="py-6 text-center text-sm text-theme-primary/70">
      No craftable {{ itemType }}s are catalogued.
    </p>

    <ul v-else class="max-h-72 space-y-2 overflow-y-auto pr-1">
      <li
        v-for="recipe in recipes"
        :key="recipe.name"
        class="flex items-center gap-3 rounded-sm border border-theme-primary/20 bg-surface-sunken/60 px-3 py-2"
      >
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2">
            <span class="truncate text-sm font-bold" :class="getRarityTextClass(recipe.rarity)">
              {{ recipe.name }}
            </span>
            <span class="shrink-0 text-[0.65rem] uppercase tracking-wider text-theme-primary/50">
              {{ recipe.rarity }}
            </span>
          </div>
          <div class="mt-0.5 flex items-center gap-2 text-xs text-theme-primary/70">
            <Icon icon="mdi:wrench" class="h-3.5 w-3.5 shrink-0" />
            <span>{{ costLabel(recipe) }}</span>
            <span v-if="recipe.missing_junk > 0" class="text-danger/80">
              (missing {{ recipe.missing_junk }} scrap)
            </span>
          </div>
        </div>
        <UButton
          variant="primary"
          size="sm"
          class="shrink-0"
          :disabled="!recipe.can_craft || craftingName !== null"
          :title="recipe.can_craft ? `Craft ${recipe.name}` : 'Not enough materials'"
          @click="handleCraft(recipe)"
        >
          <Icon
            :icon="craftingName === recipe.name ? 'mdi:loading' : 'mdi:hammer'"
            class="h-4 w-4"
            :class="{ 'animate-spin': craftingName === recipe.name }"
          />
          Craft
        </UButton>
      </li>
    </ul>

    <p class="mt-2 text-[0.7rem] text-theme-primary/50">
      Materials come from scrapping gear and wasteland salvage. Higher-rarity schematics accept lower-grade scrap.
    </p>
  </UCard>
</template>

<style scoped>
.crafting-panel {
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 30%, transparent);
}
</style>
