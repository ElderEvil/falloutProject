<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { Badge } from '@/core/components/ui/badge'
import { Button } from '@/core/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/core/components/ui/card'
import { useToast } from '@/core/composables/useToast'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useAuthStore } from '@/modules/auth/stores/auth'
import DwellerAgeBadge from '@/modules/dwellers/components/DwellerAgeBadge.vue'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import {
  formatIdentityLabel,
  getDwellerDisplayName,
  isMature,
  type DwellerShort,
} from '@/modules/dwellers/models/dweller'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import type { Room } from '../models/room'
import {
  BARBERSHOP_HAIR_COLORS,
  BARBERSHOP_SKIN_TONES,
  humanPortraitVariantUrls,
  normalizeHairColor,
  normalizeSkinTone,
  type BarbershopStatus,
} from '../models/barbershop'
import { changeBarbershopAppearance, fetchBarbershopStatus } from '../services/barbershopService'

const props = defineProps<{
  room: Room
  vaultId: string
  assignedDwellers: DwellerShort[]
}>()

const emit = defineEmits<{
  changed: []
}>()

const authStore = useAuthStore()
const { filter: filterStore, generation } = useDwellerStore()
const toast = useToast()

const token = computed(() => (typeof authStore.token === 'string' ? authStore.token : ''))

const status = ref<BarbershopStatus | null>(null)
const isLoadingStatus = ref(false)
const isLoadingDwellers = ref(false)
const selectedDwellerId = ref<string | null>(null)
const skinTone = ref<string>('Pale')
const hairColor = ref<string>('Brown')
const saving = ref(false)
const generating = ref(false)
const inlineError = ref<string | null>(null)
const portraitVersion = ref(0)

const SKIN_SWATCH_CLASS: Record<string, string> = {
  Pale: 'bg-theme-primary/10',
  Tan: 'bg-theme-primary/30',
  Brown: 'bg-theme-primary/60',
  Ebony: 'bg-theme-primary/90',
}

const HAIR_SWATCH_CLASS: Record<string, string> = {
  Blonde: 'bg-theme-primary/20',
  Brunette: 'bg-theme-primary/40',
  Black: 'bg-terminal-background',
  Brown: 'bg-theme-primary/60',
  Red: 'bg-theme-primary/80',
  Gray: 'bg-theme-primary/30',
}

const swatchClass = (map: Record<string, string>, value: string): string =>
  map[value] ?? 'bg-theme-primary/30'

const eligibleDwellers = computed(() =>
  filterStore.allDwellers.filter(
    (dweller) =>
      isMature(dweller) &&
      dweller.status !== 'dead' &&
      (dweller.visual_attributes?.race ?? 'human') === 'human'
  )
)

const selectedDweller = computed(
  () => eligibleDwellers.value.find((dweller) => dweller.id === selectedDwellerId.value) ?? null
)

const isElder = computed(() => selectedDweller.value?.age_group === 'elder')
const isDefaultPortrait = computed(() => selectedDweller.value?.is_default_portrait === true)

const skinToneOptions = computed(() => {
  const source = status.value?.skin_tones?.length ? status.value.skin_tones : BARBERSHOP_SKIN_TONES
  return [...new Set(source.map((tone) => normalizeSkinTone(tone)))]
})

const hairColorOptions = computed(() => {
  const source = status.value?.hair_colors?.length
    ? status.value.hair_colors
    : BARBERSHOP_HAIR_COLORS
  return [...new Set(source.map((color) => normalizeHairColor(color, 'adult')))]
})

const variantUrls = computed(() => {
  const dweller = selectedDweller.value
  if (!dweller || !isDefaultPortrait.value) return null
  return humanPortraitVariantUrls(
    dweller.gender,
    dweller.age_group,
    skinTone.value,
    hairColor.value
  )
})

function withCacheBust(url: string | null | undefined, version: number): string | null {
  if (!url) return null
  if (version <= 0) return url
  return `${url}${url.includes('?') ? '&' : '?'}v=${version}`
}

const customPortraitUrl = computed(() =>
  withCacheBust(selectedDweller.value?.thumbnail_url, portraitVersion.value)
)

