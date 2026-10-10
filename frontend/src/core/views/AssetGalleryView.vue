<script setup lang="ts">
/**
 * AssetGalleryView — dev-only visual mockup for the item/dweller image backfill.
 *
 * Renders every catalog weapon, outfit and dweller template with its resolved
 * image on one page so missing art (null URLs) and generic fallbacks stand out.
 * Data comes from the authenticated read_data endpoints; log in first.
 */
import { computed, onMounted, ref } from 'vue'
import { apiGet } from '@/core/utils/api'

import { getStaticImageUrl } from '@/core/utils/image'
import { Badge } from '@/core/components/ui/badge'
import { Card, CardContent } from '@/core/components/ui/card'
import { Input } from '@/core/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/core/components/ui/tabs'
import type { components } from '@/core/types/api.generated'

type Weapon = components['schemas']['WeaponCreate']
type Outfit = components['schemas']['OutfitCreate']
type DwellerTemplate = components['schemas']['DwellerCreateWithoutVaultID']
type Junk = components['schemas']['JunkCreate']

const weapons = ref<Weapon[]>([])
const outfits = ref<Outfit[]>([])
const dwellers = ref<DwellerTemplate[]>([])
const junks = ref<Junk[]>([])
const failedUrls = ref<Set<string>>(new Set())
const search = ref('')
const activeTab = ref('weapons')
const loadError = ref('')

interface PetEntry {
  name: string
  kind: string
  image: string
}

