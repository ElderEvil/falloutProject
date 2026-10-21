<script setup lang="ts">
import { computed, onMounted, onScopeDispose, onUnmounted, ref, watch } from 'vue'
import { useConfirmDialog } from '@vueuse/core'
import TerminalConfirmation from '@/core/components/common/TerminalConfirmation.vue'
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
import { getItemIcon, getRarityTextClass } from '@/core/models/items'
import { useToast } from '@/core/composables/useToast'
import { useSound } from '@/core/composables/useSound'
import { useNow } from '@/core/composables/useNow'
import { computeRemainingSeconds, formatDuration } from '@/core/utils/time'
import { notifyErrorOnce, getErrorMessage } from '@/core/utils/errorHandler'
import { craftingService } from '../services/craftingService'
import type { CraftableItemType, CraftingOrder, CraftingRecipe } from '../models/crafting'

interface Props {
  vaultId: string
  itemType: CraftableItemType
  crewKey?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  crafted: []
}>()

const toast = useToast()
const { playSound } = useSound()

const recipes = ref<CraftingRecipe[]>([])
const orders = ref<CraftingOrder[]>([])
const isLoading = ref(false)
const busyKey = ref<string | null>(null)
const now = useNow(1000)
let loadSequence = 0
let recheckTimer: number | null = null
let lastRecheck = 0
const RECHECK_MS = 5000

const itemIcon = computed(() =>
  props.itemType === 'theme' ? 'mdi:palette-outline' : getItemIcon(props.itemType, {})
)
const workshopLabel = computed(() =>
  props.itemType === 'weapon'
    ? 'Weapon workshop'
    : props.itemType === 'outfit'
      ? 'Outfit workshop'
      : 'Theme workshop'
)
const startLabel = computed(() => (props.itemType === 'theme' ? 'Craft' : 'Start'))

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
    if (onlyCraftable.value && !recipe.has_junk) return false
    const term = search.value.trim().toLowerCase()
    return term === '' || recipe.name.toLowerCase().includes(term)
  })
)

const isLocked = (recipe: CraftingRecipe) => recipe.unlocked === false
const isOwned = (recipe: CraftingRecipe) => recipe.owned === true

/** "3 common · 3 rare" — what the recipe consumes, by material rarity. */
function materialsLabel(recipe: CraftingRecipe): string {
  return Object.entries(recipe.junk_materials)
    .map(([material, needed]) => `${needed} ${material}`)
    .join(' · ')
}
const craftableCount = computed(() => recipes.value.filter((recipe) => recipe.can_craft).length)
const queue = computed(() =>
  orders.value.filter(
    (order) =>
      order.status !== 'collected' &&
      order.status !== 'cancelled' &&
      order.item_type === props.itemType
  )
)

function remainingSeconds(order: CraftingOrder): number {
  if (order.status !== 'active') return 0
  return computeRemainingSeconds(order.estimated_completion_at, now.value)
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
    notifyErrorOnce(error, getErrorMessage(error) || 'Failed to load the workshop')
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
    playSound('craftStart', 'sfx')
    toast.success(
      `Queued ${order.item_name} (${order.junk_spent} materials, ${order.caps_spent} caps)`
    )
    await loadAll()
    emit('crafted')
  } catch (error) {
    notifyErrorOnce(error, getErrorMessage(error) || `Failed to queue ${recipe.name}`)
  } finally {
    busyKey.value = null
  }
}

const cancelTitle = ref('')
const {
  isRevealed: showCancelConfirmation,
  reveal: revealCancel,
  confirm: confirmCancel,
  cancel: cancelCancellation,
} = useConfirmDialog()
onScopeDispose(cancelCancellation)
watch(
  () => [props.vaultId, props.itemType],
  () => cancelCancellation()
)

async function handleCancel(order: CraftingOrder) {
  if (!props.vaultId || busyKey.value || showCancelConfirmation.value) return
  const vaultId = props.vaultId
  cancelTitle.value = `Cancel ${order.item_name}?`
  const { isCanceled } = await revealCancel()
  if (isCanceled || props.vaultId !== vaultId || busyKey.value) return
  busyKey.value = order.id
  try {
    await craftingService.cancelOrder(vaultId, order.id)
    toast.success(`Cancelled ${order.item_name}; materials refunded.`)
    await loadAll()
  } catch (error) {
    notifyErrorOnce(error, getErrorMessage(error) || `Failed to cancel ${order.item_name}`)
  } finally {
    busyKey.value = null
  }
}