const previewImageUrl = computed(() =>
  isDefaultPortrait.value
    ? (variantUrls.value?.imageUrl ?? selectedDweller.value?.thumbnail_url ?? null)
    : customPortraitUrl.value
)

const previewThumbnailUrl = computed(() =>
  isDefaultPortrait.value
    ? (variantUrls.value?.thumbnailUrl ?? selectedDweller.value?.thumbnail_url ?? null)
    : customPortraitUrl.value
)

const capsSufficient = computed(() => (status.value?.vault_caps ?? 0) >= (status.value?.fee ?? 0))

const canSave = computed(
  () =>
    !!status.value?.staffed &&
    !!selectedDweller.value &&
    !saving.value &&
    !generating.value &&
    capsSufficient.value
)

const canRegenerate = computed(
  () => !!status.value?.staffed && !!selectedDweller.value && !saving.value && !generating.value
)

watch(
  eligibleDwellers,
  (dwellers) => {
    const current = selectedDwellerId.value
    if (current && dwellers.some((dweller) => dweller.id === current)) return
    selectedDwellerId.value = dwellers[0]?.id ?? null
  },
  { immediate: true }
)

watch(
  () => selectedDweller.value?.id,
  () => {
    const dweller = selectedDweller.value
    if (!dweller) return
    skinTone.value = normalizeSkinTone(dweller.visual_attributes?.skin_tone)
    hairColor.value =
      dweller.age_group === 'elder'
        ? 'Gray'
        : normalizeHairColor(dweller.visual_attributes?.hair_color, dweller.age_group)
    portraitVersion.value = 0
    inlineError.value = null
  },
  { immediate: true }
)

async function loadStatus(): Promise<void> {
  if (!props.room.id || !token.value) return
  isLoadingStatus.value = true
  try {
    status.value = await fetchBarbershopStatus(props.room.id, token.value)
  } catch (error) {
    status.value = null
    inlineError.value = handleStoreError(error, 'Failed to load the Barbershop')
  } finally {
    isLoadingStatus.value = false
  }
}

async function loadDwellers(): Promise<void> {
  if (!props.vaultId || !token.value) return
  isLoadingDwellers.value = true
  try {
    await filterStore.fetchAllDwellers(props.vaultId, token.value)
  } catch (error) {
    inlineError.value = handleStoreError(error, 'Failed to load vault dwellers')
  } finally {
    isLoadingDwellers.value = false
  }
}

function reload(): void {
  inlineError.value = null
  void loadStatus()
  void loadDwellers()
}

watch(
  [() => props.room.id, () => props.vaultId, token],
  () => {
    status.value = null
    reload()
  },
  { immediate: true }
)

function patchPortraitSnapshot(
  dwellerId: string,
  thumbnailUrl: string | null | undefined,
  isDefaultPortrait: boolean | undefined
): void {
  const update = (list: DwellerShort[]) => {
    const index = list.findIndex((dweller) => dweller.id === dwellerId)
    const entry = list[index]
    if (!entry) return
    list[index] = {
      ...entry,
      thumbnail_url: thumbnailUrl ?? null,
      ...(isDefaultPortrait === undefined ? {} : { is_default_portrait: isDefaultPortrait }),
    }
  }
  update(filterStore.allDwellers)
  update(filterStore.dwellers)
}

async function handleSave(): Promise<void> {
  const dweller = selectedDweller.value
  const current = status.value
  if (!dweller || !current || !canSave.value) return

  saving.value = true
  inlineError.value = null
  try {
    const response = await changeBarbershopAppearance(
      props.room.id,
      dweller.id,
      { skin_tone: skinTone.value, hair_color: hairColor.value },
      token.value
    )
    filterStore.detailedDwellers[dweller.id] = response.dweller
    patchPortraitSnapshot(
      dweller.id,
      response.dweller.thumbnail_url,
      response.dweller.is_default_portrait
    )
    status.value = { ...current, vault_caps: response.remaining_caps }
    emit('changed')
    toast.success(`${getDwellerDisplayName(dweller)} leaves the chair looking sharp.`)
    if (!response.portrait_updated) {
      toast.info('Custom portrait kept. Only skin tone and hair color changed.')
    }
  } catch (error) {
    inlineError.value = handleStoreError(error, 'Failed to change appearance')
  } finally {
    saving.value = false
  }
}

