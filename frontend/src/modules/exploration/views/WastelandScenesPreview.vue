<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/core/components/ui/select'
import WastelandScene from '../components/WastelandScene.vue'
import { WASTELAND_SCENES, type WastelandSceneId } from '../models/wastelandScenes'

const selectedScene = ref<WastelandSceneId>('desert_highway')
const artwork = computed(() => WASTELAND_SCENES[selectedScene.value])
const portrait = '/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Female.webp'

function selectScene(value: unknown): void {
  if (typeof value === 'string' && Object.hasOwn(WASTELAND_SCENES, value))
    selectedScene.value = value as WastelandSceneId
}
</script>

<template>
  <main class="mx-auto flex max-w-4xl flex-col gap-6 p-4 font-mono text-theme-primary sm:py-8">
    <header class="flex flex-col gap-3 border-b border-theme-primary/30 pb-4">
      <RouterLink to="/dev" class="w-fit text-sm text-theme-primary underline underline-offset-4">
        Back to development tools
      </RouterLink>
      <p class="text-xs uppercase tracking-widest text-theme-primary/70">
        Vault-Tec expedition terminal
      </p>
      <h1 class="text-2xl font-bold">Wasteland scenes</h1>
      <p class="max-w-2xl text-sm leading-relaxed text-theme-primary/80">
        Compare journey and encounter artwork with the same explorer, reserved frames, and image
        fallbacks.
      </p>
      <div class="max-w-sm">
        <Select :model-value="selectedScene" @update:model-value="selectScene">
          <SelectTrigger aria-label="Preview location" class="w-full">
            <SelectValue placeholder="Choose a location" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem v-for="(scene, key) in WASTELAND_SCENES" :key="key" :value="key">
                {{ scene.label }}
              </SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>
      </div>
    </header>

    <section class="flex flex-col gap-3" aria-labelledby="journey-heading">
      <h2 id="journey-heading" class="text-lg font-bold">Journey / arrival</h2>
      <WastelandScene
        :scene="selectedScene"
        heading="Lucy MacLean's wasteland journey"
        :description="`Last reported location: ${artwork.label}`"
        dweller-name="Lucy MacLean"
        :thumbnail-url="portrait"
      />
    </section>

    <section
      class="mx-auto flex w-full max-w-xl flex-col gap-3"
      aria-labelledby="encounter-heading"
    >
      <h2 id="encounter-heading" class="text-lg font-bold">Encounter framing</h2>
      <WastelandScene
        :scene="selectedScene"
        variant="battleback"
        heading="Encounter backdrop"
        :description="artwork.label"
        compact
        dweller-name="Lucy MacLean"
        :thumbnail-url="portrait"
      />
    </section>
  </main>
</template>
