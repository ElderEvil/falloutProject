<script setup lang="ts">
import { computed, nextTick, onScopeDispose, ref, watch } from 'vue'
import { X } from '@lucide/vue'
import { Input } from '@/core/components/ui/input'
import RoomPreviewSection from './RoomPreviewSection.vue'
import { getTrainingRoomCapacity } from '../utils/room'
import { Icon } from '@iconify/vue'
import { Badge } from '@/core/components/ui/badge'
import { Button } from '@/core/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/core/components/ui/card'
import { useToast } from '@/core/composables/useToast'
import { getErrorMessage, handleStoreError } from '@/core/utils/errorHandler'
import { useAuthStore } from '@/modules/auth/stores/auth'
import DwellerAgeBadge from '@/modules/dwellers/components/DwellerAgeBadge.vue'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import {
  formatIdentityLabel,
  getDwellerDisplayName,
  isMature,
  isAvailableUnassignedDweller,
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
  roomImageUrl?: string | null
}>()

const emit = defineEmits<{
  changed: []
}>()

const authStore = useAuthStore()
const { filter: filterStore, generation, management } = useDwellerStore()
const toast = useToast()

const token = computed(() => (typeof authStore.token === 'string' ? authStore.token : ''))

const status = ref<BarbershopStatus | null>(null)
const isLoadingStatus = ref(false)
const roster = ref<DwellerShort[]>([...props.assignedDwellers])
const barberId = ref<string | null>(null)
const clientId = ref<string | null>(null)
const activeSlot = ref<'worker' | 'client' | null>(null)
const search = ref('')
const pickerLoading = ref(false)
const pickerError = ref<string | null>(null)
const slotError = ref<string | null>(null)
const picker = ref<HTMLElement | null>(null)
const assigning = ref(false)
let statusRequest = 0
let contextVersion = 0
onScopeDispose(() => {
  contextVersion += 1
  statusRequest += 1
})
let initializedRoles = false
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

const barberCandidates = computed(() =>
  roster.value.filter((dweller) => isMature(dweller) && dweller.status !== 'dead')
)

const clientCandidates = computed(() =>
  roster.value.filter(
    (dweller) =>
      isMature(dweller) &&
      dweller.status !== 'dead' &&
      (dweller.visual_attributes?.race ?? 'human') === 'human'
  )
)

const barber = computed(
  () => barberCandidates.value.find((dweller) => dweller.id === barberId.value) ?? null
)

const availableClients = computed(() =>
  clientCandidates.value.filter((dweller) => dweller.id !== barberId.value)
)

const selectedDweller = computed(
  () => availableClients.value.find((dweller) => dweller.id === clientId.value) ?? null
)

const waitingClients = computed(() =>
  availableClients.value.filter((dweller) => dweller.id !== clientId.value)
)

const currentSkinTone = computed(() =>
  normalizeSkinTone(selectedDweller.value?.visual_attributes?.skin_tone)
)

const currentHairColor = computed(() =>
  normalizeHairColor(
    selectedDweller.value?.visual_attributes?.hair_color,
    selectedDweller.value?.age_group
  )
)

const skinChanged = computed(
  () => !!selectedDweller.value && skinTone.value !== currentSkinTone.value
)
const hairChanged = computed(
  () => !!selectedDweller.value && hairColor.value !== currentHairColor.value
)
const hasAppearanceChange = computed(() => skinChanged.value || hairChanged.value)

const changeFee = computed(() => {
  if (!status.value) return 0
  return (
    (skinChanged.value ? status.value.skin_fee : 0) +
    (hairChanged.value ? status.value.hair_fee : 0)
  )
})

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

const capsSufficient = computed(() => (status.value?.vault_caps ?? 0) >= changeFee.value)

const canSave = computed(
  () =>
    !!status.value?.staffed &&
    !!barber.value &&
    !!selectedDweller.value &&
    hasAppearanceChange.value &&
    !saving.value &&
    !assigning.value &&
    !generating.value &&
    capsSufficient.value
)

const canRegenerate = computed(
  () =>
    !!status.value?.staffed &&
    !!barber.value &&
    !!selectedDweller.value &&
    !saving.value &&
    !assigning.value &&
    !generating.value
)

watch(
  [() => props.room.id, () => props.vaultId, () => props.assignedDwellers],
  ([roomId, vaultId, dwellers], previous) => {
    // Parent assignments follow sidebar filters; keep known occupants outside that view.
    const visibleIds = new Set(filterStore.dwellers.map((entry) => entry.id))
    const hidden =
      previous?.[0] === roomId && previous?.[1] === vaultId
        ? roster.value.filter((entry) => !visibleIds.has(entry.id))
        : []
    roster.value = [...new Map([...hidden, ...dwellers].map((entry) => [entry.id, entry])).values()]
  },
  { immediate: true, deep: true }
)