async function handleRegenerate(): Promise<void> {
  const dweller = selectedDweller.value
  if (!dweller || !canRegenerate.value) return

  generating.value = true
  inlineError.value = null
  try {
    const generated = await generation.generateDwellerPortrait(dweller.id, token.value)
    if (!generated) return
    const refreshed = await filterStore.fetchDwellerDetails(dweller.id, token.value, true)
    const updated = refreshed ?? generated
    filterStore.detailedDwellers[dweller.id] = updated
    patchPortraitSnapshot(dweller.id, updated.thumbnail_url, updated.is_default_portrait)
    portraitVersion.value += 1
    emit('changed')
  } catch (error) {
    inlineError.value = handleStoreError(error, 'Failed to regenerate the portrait')
  } finally {
    generating.value = false
  }
}
</script>

<template>
  <section class="barbershop-panel flex flex-col gap-4" aria-label="Barbershop appearance studio">
    <Card class="border border-theme-primary/30 bg-terminal-background">
      <CardHeader class="gap-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <CardTitle class="flex items-center gap-2 text-base text-theme-primary">
            <Icon icon="mdi:content-cut" class="h-4 w-4" :ariaHidden="true" />
            Appearance Studio
          </CardTitle>
          <!-- @vue-ignore -->
          <Badge
            variant="outline"
            class="border-theme-primary/40 text-theme-primary/80"
            data-testid="barbershop-staffing"
          >
            {{ status ? (status.staffed ? 'Staffed' : 'Unstaffed') : '—' }}
          </Badge>
        </div>
        <p class="text-xs leading-relaxed text-theme-primary/65">
          Pick a human adult or elder and swap a preset skin tone and hair color. The fee is charged
          from the vault's caps when the change saves.
        </p>
        <dl class="grid grid-cols-3 gap-2 text-center">
          <div class="rounded border border-theme-primary/20 bg-surface-sunken px-2 py-1.5">
            <dt class="text-[0.6rem] tracking-wider text-theme-primary/60 uppercase">Fee</dt>
            <!-- @vue-ignore -->
            <dd class="text-sm font-bold text-theme-primary" data-testid="barbershop-fee">
              {{ status ? `${status.fee} caps` : '—' }}
            </dd>
          </div>
          <div class="rounded border border-theme-primary/20 bg-surface-sunken px-2 py-1.5">
            <dt class="text-[0.6rem] tracking-wider text-theme-primary/60 uppercase">Vault caps</dt>
            <!-- @vue-ignore -->
            <dd class="text-sm font-bold text-theme-primary" data-testid="barbershop-caps">
              {{ status?.vault_caps ?? '—' }}
            </dd>
          </div>
          <div class="rounded border border-theme-primary/20 bg-surface-sunken px-2 py-1.5">
            <dt class="text-[0.6rem] tracking-wider text-theme-primary/60 uppercase">Chair</dt>
            <!-- @vue-ignore -->
            <dd class="text-sm font-bold text-theme-primary" data-testid="barbershop-chair">
              {{ status ? (status.staffed ? 'Ready' : 'Empty') : '—' }}
            </dd>
          </div>
        </dl>
      </CardHeader>

      <CardContent class="flex flex-col gap-4">
        <!-- @vue-ignore -->
        <p
          v-if="!status && isLoadingStatus"
          class="text-xs text-theme-primary/60"
          data-testid="barbershop-loading"
        >
          Reading Barbershop records…
        </p>

        <!-- @vue-ignore -->
        <div
          v-if="inlineError"
          role="alert"
          class="flex flex-wrap items-center justify-between gap-2 rounded border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger"
          data-testid="barbershop-error"
        >
          <span>{{ inlineError }}</span>
          <!-- @vue-ignore -->
          <Button
            type="button"
            variant="outline"
            size="xs"
            class="border-danger/40 text-danger hover:bg-danger/10"
            data-testid="barbershop-retry"
            @click="reload"
          >
            Retry
          </Button>
        </div>

        <!-- @vue-ignore -->
        <p
          v-if="status && !status.staffed"
          class="rounded border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning"
          data-testid="barbershop-unstaffed"
        >
          Assign at least one dweller to the Barbershop first.
        </p>

        <!-- @vue-ignore -->
        <p
          v-else-if="isLoadingDwellers"
          class="text-xs text-theme-primary/60"
          data-testid="barbershop-roster-loading"
        >
          Reading dweller records…
        </p>

        <!-- @vue-ignore -->
        <p
          v-else-if="status && !eligibleDwellers.length"
          class="rounded border border-theme-primary/20 bg-surface-sunken px-3 py-2 text-xs text-theme-primary/60"
          data-testid="barbershop-empty"
        >
          No adult human dwellers are available for a trim.
        </p>

        <!-- @vue-ignore -->
        <div
          v-if="status && eligibleDwellers.length"
          class="grid gap-4 sm:grid-cols-2"
          data-testid="barbershop-workspace"
        >
          <div class="flex min-w-0 flex-col gap-4">
            <div class="flex flex-col gap-2">
              <h4 class="text-xs font-semibold tracking-wider text-theme-primary/70 uppercase">
                Dwellers
              </h4>
              <div class="flex max-h-64 flex-col gap-1.5 overflow-y-auto pr-1">
                <!-- @vue-ignore -->
                <Button
                  v-for="dweller in eligibleDwellers"
                  :key="dweller.id"
                  type="button"
                  variant="ghost"
                  class="h-auto w-full justify-start gap-3 rounded border border-theme-primary/20 bg-surface-sunken px-2 py-1.5 text-left hover:bg-theme-primary/10"
                  :class="{
                    'border-theme-primary bg-theme-primary/10': selectedDwellerId === dweller.id,
                  }"
                  :aria-pressed="selectedDwellerId === dweller.id"
                  data-testid="barbershop-dweller-row"
                  :data-dweller-id="dweller.id"
                  @click="selectedDwellerId = dweller.id"
                >
                  <DwellerPortrait
                    :image-url="dweller.thumbnail_url"
                    :thumbnail-url="dweller.thumbnail_url"
                    :alt="`${getDwellerDisplayName(dweller)} portrait`"
                    prefer-thumbnail
                    image-class="h-10 w-10 object-cover"
                    fallback-class="h-6 w-6 text-theme-primary/60"
                  />
                  <span class="flex min-w-0 flex-col items-start gap-1">
                    <span class="w-full truncate text-sm font-semibold text-theme-primary">
                      {{ getDwellerDisplayName(dweller) }}
                    </span>
                    <span class="flex flex-wrap items-center gap-1.5 text-theme-primary/60">
                      <DwellerAgeBadge :age-group="dweller.age_group" size="sm" show-label />
                      <span class="text-[0.65rem] tracking-wide uppercase">
                        Level {{ dweller.level }}
                      </span>
                    </span>
                  </span>
                </Button>
              </div>
            </div>

            <div class="flex flex-col gap-2" role="group" aria-label="Skin tone">
              <h4 class="text-xs font-semibold tracking-wider text-theme-primary/70 uppercase">
                Skin tone
              </h4>
              <div class="flex flex-wrap gap-1.5">
                <!-- @vue-ignore -->
                <Button
                  v-for="tone in skinToneOptions"
                  :key="tone"
                  type="button"
                  variant="outline"
                  size="sm"
                  class="gap-1.5 border-theme-primary/25 bg-surface-sunken text-xs text-theme-primary hover:bg-theme-primary/10"
                  :class="{ 'border-theme-primary bg-theme-primary/15': skinTone === tone }"
                  :aria-pressed="skinTone === tone"
                  data-testid="barbershop-skin-swatch"
                  :data-value="tone"
                  @click="skinTone = tone"
                >
                  <span
                    class="h-3 w-3 rounded-full border border-theme-primary/50"
                    :class="swatchClass(SKIN_SWATCH_CLASS, tone)"
                    aria-hidden="true"
                  />
                  {{ formatIdentityLabel(tone) }}
                </Button>
              </div>
            </div>

            <div class="flex flex-col gap-2" role="group" aria-label="Hair color">
              <div class="flex items-center justify-between gap-2">
                <h4 class="text-xs font-semibold tracking-wider text-theme-primary/70 uppercase">
                  Hair color
                </h4>
                <span v-if="isElder" class="text-[0.65rem] text-theme-primary/55">
                  Elders keep silver hair.
                </span>
              </div>
              <div class="flex flex-wrap gap-1.5">
                <!-- @vue-ignore -->
                <Button
                  v-for="hair in hairColorOptions"
                  :key="hair"
                  type="button"
                  variant="outline"
                  size="sm"
                  class="gap-1.5 border-theme-primary/25 bg-surface-sunken text-xs text-theme-primary hover:bg-theme-primary/10"
                  :class="{ 'border-theme-primary bg-theme-primary/15': hairColor === hair }"
                  :aria-pressed="hairColor === hair"
                  :disabled="isElder"
                  data-testid="barbershop-hair-swatch"
                  :data-value="hair"
                  @click="hairColor = hair"
                >
                  <span
                    class="h-3 w-3 rounded-full border border-theme-primary/50"
                    :class="swatchClass(HAIR_SWATCH_CLASS, hair)"
                    aria-hidden="true"
                  />
                  {{ formatIdentityLabel(hair) }}
                </Button>
              </div>
            </div>
          </div>

          <div class="flex min-w-0 flex-col gap-3">
            <div
              class="mx-auto flex h-56 w-full max-w-48 items-center justify-center overflow-hidden rounded border border-theme-primary/25 bg-surface-sunken"
            >
              <!-- @vue-ignore -->
              <div data-testid="barbershop-portrait" class="h-full w-full">
                <DwellerPortrait
                  :image-url="previewImageUrl"
                  :thumbnail-url="previewThumbnailUrl"
                  :alt="
                    selectedDweller
                      ? `${getDwellerDisplayName(selectedDweller)} preview`
                      : 'Preview'
                  "
                  :prefer-thumbnail="!isDefaultPortrait"
                  image-class="h-full w-full object-contain"
                  fallback-class="h-16 w-16 text-theme-primary/40"
                />
              </div>
            </div>

            <div v-if="selectedDweller" class="flex flex-col gap-1 text-xs">
              <p class="font-semibold text-theme-primary">
                {{ getDwellerDisplayName(selectedDweller) }}
              </p>
              <p class="text-theme-primary/60">
                {{ formatIdentityLabel(skinTone) }} skin · {{ formatIdentityLabel(hairColor) }} hair
              </p>
              <p v-if="!isDefaultPortrait" class="text-theme-primary/55">
                Custom portrait preserved when saving.
              </p>
            </div>

            <div class="flex flex-col gap-2">
              <!-- @vue-ignore -->
              <Button
                type="button"
                variant="default"
                size="sm"
                class="w-full bg-theme-primary text-terminal-background hover:bg-theme-primary/80"
                :disabled="!canSave || saving"
                data-testid="barbershop-save"
                @click="handleSave"
              >
                <Icon icon="mdi:content-save-outline" class="h-4 w-4" :ariaHidden="true" />
                {{ saving ? 'Saving…' : `Save appearance (${status?.fee ?? 0} caps)` }}
              </Button>

              <!-- @vue-ignore -->
              <Button
                type="button"
                variant="outline"
                size="sm"
                class="w-full border-theme-primary/40 text-theme-primary hover:bg-theme-primary/10"
                :disabled="!canRegenerate || generating"
                data-testid="barbershop-regenerate"
                @click="handleRegenerate"
              >
                <Icon icon="mdi:auto-fix" class="h-4 w-4" :ariaHidden="true" />
                {{
                  generating
                    ? 'Regenerating…'
                    : isDefaultPortrait
                      ? 'Generate custom portrait'
                      : 'Regenerate custom portrait'
                }}
              </Button>

              <p v-if="!capsSufficient" class="text-[0.65rem] text-warning">
                This change costs {{ status?.fee ?? 0 }} caps, but the vault holds
                {{ status?.vault_caps ?? 0 }}.
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  </section>
</template>
