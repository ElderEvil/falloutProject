<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import type { AcceptableValue } from 'reka-ui'
import { Button } from '@/core/components/ui/button'
import { Card } from '@/core/components/ui/card'
import { Input } from '@/core/components/ui/input'
import { Label } from '@/core/components/ui/label'
import { Progress } from '@/core/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/core/components/ui/select'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/core/components/ui/tooltip'
import { getRarityTextClass } from '@/core/models/items'
import { useToast } from '@/core/composables/useToast'
import { getErrorMessage } from '@/core/utils/errorHandler'
import { craftingService } from '../services/craftingService'
import type { CraftableItemType, CraftingOrder, CraftingRecipe } from '../models/crafting'

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
const orders = ref<CraftingOrder[]>([])
const isLoading = ref(false)
const busyKey = ref<string | null>(null)
const now = ref(Date.now())
let loadSequence = 0
let ticker: number | null = null
let lastRecheck = 0
const RECHECK_MS = 5000

const itemIcon = computed(() =>
  props.itemType === 'weapon' ? 'mdi:sword-cross' : 'mdi:tshirt-crew'
)
const workshopLabel = computed(() =>
  props.itemType === 'weapon' ? 'Weapon workshop' : 'Outfit workshop'
)

const STAT_META: Record<string, { icon: string; label: string }> = {
  strength: { icon: 'mdi:arm-flex', label: 'STR' },
  perception: { icon: 'mdi:eye', label: 'PER' },
  endurance: { icon: 'mdi:heart', label: 'END' },
  charisma: { icon: 'mdi:account-voice', label: 'CHA' },
  intelligence: { icon: 'mdi:brain', label: 'INT' },
  agility: { icon: 'mdi:run-fast', label: 'AGI' },
  luck: { icon: 'mdi:clover', label: 'LUK' },
}

const statMeta = (stat: string) =>
  STAT_META[stat.toLowerCase()] ?? { icon: 'mdi:star', label: stat.toUpperCase() }

const JUNK_TYPE_META: Record<string, { icon: string; label: string }> = {
  circuitry: { icon: 'mdi:chip', label: 'Circuitry' },
  leather: { icon: 'mdi:bag-personal', label: 'Leather' },
  adhesive: { icon: 'mdi:tape', label: 'Adhesive' },
  cloth: { icon: 'mdi:tshirt-crew-outline', label: 'Cloth' },
  science: { icon: 'mdi:flask', label: 'Science' },
  steel: { icon: 'mdi:anvil', label: 'Steel' },
  valuables: { icon: 'mdi:diamond-stone', label: 'Valuables' },
}

const junkTypeMeta = (junkType: string) =>
  JUNK_TYPE_META[junkType.toLowerCase()] ?? { icon: 'mdi:wrench', label: junkType }

const RARITY_FILTERS = ['all', 'common', 'rare', 'legendary'] as const
const rarityFilter = ref<(typeof RARITY_FILTERS)[number]>('all')
// reka-ui's Select modelValue is AcceptableValue (nullable); the filter is a
// strict string-literal union, so bridge at the Select boundary.
const rarityFilterSelect = computed<AcceptableValue>({
  get: () => rarityFilter.value,
  set: (value: AcceptableValue) => {
    if (value !== null) rarityFilter.value = value as (typeof RARITY_FILTERS)[number]
  },
})
const onlyCraftable = ref(false)
const search = ref('')

const filteredRecipes = computed(() =>
  recipes.value.filter((recipe) => {
    if (rarityFilter.value !== 'all' && recipe.rarity !== rarityFilter.value) return false
    if (onlyCraftable.value && !recipe.can_craft) return false
    const term = search.value.trim().toLowerCase()
    return term === '' || recipe.name.toLowerCase().includes(term)
  })
)