watch(
  roster,
  (dwellers) => {
    if (!initializedRoles) {
      barberId.value = barberCandidates.value[0]?.id ?? null
      clientId.value =
        clientCandidates.value.find((entry) => entry.id !== barberId.value)?.id ?? null
      initializedRoles = true
    } else {
      if (!dwellers.some((entry) => entry.id === barberId.value)) barberId.value = null
      if (!dwellers.some((entry) => entry.id === clientId.value)) clientId.value = null
    }
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

function selectBarber(dwellerId: string): void {
  const previousBarberId = barberId.value
  barberId.value = dwellerId

  if (clientId.value !== dwellerId) return
  const available = clientCandidates.value.filter((dweller) => dweller.id !== dwellerId)
  const preferred = available.find((dweller) => dweller.id !== previousBarberId)
  clientId.value = preferred?.id ?? available[0]?.id ?? null
}

function selectClient(dwellerId: string): void {
  clientId.value = dwellerId
}

async function loadStatus(): Promise<void> {
  const request = ++statusRequest
  const roomId = props.room.id
  const authToken = token.value
  if (!roomId || !authToken) return
  isLoadingStatus.value = true
  try {
    const result = await fetchBarbershopStatus(roomId, authToken)
    if (request !== statusRequest) return
    status.value = result
  } catch (error) {
    if (request !== statusRequest) return
    status.value = null
    inlineError.value = handleStoreError(error, 'Failed to load the Barbershop')
  } finally {
    if (request === statusRequest) isLoadingStatus.value = false
  }
}

function reload(): void {
  inlineError.value = null
  void loadStatus()
}

watch(
  [() => props.room.id, () => props.vaultId, token],
  () => {
    contextVersion += 1
    status.value = null
    isLoadingStatus.value = false
    saving.value = false
    generating.value = false
    activeSlot.value = null
    pickerLoading.value = false
    pickerError.value = null
    slotError.value = null
    assigning.value = false
    barberId.value = barberCandidates.value[0]?.id ?? null
    clientId.value = clientCandidates.value.find((entry) => entry.id !== barberId.value)?.id ?? null
    reload()
  },
  { immediate: true }
)

function patchPortraitSnapshot(
  dwellerId: string,
  thumbnailUrl: string | null | undefined,
  isDefaultPortrait: boolean | undefined,
  visualAttributes?: DwellerShort['visual_attributes']
): void {
  const update = (list: DwellerShort[]) => {
    const index = list.findIndex((dweller) => dweller.id === dwellerId)
    const entry = list[index]
    if (!entry) return
    list[index] = {
      ...entry,
      thumbnail_url: thumbnailUrl ?? null,
      ...(isDefaultPortrait === undefined ? {} : { is_default_portrait: isDefaultPortrait }),
      ...(visualAttributes === undefined ? {} : { visual_attributes: visualAttributes }),
    }
  }
  update(roster.value)
  update(filterStore.allDwellers)
  update(filterStore.dwellers)
}

const busy = computed(() => assigning.value || saving.value || generating.value)
const slotOptions = computed(() => {
  if (pickerLoading.value || pickerError.value) return []
  const candidates = new Map(roster.value.map((entry) => [entry.id, entry]))
  if (roster.value.length < getTrainingRoomCapacity(props.room)) {
    for (const entry of filterStore.allDwellers) {
      if (isAvailableUnassignedDweller(entry)) candidates.set(entry.id, entry)
    }
  }
  return [...candidates.values()].filter(
    (entry) =>
      isMature(entry) &&
      entry.status !== 'dead' &&
      (activeSlot.value === 'worker' ||
        ((entry.visual_attributes?.race ?? 'human') === 'human' && entry.id !== barberId.value)) &&
      getDwellerDisplayName(entry).toLowerCase().includes(search.value.trim().toLowerCase())
  )
})
const openSlot = async (role: 'worker' | 'client') => {
  activeSlot.value = role
  search.value = ''
  slotError.value = null
  pickerError.value = null
  pickerLoading.value = true
  const version = contextVersion
  await nextTick()
  picker.value?.querySelector('input')?.focus()
  try {
    await filterStore.fetchAllDwellers(props.vaultId, token.value, true)
    if (version === contextVersion)
      roster.value = filterStore.allDwellers.filter((entry) => entry.room_id === props.room.id)
  } catch (error) {
    if (version === contextVersion)
      pickerError.value = getErrorMessage(error, 'Could not load dwellers')
  } finally {
    if (version === contextVersion) pickerLoading.value = false
  }
}
const closeSlot = async () => {
  if (busy.value) return
  const role = activeSlot.value
  activeSlot.value = null
  await nextTick()
  if (role)
    document
      .getElementById(`barbershop-${props.room.id}-${role}${role === 'worker' ? '-1' : ''}`)
      ?.focus()
}
async function chooseSlot(entry: DwellerShort): Promise<void> {
  const role = activeSlot.value
  if (!role || busy.value) return
  const roomId = props.room.id
  const authToken = token.value
  const version = contextVersion
  assigning.value = true
  slotError.value = null
  try {
    if (!roster.value.some((dweller) => dweller.id === entry.id)) {
      const assigned = await management.assignDwellerToRoom(entry.id, roomId, authToken)
      if (version !== contextVersion) return
      if (!roster.value.some((dweller) => dweller.id === entry.id))
        roster.value.push({ ...entry, room_id: roomId, status: assigned.status })
      emit('changed')
    }
    if (role === 'worker') selectBarber(entry.id)
    else selectClient(entry.id)
    await loadStatus()
    if (version !== contextVersion) return
    assigning.value = false
    await closeSlot()
  } catch (error) {
    if (version === contextVersion)
      slotError.value = getErrorMessage(error, 'Failed to assign dweller')
  } finally {
    if (version === contextVersion) assigning.value = false
  }
}
async function removeOccupant(dwellerId: string): Promise<void> {
  const entry = roster.value.find((dweller) => dweller.id === dwellerId)
  if (!entry || busy.value) return
  const role = entry.id === barberId.value ? 'worker' : 'client'
  const roomId = props.room.id
  const authToken = token.value
  const version = contextVersion
  assigning.value = true
  slotError.value = null
  try {
    await management.unassignDwellerFromRoom(entry.id, authToken)
    if (version !== contextVersion) return
    roster.value = roster.value.filter((dweller) => dweller.id !== entry.id)
    emit('changed')
    await loadStatus()
    if (version !== contextVersion) return
    assigning.value = false
    await nextTick()
    document.getElementById(`barbershop-${roomId}-${role}${role === 'worker' ? '-1' : ''}`)?.focus()
  } catch (error) {
    if (version === contextVersion)
      slotError.value = getErrorMessage(error, 'Failed to unassign dweller')
  } finally {
    if (version === contextVersion) assigning.value = false
  }
}

async function handleSave(): Promise<void> {
  const dweller = selectedDweller.value
  const current = status.value
  if (!dweller || !current || !canSave.value) return

  const version = contextVersion
  saving.value = true
  inlineError.value = null
  try {
    const response = await changeBarbershopAppearance(
      props.room.id,
      dweller.id,
      { skin_tone: skinTone.value, hair_color: hairColor.value },
      token.value
    )
    if (version !== contextVersion) return
    filterStore.detailedDwellers[dweller.id] = response.dweller
    patchPortraitSnapshot(
      dweller.id,
      response.dweller.thumbnail_url,
      response.dweller.is_default_portrait,
      response.dweller.visual_attributes as DwellerShort['visual_attributes']
    )
    status.value = { ...current, vault_caps: response.remaining_caps }
    emit('changed')
    toast.success(`${getDwellerDisplayName(dweller)} leaves the chair looking sharp.`)
    if (!response.portrait_updated) {
      toast.info('Custom portrait kept. Only skin tone and hair color changed.')
    }
  } catch (error) {
    if (version === contextVersion)
      inlineError.value = handleStoreError(error, 'Failed to change appearance')
  } finally {
    if (version === contextVersion) saving.value = false
  }
}

async function handleRegenerate(): Promise<void> {
  const dweller = selectedDweller.value
  if (!dweller || !canRegenerate.value) return

  const version = contextVersion
  generating.value = true
  inlineError.value = null
  try {
    const generated = await generation.generateDwellerPortrait(dweller.id, token.value)
    if (!generated || version !== contextVersion) return
    const refreshed = await filterStore.fetchDwellerDetails(dweller.id, token.value, true)
    if (version !== contextVersion) return
    const updated = refreshed ?? generated
    filterStore.detailedDwellers[dweller.id] = updated
    patchPortraitSnapshot(dweller.id, updated.thumbnail_url, updated.is_default_portrait)
    portraitVersion.value += 1
    emit('changed')
  } catch (error) {
    if (version === contextVersion)
      inlineError.value = handleStoreError(error, 'Failed to regenerate the portrait')
  } finally {
    if (version === contextVersion) generating.value = false
  }
}
</script>

<template>
  <section class="barbershop-panel flex flex-col gap-4" aria-label="Barbershop appearance studio">
    <RoomPreviewSection
      class="barbershop-scene"
      :room-name="room.name"
      :image-url="room.image_url ?? null"
      :room-image-url="roomImageUrl ?? null"
      :room-units="3"
      :dweller-capacity="1"
      :assigned-dwellers="barber ? [barber] : []"
      :client-slot="selectedDweller"
      :selection-mode="true"
      :assign-enabled="!busy"
      :slot-id-prefix="`barbershop-${room.id}`"
      @assign-worker="openSlot('worker')"
      @assign-client="openSlot('client')"
      @unassign="removeOccupant"
    />
    <p
      v-if="slotError"
      role="alert"
      class="rounded border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger"
    >
      {{ slotError }}
    </p>
    <section
      v-if="activeSlot"
      ref="picker"
      :aria-label="`Choose ${activeSlot}`"
      class="flex flex-col gap-2 rounded border border-theme-primary/30 bg-surface-sunken p-3"
      @keydown.esc.prevent.stop="closeSlot()"
    >
      <div class="flex items-center gap-2">
        <label class="min-w-0 flex-1 text-xs text-muted-foreground"
          >Choose {{ activeSlot
          }}<Input v-model="search" type="search" placeholder="Search dwellers…"
        /></label>
        <Button
          size="icon-sm"
          variant="ghost"
          aria-label="Close slot picker"
          :disabled="busy"
          @click="closeSlot()"
          ><X
        /></Button>
      </div>
      <p class="text-xs text-muted-foreground">
        {{
          activeSlot === 'client'
            ? 'Human adults and elders. The worker cannot be the client.'
            : 'Any adult or elder can work here.'
        }}
      </p>
      <div class="grid max-h-56 gap-1 overflow-y-auto sm:grid-cols-2">
        <!-- @vue-ignore -->
        <Button
          v-for="candidate in slotOptions"
          :key="candidate.id"
          variant="ghost"
          :disabled="busy"
          :data-testid="
            activeSlot === 'worker' ? 'barbershop-barber-option' : 'barbershop-client-option'
          "
          :data-dweller-id="candidate.id"
          class="h-auto min-w-0 justify-start gap-2 whitespace-normal p-2 text-left"
          @click="chooseSlot(candidate)"
        >
          <DwellerPortrait
            :thumbnail-url="candidate.thumbnail_url"
            :alt="getDwellerDisplayName(candidate)"
            prefer-thumbnail
            image-class="size-9 shrink-0 rounded object-cover"
            fallback-class="size-9 shrink-0"
          />
          <span class="flex min-w-0 flex-col"
            ><span class="truncate text-xs">{{ getDwellerDisplayName(candidate) }}</span
            ><span class="text-[10px] text-muted-foreground">{{
              roster.some((entry) => entry.id === candidate.id)
                ? 'In Barbershop'
                : 'Available · joins Barbershop'
            }}</span></span
          >
        </Button>
      </div>
      <p v-if="pickerLoading" role="status" class="text-xs text-muted-foreground">
        Loading dwellers…
      </p>
      <div
        v-else-if="pickerError"
        role="alert"
        class="flex items-center justify-between gap-2 text-xs text-danger"
      >
        {{ pickerError
        }}<Button variant="outline" size="xs" @click="openSlot(activeSlot)">Retry dwellers</Button>
      </div>
      <p v-else-if="!slotOptions.length" class="text-xs text-muted-foreground">
        No eligible dwellers available. Room assignments still use the Barbershop's capacity.
      </p>
    </section>
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
          Choose a worker and a human client in the preview. Available dwellers join this room when
          selected. Only appearance changes are charged.
        </p>
        <dl class="grid grid-cols-2 gap-2 text-center sm:grid-cols-4">
          <div class="rounded border border-theme-primary/20 bg-surface-sunken px-2 py-1.5">
            <dt class="text-[0.6rem] tracking-wider text-theme-primary/60 uppercase">Skin</dt>
            <!-- @vue-ignore -->
            <dd class="text-sm font-bold text-theme-primary" data-testid="barbershop-skin-fee">
              {{ status ? `${status.skin_fee} caps` : '—' }}
            </dd>
          </div>
          <div class="rounded border border-theme-primary/20 bg-surface-sunken px-2 py-1.5">
            <dt class="text-[0.6rem] tracking-wider text-theme-primary/60 uppercase">Hair</dt>
            <!-- @vue-ignore -->
            <dd class="text-sm font-bold text-theme-primary" data-testid="barbershop-hair-fee">
              {{ status ? `${status.hair_fee} caps` : '—' }}
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
              {{
                status
                  ? barber && selectedDweller
                    ? 'Ready'
                    : status.staffed
                      ? 'Pair needed'
                      : 'Empty'
                  : '—'
              }}
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
          v-else-if="status && !barberCandidates.length"
          class="rounded border border-theme-primary/20 bg-surface-sunken px-3 py-2 text-xs text-theme-primary/60"
          data-testid="barbershop-empty-barber"
        >
          Assign an adult barber to the Barbershop.
        </p>

        <!-- @vue-ignore -->
        <p
          v-else-if="status && !availableClients.length"
          class="rounded border border-theme-primary/20 bg-surface-sunken px-3 py-2 text-xs text-theme-primary/60"
          data-testid="barbershop-empty-client"
        >
          Assign a human customer to the Barbershop to complete the pair.
        </p>

        <div
          v-if="waitingClients.length"
          class="flex flex-wrap items-center gap-2"
          aria-label="Waiting clients"
        >
          <span class="text-xs text-muted-foreground">Waiting clients</span>
          <!-- @vue-ignore -->
          <Button
            v-for="candidate in waitingClients"
            :key="candidate.id"
            size="sm"
            variant="outline"
            :disabled="busy"
            data-testid="barbershop-waiting-row"
            :data-dweller-id="candidate.id"
            @click="selectClient(candidate.id)"
            >{{ getDwellerDisplayName(candidate) }}</Button
          >
        </div>
        <!-- @vue-ignore -->
        <div
          v-if="status && barberCandidates.length && availableClients.length"
          class="grid gap-4 sm:grid-cols-2"
          data-testid="barbershop-workspace"
        >
          <div class="flex min-w-0 flex-col gap-3">
            <div
              class="mx-auto flex h-64 w-full max-w-56 items-center justify-center overflow-hidden rounded border border-theme-primary/25 bg-surface-sunken"
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
              <p class="text-theme-primary/60">
                <span class="uppercase tracking-wider">Barber</span>
                {{ barber ? getDwellerDisplayName(barber) : '—' }}
              </p>
              <p class="font-semibold text-theme-primary">
                <span class="font-normal text-theme-primary/60 uppercase tracking-wider">
                  Customer
                </span>
                {{ getDwellerDisplayName(selectedDweller) }}
              </p>
              <p class="text-theme-primary/60">
                {{ formatIdentityLabel(skinTone) }} skin · {{ formatIdentityLabel(hairColor) }} hair
              </p>
              <p v-if="!isDefaultPortrait" class="text-theme-primary/55">
                Custom portrait preserved when saving.
              </p>
            </div>
          </div>

          <div class="flex min-w-0 flex-col gap-4">
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

            <div class="rounded border border-theme-primary/20 bg-surface-sunken p-3">
              <div class="flex items-center justify-between gap-2">
                <span class="text-xs tracking-wider text-theme-primary/60 uppercase">
                  Change total
                </span>
                <!-- @vue-ignore -->
                <span
                  class="text-base font-bold text-theme-primary"
                  data-testid="barbershop-change-fee"
                >
                  {{ changeFee }} caps
                </span>
              </div>
              <p class="mt-1 text-[0.65rem] text-theme-primary/55">
                Skin {{ skinChanged ? `+${status?.skin_fee ?? 0}` : '—' }} · Hair
                {{ hairChanged ? `+${status?.hair_fee ?? 0}` : '—' }}
              </p>
              <p v-if="!hasAppearanceChange" class="mt-1 text-[0.65rem] text-theme-primary/55">
                Pick a different skin tone or hair color to enable saving.
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
                {{
                  saving
                    ? 'Saving…'
                    : hasAppearanceChange
                      ? `Save appearance (${changeFee} caps)`
                      : 'No changes to save'
                }}
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

              <!-- @vue-ignore -->
              <p
                v-if="hasAppearanceChange && !capsSufficient"
                class="text-[0.65rem] text-warning"
                data-testid="barbershop-insufficient-caps"
              >
                This change costs {{ changeFee }} caps, but the vault holds
                {{ status?.vault_caps ?? 0 }}.
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  </section>
</template>

<style scoped>
.barbershop-scene :deep(.dweller-sprites-overlay) {
  bottom: 0.75rem;
}
.barbershop-scene :deep(.room-image-frame) {
  width: 100%;
  height: 240px;
  aspect-ratio: auto;
}
</style>
