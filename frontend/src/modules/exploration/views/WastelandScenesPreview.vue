<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { Button } from '@/core/components/ui/button'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/core/components/ui/select'
import WastelandScene from '../components/WastelandScene.vue'
import ExpeditionSiteModal from '../components/ExpeditionSiteModal.vue'
import { useExpeditionSiteStore } from '../stores/expeditionSite'
import { WASTELAND_SCENES, type WastelandSceneId } from '../models/wastelandScenes'

const selectedScene = ref<WastelandSceneId>('desert_highway')
const previewIsCombat = ref(false)
const combatOpen = ref(false)
const artwork = computed(() => WASTELAND_SCENES[selectedScene.value])
const portrait = '/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Female.webp'

function previewCombat(combat = true): void {
  previewIsCombat.value = combat
  const store = useExpeditionSiteStore()
  store.reset()
  store.currentExplorationId = 'preview'
  const desert = selectedScene.value === 'desert_highway'
  const enemy = desert
    ? { id: 'giant-radscorpion#0', name: 'Radscorpion' }
    : selectedScene.value === 'supermarket_interior'
      ? { id: 'raider#0', name: 'Raider' }
      : { id: 'feral-ghoul#0', name: 'Feral Ghoul' }
  store.room = {
    exploration_id: 'preview',
    site_id: 'preview',
    site_name: artwork.value.label,
    room_index: 0,
    room_total: 1,
    room_name: artwork.value.label,
    scene_id: selectedScene.value,
    flavor: 'Read-only preview of the encounter battlefield and journal.',
    lore: 'This preview does not advance a real expedition.',
    threat: 'low',
    node: { kind: 'combat', prompt: 'Preview', enemy_names: [enemy.name], options: [] },
    can_retreat: false,
    status: 'in_room',
    outcome: null,
    finale_paid: false,
    defeated: false,
    dweller_health: 81,
    dweller_max_health: 100,
    combat_state: {
      round: combat ? 16 : 0,
      next_attack_team: 'A',
      fighters: [
        {
          id: 'lucy',
          name: 'Lucy MacLean',
          level: 10,
          health: 81,
          max_health: 100,
          power: 20,
          is_creature: false,
          is_robot: false,
          thumbnail_url: portrait,
          active_skill: {
            name: 'Aimed Shot',
            description: 'Extra attack.',
            icon: 'gun-rifle',
            charge: 80,
            queued: false,
          },
        },
        {
          ...enemy,
          level: 0,
          health: 12,
          max_health: 30,
          power: 10,
          is_creature: true,
          is_robot: false,
        },
      ],
      events: !combat
        ? []
        : Array.from({ length: 30 }, (_, index) => ({
            id: `${index + 1}:0`,
            message: `Lucy ${index % 5 === 0 ? 'uses Aimed Shot' : 'attacks'} · Turn ${index + 1}`,
            action: {
              actor_id: 'lucy',
              actor_body: 'human',
              effect: 'shot',
              skill: index % 5 === 0 ? 'Aimed Shot' : null,
              skill_icon: 'gun-rifle',
              targets: [],
            },
          })),
    },
  }
  combatOpen.value = true
}

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
        One location for the whole encounter. The scene stays fixed while you play and review the
        result.
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
      <Button class="w-fit" @click="previewCombat(false)">Preview briefing</Button>
      <Button class="w-fit" @click="previewCombat(true)">Preview combat layout</Button>
    </header>

    <section class="flex flex-col gap-3" aria-labelledby="encounter-heading">
      <h2 id="encounter-heading" class="text-lg font-bold">Encounter scene</h2>
      <WastelandScene
        :scene="selectedScene"
        variant="battleback"
        heading="Encounter scene"
        :description="artwork.label"
        dweller-name="Lucy MacLean"
        :thumbnail-url="portrait"
      />
    </section>
    <ExpeditionSiteModal
      :show="combatOpen"
      exploration-id="preview"
      :exploration-active="!previewIsCombat"
      dweller-name="Lucy MacLean"
      :dweller-thumbnail-url="portrait"
      pauses-travel
      @close="combatOpen = false"
    >
      <template #footer>
        <Button class="w-full" size="lg" @click="combatOpen = false">Close preview</Button>
      </template>
    </ExpeditionSiteModal>
  </main>
</template>