// Starter plus full FOS breed roster (generated from the wiki pet tables).
const pets: PetEntry[] = [
  { name: 'CX404', kind: 'dog', image: '/static/pet_images/FOS CX404.png' },
  { name: 'Rollerbrain', kind: 'robot', image: '/static/pet_images/FOS Rollerbrain.png' },
  { name: 'Abyssinian', kind: 'cat', image: '/static/pet_images/FOS Abyssinian.png' },
  { name: 'Akita', kind: 'dog', image: '/static/pet_images/FOS Akita.png' },
  { name: 'Alien Drone', kind: 'parrot', image: '/static/pet_images/FOS Alien Drone.png' },
  {
    name: 'American Shorthair',
    kind: 'cat',
    image: '/static/pet_images/FOS American Shorthair.png',
  },
  {
    name: 'Australian Shepherd',
    kind: 'dog',
    image: '/static/pet_images/FOS Australian Shepherd.png',
  },
  { name: 'Belgian Malinois', kind: 'dog', image: '/static/pet_images/FOS Belgian Malinois.png' },
  { name: 'Black Lab', kind: 'dog', image: '/static/pet_images/FOS Black Lab.png' },
  { name: 'Bloodhound', kind: 'dog', image: '/static/pet_images/FOS Bloodhound.png' },
  { name: 'Bombay', kind: 'cat', image: '/static/pet_images/FOS Bombay.png' },
  { name: 'Boxer', kind: 'dog', image: '/static/pet_images/FOS Boxer.png' },
  { name: 'British Shorthair', kind: 'cat', image: '/static/pet_images/FOS British Shorthair.png' },
  { name: 'Brittany', kind: 'dog', image: '/static/pet_images/FOS Brittany.png' },
  { name: 'Burmilla', kind: 'cat', image: '/static/pet_images/FOS Burmilla.png' },
  { name: 'Cattle Dog', kind: 'dog', image: '/static/pet_images/FOS Cattle Dog.png' },
  { name: 'Collie', kind: 'dog', image: '/static/pet_images/FOS Collie.png' },
  { name: 'Dalmatian', kind: 'dog', image: '/static/pet_images/FOS Dalmatian.png' },
  { name: 'Doberman', kind: 'dog', image: '/static/pet_images/FOS Doberman.png' },
  { name: 'English Mastiff', kind: 'dog', image: '/static/pet_images/FOS English Mastiff.png' },
  { name: 'German Pointer', kind: 'dog', image: '/static/pet_images/FOS German Pointer.png' },
  { name: 'German Shepherd', kind: 'dog', image: '/static/pet_images/FOS German Shepherd.png' },
  { name: 'Golden Retriever', kind: 'dog', image: '/static/pet_images/FOS Golden Retriever.png' },
  { name: 'Greyhound', kind: 'dog', image: '/static/pet_images/FOS Greyhound.png' },
  { name: 'Havana Brown', kind: 'cat', image: '/static/pet_images/FOS Havana Brown.png' },
  { name: 'Husky', kind: 'dog', image: '/static/pet_images/FOS Husky.png' },
  { name: 'LaPerm', kind: 'cat', image: '/static/pet_images/FOS LaPerm.png' },
  { name: 'Lykoi', kind: 'cat', image: '/static/pet_images/FOS Lykoi.png' },
  { name: 'Maine Coon', kind: 'cat', image: '/static/pet_images/FOS Maine Coon.png' },
  { name: 'Manx', kind: 'cat', image: '/static/pet_images/FOS Manx.png' },
  { name: 'Ocicat', kind: 'cat', image: '/static/pet_images/FOS Ocicat.png' },
  { name: "Pallas's Cat", kind: 'cat', image: "/static/pet_images/FOS Pallas's Cat.png" },
  { name: 'Persian', kind: 'cat', image: '/static/pet_images/FOS Persian.png' },
  { name: 'Pirate parrot', kind: 'parrot', image: '/static/pet_images/FOS Pirate parrot.png' },
  { name: 'Pit Bull Terrier', kind: 'dog', image: '/static/pet_images/FOS Pit Bull Terrier.png' },
  { name: 'Poodle', kind: 'dog', image: '/static/pet_images/FOS Poodle.png' },
  { name: 'Rottweiler', kind: 'dog', image: '/static/pet_images/FOS Rottweiler.png' },
  { name: 'Scottish Fold', kind: 'cat', image: '/static/pet_images/FOS Scottish Fold.png' },
  { name: 'Siamese', kind: 'cat', image: '/static/pet_images/FOS Siamese.png' },
  { name: 'Somali', kind: 'cat', image: '/static/pet_images/FOS Somali.png' },
  { name: 'Sphynx', kind: 'cat', image: '/static/pet_images/FOS Sphynx.png' },
  { name: 'St. Bernard', kind: 'dog', image: '/static/pet_images/FOS St. Bernard.png' },
  { name: 'Toyger', kind: 'cat', image: '/static/pet_images/FOS Toyger.png' },
  { name: 'Trained parrot', kind: 'parrot', image: '/static/pet_images/FOS Trained parrot.png' },
  { name: 'Turkish Van', kind: 'cat', image: '/static/pet_images/FOS Turkish Van.png' },
  {
    name: 'Vault-Tec parrot',
    kind: 'parrot',
    image: '/static/pet_images/FOS Vault-Tec parrot.png',
  },
]

function markBroken(url: string | null) {
  if (url) failedUrls.value.add(url)
}

function imgOf(url: string | null | undefined): string | null {
  const resolved = getStaticImageUrl(url)
  return resolved && !failedUrls.value.has(resolved) ? resolved : null
}

function isFallbackWeapon(w: Weapon): boolean {
  return (
    (w.image_url ?? '').endsWith('10mm pistol FOS.png') && w.name.toLowerCase() !== '10mm pistol'
  )
}

function dwellerName(d: DwellerTemplate): string {
  return `${d.first_name} ${d.last_name ?? ''}`.trim()
}

function dwellerRace(d: DwellerTemplate): string {
  const attrs = d.visual_attributes as { race?: unknown; state_of_being?: unknown } | null
  const race = typeof attrs?.race === 'string' ? attrs.race : 'human'
  const state = typeof attrs?.state_of_being === 'string' ? ` (${attrs.state_of_being})` : ''
  return `${race}${state}`
}

