<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { Icon } from '@iconify/vue'
import type { Dweller, VisualAttributes } from '../models/dweller'

interface Props {
  dweller: Dweller
  modelValue: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: [attributes: VisualAttributes]
}>()

// --- Options data (mirrors backend app/options/) ---
const RACE_OPTIONS = ['human', 'ghoul', 'super_mutant', 'synth'] as const

const STATE_OF_BEING_OPTIONS: Record<string, string[]> = {
  ghoul: ['sane', 'partially_feral', 'fully_feral'],
  super_mutant: ['mild_mutation', 'severe_mutation', 'behemoth'],
  synth: ['gen_3', 'gen_2', 'gen_1'],
}

const FACTION_OPTIONS: Record<string, string[]> = {
  human: [
    'vault_dweller',
    'brotherhood_of_steel',
    'enclave',
    'minutemen',
    'raiders',
    'super_mutant_tribe',
    'children_of_atom',
    'the_institute',
    'railroad',
    'ncr',
    'caesars_legion',
    'none',
  ],
  ghoul: ['vault_dweller', 'raiders', 'children_of_atom', 'none'],
  super_mutant: ['super_mutant_tribe', 'raiders', 'none'],
  synth: ['the_institute', 'railroad', 'none'],
}

// Race-filtered appearance options (mirrors app/options/appearance.py)
const SKIN_TONE_OPTIONS: Record<string, string[]> = {
  human: ['Pale', 'Light', 'Tan', 'Brown', 'Dark Brown', 'Ebony'],
  ghoul: ['Pale Grey', 'Ashen', 'Mottled', 'Necrotic', 'Glowing'],
  super_mutant: ['Light Green', 'Green', 'Dark Green', 'Olive Green'],
  synth: ['Synthetic Fair', 'Synthetic Dark', 'Metallic Silver', 'Exposed Component'],
}

const BUILD_OPTIONS: Record<string, string[]> = {
  human: ['Slim', 'Athletic', 'Muscular', 'Stocky', 'Average', 'Overweight'],
  ghoul: ['Skeletal', 'Withered', 'Twisted'],
  super_mutant: ['Muscular', 'Brutish', 'Towering'],
  synth: ['Slender', 'Muscular', 'Armored'],
}

const HAIRCUT_OPTIONS: Record<string, string[]> = {
  human: [
    'Short Hair',
    'Long Hair',
    'Ponytail',
    'Mohawk',
    'Buzz Cut',
    'Curly Hair',
    'Bun',
    'Braided Hair',
    'Wavy Hair',
    'Dreadlocks',
  ],
  ghoul: [
    'Patchy Hair',
    'Stringy Hair',
    'Messy Hair',
    'Mohawk',
    'Burned Scalp',
    'Radiation-Scarred',
    'Thinning Hair',
    'Wispy Remains',
  ],
  super_mutant: [
    'Bald',
    'Scalp Ridges',
    'Patchy Tufts',
    'Mohawk',
    'Thick Stubble',
    'War Paint Scalp',
  ],
  synth: [
    'Clean Cut',
    'Slicked Back',
    'Military Precision Cut',
    'Exposed Circuits',
    'Synthetic Fiber Weave',
    'Metallic Sheen Hair',
  ],
}

const HEADGEAR_OPTIONS: Record<string, string[]> = {
  human: [
    'Baseball Cap',
    'Bandana',
    'Combat Helmet',
    'Gas Mask',
    'Cowboy Hat',
    'Bowler Hat',
    'Fedora',
    'Ushanka',
    'Beanie',
    'Military Beret',
    'Newsboy Cap',
    'Vault-Tec Helmet',
    'Hooded Coat',
  ],
  ghoul: [
    'Tattered Bandana',
    'Raider Cage Mask',
    'Wrapped Head Bandages',
    'Radiation Suit Hood',
    'Scrapped Metal Helmet',
    'Faded Cap',
    'Glowing One Crown',
    'Leather Hood',
  ],
  super_mutant: [
    'Metal Helmet',
    'Spiked Helmet',
    'Chain Headdress',
    'Skull Trophy',
    'Heavy Plate Helmet',
    'Makeshift Face Guard',
    'Mutant Battle Helm',
  ],
  synth: [
    'Institute Hood',
    'Metallic Plating',
    'Stealth Field Generator',
    'Neural Interface Helmet',
    'Courser Hood',
    'Synth Component Display',
    'Reinforced Circuitry Cap',
  ],
}