async function handleCollect(order: CraftingOrder) {
  if (!props.vaultId || busyKey.value) return
  busyKey.value = order.id
  try {
    const result = await craftingService.collectOrder(props.vaultId, order.id)
    playSound('success', 'ui')
    toast.success(`Crafted ${result.name}`)
    await loadAll()
    emit('crafted')
  } catch (error) {
    notifyErrorOnce(error, getErrorMessage(error) || `Failed to collect ${order.item_name}`)
  } finally {
    busyKey.value = null
  }
}

onMounted(() => {
  loadAll()
  // The game tick flips an order to completed server-side; re-poll once its
  // timer has elapsed so Collect appears without closing the panel.
  recheckTimer = window.setInterval(() => {
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
  if (recheckTimer) clearInterval(recheckTimer)
})

watch(() => [props.vaultId, props.itemType, props.crewKey], loadAll)
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
                No radiation segment here (the bar carries no `radiation` value);
                shadcn Progress's h-1.5 base matches the previous height=6 and it
                has no glow by default, so the old glow=false is kept implicitly.
              -->
              <Progress :model-value="progressPercent(order)" />
              <span class="w-9 shrink-0 text-right text-xs text-theme-primary">
                {{ progressPercent(order).toFixed(0) }}%
              </span>
              <Button
                v-if="order.status === 'active'"
                variant="destructive"
                size="sm"
                class="shrink-0 border-2 font-mono"
                :disabled="busyKey !== null"
                @click="handleCancel(order)"
              >
                <Icon
                  :icon="busyKey === order.id ? 'mdi:loading' : 'mdi:close'"
                  class="h-4 w-4"
                  :class="{ 'animate-spin': busyKey === order.id }"
                />
                Cancel
              </Button>
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
          <SelectTrigger size="sm" class="text-xs">
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
          <input v-model="onlyCraftable" type="checkbox" class="craftable-checkbox" />
          Have materials
        </Label>
      </div>

      <ul v-if="filteredRecipes.length > 0" class="max-h-64 space-y-2 overflow-y-auto pr-1">
        <li
          v-for="recipe in filteredRecipes"
          :key="recipe.name"
          class="recipe-row rounded-sm border border-theme-primary/20 bg-surface-sunken/60 px-3 py-2"
          :class="{ 'locked-recipe': isLocked(recipe) }"
        >
          <!--
            TooltipProvider delayDuration (200ms) preserves the previous tooltip
            hover delay; reka-ui opens instantly on keyboard focus, which is the
            stronger a11y contract (same pattern as StorageItemCard.vue).
          -->
          <TooltipProvider :delay-duration="200">
            <span :class="['recipe-icon', `recipe-icon-${recipe.item_type}`]">
              <Icon :icon="itemIcon" class="h-6 w-6" :class="getRarityTextClass(recipe.rarity)" />
            </span>
            <div class="flex min-w-0 flex-1 items-center gap-2">
              <span
                v-if="isLocked(recipe)"
                class="flex shrink-0 items-center text-warning"
                :title="recipe.unlock_hint ?? 'Recipe locked'"
              >
                <Icon icon="mdi:lock" class="h-3.5 w-3.5" />
              </span>
              <span class="truncate text-sm font-bold" :class="getRarityTextClass(recipe.rarity)">
                {{ recipe.name }}
              </span>
              <span class="recipe-meta">{{ recipe.rarity }}</span>
              <span v-if="isOwned(recipe)" class="recipe-meta text-theme-accent">Crafted</span>
            </div>
            <div class="recipe-details">
              <span class="recipe-materials">
                <span class="flex shrink-0 items-center gap-1 opacity-80">
                  <Tooltip v-for="junkType in recipe.junk_types" :key="junkType">
                    <TooltipTrigger as-child>
                      <Icon :icon="junkTypeMeta(junkType).icon" class="h-4 w-4" />
                    </TooltipTrigger>
                    <TooltipContent>{{ junkTypeMeta(junkType).label }}</TooltipContent>
                  </Tooltip>
                </span>
                <span
                  v-for="(needed, material) in recipe.junk_materials"
                  :key="material"
                  class="flex shrink-0 items-center gap-1"
                  :class="{
                    'text-danger/80': (recipe.available_junk[material] ?? 0) < needed,
                  }"
                >
                  <Icon icon="mdi:wrench" class="h-4 w-4" />
                  {{ recipe.available_junk[material] ?? 0 }}/{{ needed }} {{ material }}
                </span>
              </span>
              <span class="recipe-speed">
                <span class="flex shrink-0 items-center gap-1 text-theme-accent/80">
                  <Icon :icon="statMeta(recipe.stat).icon" class="h-4 w-4" />
                  {{ statMeta(recipe.stat).label }} {{ recipe.ability_sum }}
                </span>
                <span class="flex shrink-0 items-center gap-1">
                  <Icon icon="mdi:clock-outline" class="h-4 w-4" />
                  {{ formatDuration(recipe.duration_seconds, { rounding: 'round' }) }}
                </span>
              </span>
            </div>
            <Tooltip>
              <TooltipTrigger as-child>
                <Button
                  variant="default"
                  size="sm"
                  class="shrink-0 border-2 border-theme-primary font-mono"
                  :disabled="
                    isLocked(recipe) || isOwned(recipe) || !recipe.can_craft || busyKey !== null
                  "
                  @click="handleStart(recipe)"
                >
                  <Icon
                    :icon="
                      busyKey === recipe.name
                        ? 'mdi:loading'
                        : isOwned(recipe)
                          ? 'mdi:check'
                          : 'mdi:hammer'
                    "
                    class="h-4 w-4"
                    :class="{ 'animate-spin': busyKey === recipe.name }"
                  />
                  {{ isOwned(recipe) ? 'Crafted' : startLabel }}
                </Button>
              </TooltipTrigger>
              <TooltipContent>{{
                isOwned(recipe)
                  ? 'Already crafted'
                  : isLocked(recipe)
                    ? (recipe.unlock_hint ?? 'Recipe locked')
                    : recipe.can_craft
                      ? `Queue ${recipe.name}`
                      : materialsLabel(recipe)
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
        finish orders faster. Locked schematics are learned by scrapping the matching item.
      </p>
    </template>
  </Card>
  <TerminalConfirmation
    :open="showCancelConfirmation"
    :title="cancelTitle"
    message="Spent materials will be refunded."
    confirm-label="Cancel crafting"
    @confirm="confirmCancel()"
    @cancel="cancelCancellation()"
  />
</template>

<style scoped>
.crafting-panel {
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 30%, transparent);
}

.recipe-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.recipe-icon {
  display: inline-flex;
  flex-shrink: 0;
}

.recipe-details {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 0.75rem;
  color: color-mix(in srgb, var(--color-theme-primary) 70%, transparent);
  font-size: 0.75rem;
}

.recipe-materials,
.recipe-speed {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.recipe-speed {
  padding-left: 0.75rem;
  border-left: 1px solid color-mix(in srgb, var(--color-theme-primary) 25%, transparent);
}

.recipe-meta {
  flex-shrink: 0;
  color: color-mix(in srgb, var(--color-theme-primary) 50%, transparent);
  font-size: 0.65rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.queue-ready {
  border-color: color-mix(in srgb, var(--color-theme-accent) 60%, transparent);
}

@media (max-width: 720px) {
  .recipe-row {
    flex-wrap: wrap;
  }

  .recipe-details {
    order: 3;
    width: 100%;
    flex-wrap: wrap;
  }
}

.locked-recipe {
  opacity: 0.65;
  border-style: dashed;
}

.craftable-checkbox {
  appearance: none;
  width: 0.875rem;
  height: 0.875rem;
  flex-shrink: 0;
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 60%, transparent);
  border-radius: 2px;
  background: var(--color-surface-sunken);
  cursor: pointer;
  transition:
    background-color 0.15s ease,
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.craftable-checkbox:hover {
  border-color: var(--color-theme-primary);
}

.craftable-checkbox:checked {
  background-color: var(--color-theme-primary);
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 8px var(--color-theme-glow);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='none' stroke='%23000' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3.5 8.5l3 3 6-7'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: center;
  background-size: 0.7rem;
}

.craftable-checkbox:focus-visible {
  outline: 2px solid var(--color-theme-primary);
  outline-offset: 2px;
}
</style>