function outfitBonus(o: Outfit): string {
  const parts = (
    ['strength', 'perception', 'endurance', 'charisma', 'intelligence', 'agility', 'luck'] as const
  )
    .filter((s) => o[s] > 0)
    .map((s) => `+${o[s]} ${s.slice(0, 3).toUpperCase()}`)
  return parts.join(' ') || 'no bonus'
}

function matches(haystack: string): boolean {
  return haystack.toLowerCase().includes(search.value.trim().toLowerCase())
}

const filteredWeapons = computed(() =>
  search.value ? weapons.value.filter((w) => matches(`${w.name} ${w.rarity}`)) : weapons.value
)
const filteredOutfits = computed(() =>
  search.value ? outfits.value.filter((o) => matches(`${o.name} ${o.rarity}`)) : outfits.value
)
const filteredDwellers = computed(() =>
  search.value
    ? dwellers.value.filter((d) => matches(`${dwellerName(d)} ${dwellerRace(d)}`))
    : dwellers.value
)
const filteredJunks = computed(() =>
  search.value ? junks.value.filter((j) => matches(`${j.name} ${j.junk_type}`)) : junks.value
)
const filteredPets = computed(() =>
  search.value ? pets.filter((p) => matches(`${p.name} ${p.kind}`)) : pets
)
const missingCount = computed(
  () =>
    weapons.value.filter((w) => !w.image_url).length +
    outfits.value.filter((o) => !o.image_url).length +
    dwellers.value.filter((d) => !d.image_url).length
)

function setActiveTab(value: unknown) {
  activeTab.value = String(value)
}

onMounted(async () => {
  try {
    const [w, o, d, j] = await Promise.all([
      apiGet<Weapon[]>('/api/v1/weapons/read_data/'),
      apiGet<Outfit[]>('/api/v1/outfits/read_data/'),
      apiGet<DwellerTemplate[]>('/api/v1/dwellers/read_data/'),
      apiGet<Junk[]>('/api/v1/junk/read_data/'),
    ])
    weapons.value = w
    outfits.value = o
    dwellers.value = d
    junks.value = j
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : 'Failed to load catalog data.'
  }
})
</script>