// Universal options
const HEIGHT_OPTIONS = ['tall', 'average', 'short'] as const
const EYE_COLOR_OPTIONS = ['blue', 'green', 'brown', 'hazel', 'gray'] as const
const HAIR_COLORS = [
  'blonde',
  'brunette',
  'black',
  'brown',
  'red',
  'gray',
  'white',
  'blue',
  'green',
  'pink',
] as const
const EXPRESSIONS = [
  'neutral',
  'smiling',
  'laughing',
  'proud',
  'sad',
  'angry',
  'frustrated',
  'shocked',
  'terrified',
  'determined',
  'heroic',
  'stoic',
  'skeptical',
  'suspicious',
  'confused',
  'awkward',
  'mischievous',
  'flirty',
] as const
const POSE_OPTIONS = [
  'Standing confidently',
  'Combat ready',
  'Checking Pip-Boy',
  'Faction salute',
  'Alert and wary',
  'Action shot',
  'Stealth crouch',
  'Power armor stance',
  'Wounded but resilient',
  'Weapon drawn',
  'Scavenging through debris',
] as const
const BACKGROUND_OPTIONS = [
  'Vault Interior',
  'Wasteland Ruins',
  'Brotherhood Airship',
  'Super Mutant Camp',
  'Nuclear Crater',
  'Pre-War Suburb',
  'Red Rocket Station',
  'Settlement',
  'Abandoned Factory',
  'The Institute',
  'New Vegas Strip',
] as const

// --- Form state ---
const form = reactive<VisualAttributes>({})

// Initialize form from dweller's current visual_attributes
watch(
  () => props.dweller,
  (dweller) => {
    // Clear any stale keys from previous dweller
    for (const key in form) {
      delete form[key]
    }
    if (dweller.visual_attributes) {
      Object.assign(form, dweller.visual_attributes)
    } else {
      // Set defaults
      form.race = 'human'
      form.faction = 'vault_dweller'
    }
  },
  { immediate: true, deep: true }
)

// --- Race-filtered computed options ---

const raceKey = computed(() => form.race || 'human')

const availableFactions = computed(() => {
  return FACTION_OPTIONS[raceKey.value] || FACTION_OPTIONS.human
})

const availableStates = computed(() => {
  return STATE_OF_BEING_OPTIONS[raceKey.value] || null
})

const showStateOfBeing = computed(() => form.race && form.race !== 'human')

const availableSkinTones = computed(
  () => SKIN_TONE_OPTIONS[raceKey.value] || SKIN_TONE_OPTIONS.human
)

const availableBuilds = computed(() => BUILD_OPTIONS[raceKey.value] || BUILD_OPTIONS.human)

const availableHaircuts = computed(() => HAIRCUT_OPTIONS[raceKey.value] || HAIRCUT_OPTIONS.human)

const availableHeadgear = computed(() => HEADGEAR_OPTIONS[raceKey.value] || HEADGEAR_OPTIONS.human)

// Computed items arrays for @nuxt/ui USelect (items-based API)
const raceItems = computed(() => RACE_OPTIONS.map((r) => ({ value: r, label: formatLabel(r) })))
const factionItems = computed(() =>
  availableFactions.value.map((f) => ({ value: f, label: formatLabel(f) }))
)
const stateOfBeingItems = computed(() =>
  (availableStates.value || []).map((s) => ({ value: s, label: formatLabel(s) }))
)
const heightItems = computed(() => HEIGHT_OPTIONS.map((h) => ({ value: h, label: formatLabel(h) })))
const buildItems = computed(() => availableBuilds.value.map((b) => ({ value: b, label: b })))
const skinToneItems = computed(() => availableSkinTones.value.map((s) => ({ value: s, label: s })))
const eyeColorItems = computed(() =>
  EYE_COLOR_OPTIONS.map((e) => ({ value: e, label: formatLabel(e) }))
)
const haircutItems = computed(() => availableHaircuts.value.map((h) => ({ value: h, label: h })))
const hairColorItems = computed(() => HAIR_COLORS.map((h) => ({ value: h, label: formatLabel(h) })))
const expressionItems = computed(() =>
  EXPRESSIONS.map((e) => ({ value: e, label: formatLabel(e) }))
)
const appearanceItems = computed(() => [
  { value: 'attractive', label: 'Attractive' },
  { value: 'cute', label: 'Cute' },
  { value: 'average', label: 'Average' },
  { value: 'unattractive', label: 'Unattractive' },
])
const headgearItems = computed(() => availableHeadgear.value.map((h) => ({ value: h, label: h })))
const poseItems = computed(() => POSE_OPTIONS.map((p) => ({ value: p, label: p })))
const backgroundItems = computed(() => BACKGROUND_OPTIONS.map((b) => ({ value: b, label: b })))