function formatDuration(seconds: number): string {
  if (seconds >= 3600) {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.round((seconds % 3600) / 60)
    return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`
  }
  return `${Math.max(1, Math.round(seconds / 60))}m`
}

/** "3 common · 3 rare" — what the recipe consumes, by material rarity. */
function materialsLabel(recipe: CraftingRecipe): string {
  return Object.entries(recipe.junk_materials)
    .map(([material, needed]) => `${needed} ${material}`)
    .join(' · ')
}
const craftableCount = computed(() => recipes.value.filter((recipe) => recipe.can_craft).length)
const queue = computed(() =>
  orders.value.filter((order) => order.status !== 'collected' && order.item_type === props.itemType)
)

function remainingSeconds(order: CraftingOrder): number {
  if (order.status !== 'active') return 0
  const endsAt = new Date(`${order.estimated_completion_at}Z`).getTime()
  return Math.max(0, Math.round((endsAt - now.value) / 1000))
}

function remainingLabel(order: CraftingOrder): string {
  if (order.status === 'completed') return 'Ready to collect'
  const seconds = remainingSeconds(order)
  if (seconds <= 0) return 'Waiting for the vault clock…'
  if (seconds >= 60) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
  return `${seconds}s`
}

// Live bar so the queue visibly fills between ticks, matching the training cards.
function progressPercent(order: CraftingOrder): number {
  const started = new Date(`${order.started_at}Z`).getTime()
  const endsAt = new Date(`${order.estimated_completion_at}Z`).getTime()
  const total = endsAt - started
  const live = total > 0 ? ((now.value - started) / total) * 100 : 0
  return Math.min(100, Math.max(order.progress * 100, live))
}

async function loadAll() {
  if (!props.vaultId) return
  const sequence = ++loadSequence
  isLoading.value = true
  try {
    const [loadedRecipes, loadedOrders] = await Promise.all([
      craftingService.listRecipes(props.vaultId, props.itemType),
      craftingService.listOrders(props.vaultId),
    ])
    if (sequence !== loadSequence) return
    recipes.value = loadedRecipes
    orders.value = loadedOrders
  } catch (error) {
    if (sequence !== loadSequence) return
    toast.error(getErrorMessage(error) || 'Failed to load the workshop')
    recipes.value = []
    orders.value = []
  } finally {
    if (sequence === loadSequence) isLoading.value = false
  }
}

async function handleStart(recipe: CraftingRecipe) {
  if (!props.vaultId || busyKey.value) return
  busyKey.value = recipe.name
  try {
    const order = await craftingService.startOrder(props.vaultId, recipe.name, props.itemType)
    toast.success(
      `Queued ${order.item_name} (${order.junk_spent} materials, ${order.caps_spent} caps)`
    )
    await loadAll()
    emit('crafted')
  } catch (error) {
    toast.error(getErrorMessage(error) || `Failed to queue ${recipe.name}`)
  } finally {
    busyKey.value = null
  }
}

async function handleCollect(order: CraftingOrder) {
  if (!props.vaultId || busyKey.value) return
  busyKey.value = order.id
  try {
    const result = await craftingService.collectOrder(props.vaultId, order.id)
    toast.success(`Crafted ${result.name}`)
    await loadAll()
    emit('crafted')
  } catch (error) {
    toast.error(getErrorMessage(error) || `Failed to collect ${order.item_name}`)
  } finally {
    busyKey.value = null
  }
}

onMounted(() => {
  loadAll()
  ticker = window.setInterval(() => {
    now.value = Date.now()
    // The game tick flips an order to completed server-side; re-poll once its
    // timer has elapsed so Collect appears without closing the panel.
    if (
      Date.now() - lastRecheck > RECHECK_MS &&
      queue.value.some((order) => remainingSeconds(order) === 0 && order.status === 'active')
    ) {
      lastRecheck = Date.now()
      loadAll()
    }
  }, 1000)
})

onUnmounted(() => {
  if (ticker) clearInterval(ticker)
})

watch(() => [props.vaultId, props.itemType], loadAll)
</script>

<template>
  <Card class="crafting-panel font-mono gap-0 p-4 rounded-lg ring-0 shadow-none">
    <div class="mb-3 flex items-center gap-3 border-b border-theme-primary/30 pb-2">
      <Icon :icon="itemIcon" class="h-5 w-5 shrink-0 text-theme-primary" />
      <span class="text-xs font-semibold uppercase tracking-wider text-theme-primary">
        {{ workshopLabel }}
      </span>
      <span class="ml-auto text-xs text-theme-accent/80">
        {{ craftableCount }}/{{ recipes.length }} craftable
      </span>
    </div>

    <p v-if="isLoading" class="py-6 text-center text-sm text-theme-primary/70">
      Loading schematics…
    </p>

    <template v-else>
      <section v-if="queue.length > 0" class="mb-3">
        <h4 class="mb-2 text-[0.7rem] font-bold uppercase tracking-widest text-theme-primary/70">
          Queue
        </h4>
        <ul class="space-y-2">
          <li
            v-for="order in queue"
            :key="order.id"
            class="rounded-sm border border-theme-primary/20 bg-surface-sunken/60 px-3 py-2"
            :class="{ 'queue-ready': order.status === 'completed' }"
          >
            <div class="flex items-center gap-2">
              <span class="truncate text-sm font-bold" :class="getRarityTextClass(order.rarity)">
                {{ order.item_name }}
              </span>
              <span class="flex shrink-0 items-center gap-1 text-xs text-theme-accent/80">
                <Icon :icon="statMeta(order.required_stat).icon" class="h-3.5 w-3.5" />
                {{ statMeta(order.required_stat).label }} {{ order.ability_sum_at_start }}
              </span>
              <span class="ml-auto shrink-0 text-xs text-theme-primary/70">{{
                remainingLabel(order)
              }}</span>
            </div>
            <div class="mt-1.5 flex items-center gap-2">
              <!--
                UProgressBar's radiation segment is not used here (no `radiation`
                prop); shadcn Progress's h-1.5 base matches the old height=6 and
                it has no glow by default, so glow=false is preserved implicitly.
              -->
              <Progress :model-value="progressPercent(order)" />
              <span class="w-9 shrink-0 text-right text-xs text-theme-primary">
                {{ progressPercent(order).toFixed(0) }}%
              </span>
              <Button
                v-if="order.status === 'completed'"
                variant="default"
                size="sm"
                class="shrink-0 border-2 border-theme-primary font-mono"
                :disabled="busyKey !== null"
                @click="handleCollect(order)"
              >
                <Icon
                  :icon="busyKey === order.id ? 'mdi:loading' : 'mdi:package-down'"
                  class="h-4 w-4"
                  :class="{ 'animate-spin': busyKey === order.id }"
                />
                Collect
              </Button>
            </div>
          </li>
        </ul>
      </section>

      <p v-if="recipes.length === 0" class="py-6 text-center text-sm text-theme-primary/70">
        No craftable {{ itemType }}s are catalogued.
      </p>

      <div v-else class="mb-2 flex flex-wrap items-center gap-2 text-xs">
        <Input
          v-model="search"
          type="search"
          placeholder="Search schematics…"
          class="min-w-32 h-auto flex-1 rounded-sm border-theme-primary/30 bg-surface-sunken/60 px-2 py-1 text-xs text-theme-primary placeholder:text-theme-primary/40"
        />
        <Select v-model="rarityFilterSelect">
          <SelectTrigger
            class="h-auto rounded-sm border-theme-primary/30 bg-surface-sunken/60 px-2 py-1 text-xs text-theme-primary data-[size=default]:h-auto"
          >
            <SelectValue placeholder="All rarities" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem v-for="rarity in RARITY_FILTERS" :key="rarity" :value="rarity">
              {{ rarity === 'all' ? 'All rarities' : rarity }}
            </SelectItem>
          </SelectContent>
        </Select>
        <!--
          The checkbox stays a raw input: shadcn's Input is a text-field primitive
          (string modelValue) and the kit has no checkbox primitive, so a boolean
          toggle would type-error and mis-style. The Label wraps it, which is the
          a11y-correct association.
        -->
        <Label class="gap-1.5 text-xs text-theme-primary/80">
          <input v-model="onlyCraftable" type="checkbox" />
          Craftable now
        </Label>
      </div>

      <ul v-if="filteredRecipes.length > 0" class="max-h-64 space-y-2 overflow-y-auto pr-1">
        <li
          v-for="recipe in filteredRecipes"
          :key="recipe.name"
          class="flex items-center gap-3 rounded-sm border border-theme-primary/20 bg-surface-sunken/60 px-3 py-2"
        >
          <!--
            TooltipProvider delayDuration (200ms) matches the old UTooltip hover
            delay; reka-ui opens instantly on keyboard focus, which is the
            stronger a11y contract (same pattern as StorageItemCard.vue).
          -->
          <TooltipProvider :delay-duration="200">
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="truncate text-sm font-bold" :class="getRarityTextClass(recipe.rarity)">
                  {{ recipe.name }}
                </span>
                <span
                  class="shrink-0 text-[0.65rem] uppercase tracking-wider text-theme-primary/50"
                >
                  {{ recipe.rarity }}
                </span>
                <span class="ml-auto flex shrink-0 items-center gap-1 text-theme-accent/80">
                  <Icon :icon="statMeta(recipe.stat).icon" class="h-3.5 w-3.5" />
                  {{ statMeta(recipe.stat).label }} {{ recipe.ability_sum }}
                </span>
              </div>
              <div
                class="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-theme-primary/70"
              >
                <span
                  v-for="(needed, material) in recipe.junk_materials"
                  :key="material"
                  class="flex items-center gap-1"
                  :class="{
                    'text-danger/80': (recipe.available_junk[material] ?? 0) < needed,
                  }"
                >
                  <Icon icon="mdi:wrench" class="h-3.5 w-3.5 shrink-0" />
                  {{ recipe.available_junk[material] ?? 0 }}/{{ needed }} {{ material }}
                </span>
                <span class="flex items-center gap-1 opacity-80">
                  <Tooltip v-for="junkType in recipe.junk_types" :key="junkType">
                    <TooltipTrigger as-child>
                      <Icon :icon="junkTypeMeta(junkType).icon" class="h-3.5 w-3.5 shrink-0" />
                    </TooltipTrigger>
                    <TooltipContent>{{ junkTypeMeta(junkType).label }}</TooltipContent>
                  </Tooltip>
                </span>
                <span class="flex items-center gap-1">
                  <Icon icon="mdi:clock-outline" class="h-3.5 w-3.5 shrink-0" />
                  {{ formatDuration(recipe.duration_seconds) }}
                </span>
              </div>
            </div>
            <Tooltip>
              <TooltipTrigger as-child>
                <Button
                  variant="default"
                  size="sm"
                  class="shrink-0 border-2 border-theme-primary font-mono"
                  :disabled="!recipe.can_craft || busyKey !== null"
                  @click="handleStart(recipe)"
                >
                  <Icon
                    :icon="busyKey === recipe.name ? 'mdi:loading' : 'mdi:hammer'"
                    class="h-4 w-4"
                    :class="{ 'animate-spin': busyKey === recipe.name }"
                  />
                  Start
                </Button>
              </TooltipTrigger>
              <TooltipContent>{{
                recipe.can_craft ? `Queue ${recipe.name}` : materialsLabel(recipe)
              }}</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </li>
      </ul>

      <p v-else class="py-4 text-center text-sm text-theme-primary/70">
        No schematics match those filters.
      </p>

      <p class="mt-2 text-[0.7rem] text-theme-primary/50">
        Materials come from scrapping gear and wasteland salvage. Dwellers working the workshop
        finish orders faster.
      </p>
    </template>
  </Card>
</template>

<style scoped>
.crafting-panel {
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 30%, transparent);
}

.queue-ready {
  border-color: color-mix(in srgb, var(--color-theme-accent) 60%, transparent);
}
</style>