<template>
  <div class="mx-auto max-w-7xl px-6 py-8">
    <h1 class="terminal-glow text-2xl font-bold">Asset gallery <span class="flicker">▮</span></h1>
    <p class="mt-1 text-sm opacity-70">
      {{ weapons.length }} weapons · {{ outfits.length }} outfits · {{ dwellers.length }} dweller
      templates · {{ junks.length }} junk · {{ missingCount }} missing images
    </p>
    <Input v-model="search" placeholder="Filter by name…" class="mt-4 max-w-sm" />
    <p v-if="loadError" class="mt-4 text-sm text-red-400">{{ loadError }}</p>

    <Tabs :model-value="activeTab" @update:model-value="setActiveTab" class="mt-4">
      <TabsList>
        <TabsTrigger value="weapons">Weapons ({{ filteredWeapons.length }})</TabsTrigger>
        <TabsTrigger value="outfits">Outfits ({{ filteredOutfits.length }})</TabsTrigger>
        <TabsTrigger value="dwellers">Dwellers ({{ filteredDwellers.length }})</TabsTrigger>
        <TabsTrigger value="pets">Pets ({{ filteredPets.length }})</TabsTrigger>
        <TabsTrigger value="junk">Junk ({{ filteredJunks.length }})</TabsTrigger>
      </TabsList>

      <TabsContent value="weapons">
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
          <Card v-for="w in filteredWeapons" :key="w.name" class="overflow-hidden">
            <CardContent class="flex flex-col items-center gap-1 p-3">
              <img
                v-if="imgOf(w.image_url)"
                :src="imgOf(w.image_url)!"
                :alt="w.name"
                class="h-20 object-contain"
                loading="lazy"
                @error="markBroken(imgOf(w.image_url))"
              />
              <div v-else class="flex h-20 items-center justify-center text-xs opacity-50">
                no image
              </div>
              <span class="text-center text-xs font-semibold">{{ w.name }}</span>
              <span class="text-[11px] opacity-60"
                >{{ w.damage_min }}–{{ w.damage_max }} · {{ w.stat }}</span
              >
              <span class="flex gap-1">
                <Badge>{{ w.rarity }}</Badge>
                <Badge v-if="isFallbackWeapon(w)" variant="destructive">fallback</Badge>
              </span>
            </CardContent>
          </Card>
        </div>
      </TabsContent>

      <TabsContent value="outfits">
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
          <Card v-for="o in filteredOutfits" :key="o.name" class="overflow-hidden">
            <CardContent class="flex flex-col items-center gap-1 p-3">
              <img
                v-if="imgOf(o.image_url)"
                :src="imgOf(o.image_url)!"
                :alt="o.name"
                class="h-20 object-contain"
                loading="lazy"
                @error="markBroken(imgOf(o.image_url))"
              />
              <div v-else class="flex h-20 items-center justify-center text-xs opacity-50">
                no image
              </div>
              <span class="text-center text-xs font-semibold">{{ o.name }}</span>
              <span class="text-[11px] opacity-60">{{ outfitBonus(o) }}</span>
              <Badge>{{ o.rarity }}</Badge>
            </CardContent>
          </Card>
        </div>
      </TabsContent>

      <TabsContent value="dwellers">
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
          <Card v-for="d in filteredDwellers" :key="dwellerName(d)" class="overflow-hidden">
            <CardContent class="flex flex-col items-center gap-1 p-3">
              <img
                v-if="imgOf(d.image_url)"
                :src="imgOf(d.image_url)!"
                :alt="dwellerName(d)"
                class="h-24 object-contain"
                loading="lazy"
                @error="markBroken(imgOf(d.image_url))"
              />
              <div v-else class="flex h-24 items-center justify-center text-xs opacity-50">
                no image
              </div>
              <span class="text-center text-xs font-semibold">{{ dwellerName(d) }}</span>
              <span class="text-[11px] opacity-60">{{ dwellerRace(d) }}</span>
              <span class="text-[11px] opacity-60"
                >S{{ d.S }} P{{ d.P }} E{{ d.E }} C{{ d.C }} I{{ d.I }} A{{ d.A }} L{{ d.L }}</span
              >
            </CardContent>
          </Card>
        </div>
      </TabsContent>

      <TabsContent value="pets">
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
          <Card v-for="p in filteredPets" :key="p.name" class="overflow-hidden">
            <CardContent class="flex flex-col items-center gap-1 p-3">
              <img
                v-if="imgOf(p.image)"
                :src="imgOf(p.image)!"
                :alt="p.name"
                class="h-24 object-contain"
                loading="lazy"
                @error="markBroken(imgOf(p.image))"
              />
              <div v-else class="flex h-24 items-center justify-center text-xs opacity-50">
                no image
              </div>
              <span class="text-center text-xs font-semibold">{{ p.name }}</span>
              <Badge>{{ p.kind }}</Badge>
            </CardContent>
          </Card>
        </div>
      </TabsContent>

      <TabsContent value="junk">
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
          <Card v-for="j in filteredJunks" :key="j.name" class="overflow-hidden">
            <CardContent class="flex flex-col items-center gap-1 p-3">
              <img
                v-if="imgOf(j.image_url)"
                :src="imgOf(j.image_url)!"
                :alt="j.name"
                class="h-20 object-contain"
                loading="lazy"
                @error="markBroken(imgOf(j.image_url))"
              />
              <div v-else class="flex h-20 items-center justify-center text-xs opacity-50">
                no image
              </div>
              <span class="text-center text-xs font-semibold">{{ j.name }}</span>
              <span class="text-[11px] opacity-60">{{ j.junk_type }}</span>
              <Badge>{{ j.rarity }}</Badge>
            </CardContent>
          </Card>
        </div>
      </TabsContent>
    </Tabs>
  </div>
</template>