// Format helper for display labels
const formatLabel = (value: string) => {
  return value
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

// Pick a random element from an array
function pickRandom<T>(arr: readonly T[] | T[]): T {
  return arr[Math.floor(Math.random() * arr.length)]
}

function randomize() {
  const randomRace = pickRandom(RACE_OPTIONS)
  form.race = randomRace

  // Set faction based on race
  const factions = FACTION_OPTIONS[randomRace] || FACTION_OPTIONS.human
  form.faction = pickRandom(factions)

  // State of being for non-humans
  const states = STATE_OF_BEING_OPTIONS[randomRace]
  if (states) {
    form.state_of_being = pickRandom(states)
  } else {
    delete form.state_of_being
  }

  // Physical
  form.height = pickRandom(HEIGHT_OPTIONS)
  form.build = pickRandom(BUILD_OPTIONS[randomRace] || BUILD_OPTIONS.human)
  form.skin_tone = pickRandom(SKIN_TONE_OPTIONS[randomRace] || SKIN_TONE_OPTIONS.human)
  form.eye_color = pickRandom(EYE_COLOR_OPTIONS)
  form.age = Math.floor(Math.random() * 50) + 20

  // Facial
  form.hair_style = pickRandom(HAIRCUT_OPTIONS[randomRace] || HAIRCUT_OPTIONS.human)
  form.hair_color = pickRandom(HAIR_COLORS)
  form.facial_hair = pickRandom(['None', 'Light Stubble', 'Goatee', 'Moustache', 'Full Beard'])
  if (form.facial_hair === 'None') form.facial_hair = undefined
  form.makeup = pickRandom(['natural', 'glamorous', 'goth'])
  form.expression = pickRandom(EXPRESSIONS)
  form.appearance = pickRandom(['attractive', 'cute', 'average', 'unattractive'])
  form.headgear = pickRandom(HEADGEAR_OPTIONS[randomRace] || HEADGEAR_OPTIONS.human)

  // Scene
  form.pose = pickRandom(POSE_OPTIONS)
  form.background = pickRandom(BACKGROUND_OPTIONS)
}

function handleSave() {
  // Clean up: remove empty values
  const cleaned: VisualAttributes = {}
  for (const [key, value] of Object.entries(form)) {
    if (value !== null && value !== undefined && value !== '') {
      ;(cleaned as Record<string, unknown>)[key] = value
    }
  }
  // Parent closes the modal after successful save (avoids losing context on failure)
  emit('saved', cleaned)
}

function handleCancel() {
  emit('update:modelValue', false)
}
</script>

<template>
  <UModal
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    title="Edit Appearance"
    size="xl"
  >
    <div class="editor-scroll">
      <!-- Identity Section -->
      <div class="editor-section">
        <h4 class="section-title">
          <Icon icon="mdi:badge-account" class="section-icon" />
          Identity
        </h4>
        <div class="form-grid">
          <div class="form-field">
            <label class="text-xs font-semibold uppercase tracking-wider text-theme-primary/70"
              >Race</label
            >
            <USelect v-model="form.race" :items="raceItems" />
          </div>
          <div class="form-field">
            <label class="text-xs font-semibold uppercase tracking-wider text-theme-primary/70"
              >Faction</label
            >
            <USelect v-model="form.faction" :items="factionItems" />
          </div>
          <div v-if="showStateOfBeing" class="form-field">
            <label class="text-xs font-semibold uppercase tracking-wider text-theme-primary/70"
              >State of Being</label
            >
            <USelect v-model="form.state_of_being" :items="stateOfBeingItems" />
          </div>
        </div>
      </div>

      <!-- Physical Section -->
      <div class="editor-section">
        <h4 class="section-title">
          <Icon icon="mdi:human" class="section-icon" />
          Physical
        </h4>
        <div class="form-grid">
          <div class="form-field">
            <label class="text-xs font-semibold uppercase tracking-wider text-theme-primary/70"
              >Height</label
            >
            <USelect v-model="form.height" :items="heightItems" />
          </div>
          <div class="form-field">
            <label class="text-xs font-semibold uppercase tracking-wider text-theme-primary/70"
              >Build</label
            >
            <USelect v-model="form.build" :items="buildItems" />
          </div>
          <div class="form-field">
            <label class="text-xs font-semibold uppercase tracking-wider text-theme-primary/70"
              >Skin Tone</label
            >
            <USelect v-model="form.skin_tone" :items="skinToneItems" />
          </div>
          <div class="form-field">
            <label class="text-xs font-semibold uppercase tracking-wider text-theme-primary/70"
              >Eye Color</label
            >
            <USelect v-model="form.eye_color" :items="eyeColorItems" />
          </div>
          <div class="form-field">
            <label class="text-xs font-semibold uppercase tracking-wider text-theme-primary/70"
              >Age</label
            >
            <UInput v-model.number="form.age" type="number" placeholder="18-80" />
          </div>
        </div>
      </div>

      <!-- Facial Features Section -->
      <div class="editor-section">
        <h4 class="section-title">
          <Icon icon="mdi:face" class="section-icon" />
          Facial Features
        </h4>
        <div class="form-grid">
          <div class="form-field">
            <label class="text-xs font-semibold uppercase tracking-wider text-theme-primary/70"
              >Hair Style</label
            >
            <USelect v-model="form.hair_style" :items="haircutItems" />
          </div>
          <div class="form-field">
            <label class="text-xs font-semibold uppercase tracking-wider text-theme-primary/70"
              >Hair Color</label
            >
            <USelect v-model="form.hair_color" :items="hairColorItems" />
          </div>
          <div class="form-field">
            <label class="text-xs font-semibold uppercase tracking-wider text-theme-primary/70"
              >Facial Hair</label
            >
            <UInput v-model="form.facial_hair" placeholder="e.g. beard, stubble" />
          </div>
          <div class="form-field">
            <label class="text-xs font-semibold uppercase tracking-wider text-theme-primary/70"
              >Makeup</label
            >
            <UInput v-model="form.makeup" placeholder="e.g. natural, glamorous" />
          </div>
          <div class="form-field">
            <label class="text-xs font-semibold uppercase tracking-wider text-theme-primary/70"
              >Expression</label
            >
            <USelect v-model="form.expression" :items="expressionItems" />
          </div>
          <div class="form-field">
            <label class="text-xs font-semibold uppercase tracking-wider text-theme-primary/70"
              >Appearance</label
            >
            <USelect v-model="form.appearance" :items="appearanceItems" />
          </div>
          <div class="form-field form-field-full">
            <label class="text-xs font-semibold uppercase tracking-wider text-theme-primary/70"
              >Distinguishing Features</label
            >
            <UInput v-model="form.distinguishing_features" placeholder="e.g. scar, tattoo, mole" />
          </div>
        </div>
      </div>

      <!-- Equipment Section -->
      <div class="editor-section">
        <h4 class="section-title">
          <Icon icon="mdi:backpack" class="section-icon" />
          Equipment & Scene
        </h4>
        <div class="form-grid">
          <div class="form-field">
            <label class="text-xs font-semibold uppercase tracking-wider text-theme-primary/70"
              >Headgear</label
            >
            <USelect v-model="form.headgear" :items="headgearItems" />
          </div>
          <div class="form-field">
            <label class="text-xs font-semibold uppercase tracking-wider text-theme-primary/70"
              >Clothing Style</label
            >
            <UInput v-model="form.clothing_style" placeholder="e.g. casual, military" />
          </div>
          <div class="form-field">
            <label class="text-xs font-semibold uppercase tracking-wider text-theme-primary/70"
              >Accessory</label
            >
            <UInput v-model="form.accessory" placeholder="e.g. Pip-Boy" />
          </div>
          <div class="form-field">
            <label class="text-xs font-semibold uppercase tracking-wider text-theme-primary/70"
              >Object Held</label
            >
            <UInput v-model="form.object_held" placeholder="e.g. Laser Rifle" />
          </div>
          <div class="form-field form-field-full">
            <label class="text-xs font-semibold uppercase tracking-wider text-theme-primary/70"
              >Pose</label
            >
            <USelect v-model="form.pose" :items="poseItems" />
          </div>
          <div class="form-field form-field-full">
            <label class="text-xs font-semibold uppercase tracking-wider text-theme-primary/70"
              >Background</label
            >
            <USelect v-model="form.background" :items="backgroundItems" />
          </div>
          <div class="form-field form-field-full">
            <label class="text-xs font-semibold uppercase tracking-wider text-theme-primary/70"
              >Voice Line</label
            >
            <UInput v-model="form.voice_line_text" placeholder="e.g. For the Brotherhood!" />
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="editor-footer">
        <UButton variant="ghost" @click="randomize">
          <Icon icon="mdi:dice-5" class="h-4 w-4" />
          Randomize
        </UButton>
        <UButton variant="ghost" @click="handleCancel">Cancel</UButton>
        <UButton color="primary" @click="handleSave">Save Changes</UButton>
      </div>
    </template>
  </UModal>
</template>

<style scoped>
.editor-scroll {
  max-height: 60vh;
  overflow-y: auto;
  padding-right: 0.25rem;
  background-color: var(--color-terminal-background);
}

.editor-scroll::-webkit-scrollbar {
  width: 6px;
}

.editor-scroll::-webkit-scrollbar-thumb {
  background: var(--color-theme-glow);
  border-radius: 3px;
}

.editor-section {
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.15);
}

.editor-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  margin-bottom: 0.75rem;
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.section-icon {
  width: 1.25rem;
  height: 1.25rem;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.form-field-full {
  grid-column: 1 / -1;
}

.editor-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding-top: 0.5rem;
}
</style>
