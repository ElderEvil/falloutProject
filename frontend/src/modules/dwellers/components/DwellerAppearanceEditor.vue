<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import UModal from '@/core/components/ui/UModal.vue'
import UButton from '@/core/components/ui/UButton.vue'
import UInput from '@/core/components/ui/UInput.vue'
import USelect from '@/core/components/ui/USelect.vue'
import USlider from '@/core/components/ui/USlider.vue'
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
// Form controls use strings (and a numeric age), while the API model allows
// null values and represents distinguishing features as an array. Keep that
// transport shape at the save/load boundary rather than leaking it into inputs.
interface AppearanceForm {
  race?: string
  faction?: string
  height?: string
  build?: string
  skin_tone?: string
  eye_color?: string
  age?: number
  state_of_being?: string
  appearance?: string
  hair_style?: string
  hair_color?: string
  facial_hair?: string
  makeup?: string
  expression?: string
  headgear?: string
  distinguishing_features?: string
  clothing_style?: string
  accessory?: string
  object_held?: string
  pose?: string
  background?: string
  voice_line_text?: string
}

type AppearanceSection = 'identity' | 'physical' | 'face' | 'scene'

const sections: Array<{ id: AppearanceSection; label: string; icon: string }> = [
  { id: 'identity', label: 'Identity', icon: 'mdi:badge-account' },
  { id: 'physical', label: 'Build', icon: 'mdi:human' },
  { id: 'face', label: 'Face', icon: 'mdi:face' },
  { id: 'scene', label: 'Scene', icon: 'mdi:backpack' },
]

const form = reactive<AppearanceForm>({})
const activeSection = ref<AppearanceSection>('identity')
const ageValue = computed<number>({
  get: () => form.age ?? 30,
  set: (value) => {
    form.age = value
  },
})

// Initialize form from dweller's current visual_attributes
watch(
  () => props.dweller,
  (dweller) => {
    // Clear any stale keys from previous dweller
    for (const key of Object.keys(form) as Array<keyof AppearanceForm>) {
      delete form[key]
    }
    if (dweller.visual_attributes) {
      for (const [key, value] of Object.entries(dweller.visual_attributes)) {
        if (value === null || value === undefined) continue
        if (key === 'distinguishing_features' && Array.isArray(value)) {
          form.distinguishing_features = value.join(', ')
        } else {
          ;(form as Record<string, string | number | undefined>)[key] = value as string | number
        }
      }
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

// Format helper for display labels
const formatLabel = (value: string) => {
  return value
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

const selectOptions = (values: readonly string[]) =>
  values.map((value) => ({ value, label: formatLabel(value) }))

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
      ;(cleaned as Record<string, unknown>)[key] =
        key === 'distinguishing_features' && typeof value === 'string'
          ? value
              .split(',')
              .map((feature) => feature.trim())
              .filter(Boolean)
          : value
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
    surface="base"
  >
    <div class="editor-workbench">
      <nav class="section-nav" aria-label="Appearance sections">
        <button
          v-for="section in sections"
          :key="section.id"
          type="button"
          class="section-nav-button"
          :class="{ active: activeSection === section.id }"
          :aria-current="activeSection === section.id ? 'page' : undefined"
          @click="activeSection = section.id"
        >
          <Icon :icon="section.icon" class="section-nav-icon" />
          <span>{{ section.label }}</span>
        </button>
      </nav>

      <div class="editor-scroll">

      <!-- Identity Section -->
      <div v-show="activeSection === 'identity'" class="editor-section">
        <h4 class="section-title">
          <Icon icon="mdi:badge-account" class="section-icon" />
          Identity
        </h4>
        <div class="form-grid">
          <div class="form-field">
            <USelect v-model="form.race" :options="selectOptions(RACE_OPTIONS)" label="Race" label-icon="mdi:account" />
          </div>
          <div class="form-field">
            <USelect v-model="form.faction" :options="selectOptions(availableFactions)" label="Faction" label-icon="mdi:shield-account" />
          </div>
          <div v-if="showStateOfBeing" class="form-field">
            <USelect v-model="form.state_of_being" :options="selectOptions(availableStates || [])" label="State of Being" label-icon="mdi:radioactive" />
          </div>
        </div>
      </div>

      <!-- Physical Section -->
      <div v-show="activeSection === 'physical'" class="editor-section">
        <h4 class="section-title">
          <Icon icon="mdi:human" class="section-icon" />
          Physical
        </h4>
        <div class="form-grid">
          <div class="form-field">
            <USelect v-model="form.height" :options="selectOptions(HEIGHT_OPTIONS)" label="Height" label-icon="mdi:human-male-height" />
          </div>
          <div class="form-field">
            <USelect v-model="form.build" :options="selectOptions(availableBuilds)" label="Build" label-icon="mdi:arm-flex" />
          </div>
          <div class="form-field">
            <USelect v-model="form.skin_tone" :options="selectOptions(availableSkinTones)" label="Skin Tone" label-icon="mdi:palette-outline" />
          </div>
          <div class="form-field">
            <USelect v-model="form.eye_color" :options="selectOptions(EYE_COLOR_OPTIONS)" label="Eye Color" label-icon="mdi:eye-outline" />
          </div>
          <label class="flex flex-col gap-1">
            <span class="flex items-center gap-1 text-sm font-medium text-theme-primary/70">
              <Icon icon="mdi:calendar-outline" class="h-3.5 w-3.5 text-theme-primary/60" />
              Age <strong class="ml-auto text-theme-primary">{{ ageValue }}</strong>
            </span>
            <USlider
              v-model="ageValue"
              :min="18"
              :max="80"
              aria-label="Age"
            />
            <span class="flex justify-between text-xs text-theme-primary/50"><span>18</span><span>80</span></span>
          </label>
        </div>
      </div>

      <!-- Facial Features Section -->
      <div v-show="activeSection === 'face'" class="editor-section">
        <h4 class="section-title">
          <Icon icon="mdi:face" class="section-icon" />
          Facial Features
        </h4>
        <div class="form-grid">
          <div class="form-field">
            <USelect v-model="form.hair_style" :options="selectOptions(availableHaircuts)" label="Hair Style" label-icon="mdi:content-cut" />
          </div>
          <div class="form-field">
            <USelect v-model="form.hair_color" :options="selectOptions(HAIR_COLORS)" label="Hair Color" label-icon="mdi:palette" />
          </div>
          <div class="form-field">
            <UInput
              v-model="form.facial_hair"
              label="Facial Hair"
              label-icon="mdi:face-man-outline"
              placeholder="e.g. beard, stubble"
            />
          </div>
          <div class="form-field">
            <UInput v-model="form.makeup" label="Makeup" label-icon="mdi:brush-variant" placeholder="e.g. natural, glamorous" />
          </div>
          <div class="form-field">
            <USelect v-model="form.expression" :options="selectOptions(EXPRESSIONS)" label="Expression" label-icon="mdi:emoticon-outline" />
          </div>
          <div class="form-field">
            <USelect v-model="form.appearance" :options="selectOptions(['attractive', 'cute', 'average', 'unattractive'])" label="Appearance" label-icon="mdi:account-details-outline" />
          </div>
          <div class="form-field form-field-full">
            <UInput
              v-model="form.distinguishing_features"
              label="Distinguishing Features"
              label-icon="mdi:star-outline"
              placeholder="e.g. scar, tattoo, mole"
            />
          </div>
        </div>
      </div>

      <!-- Equipment Section -->
      <div v-show="activeSection === 'scene'" class="editor-section">
        <h4 class="section-title">
          <Icon icon="mdi:backpack" class="section-icon" />
          Equipment & Scene
        </h4>
        <div class="form-grid">
          <div class="form-field">
            <USelect v-model="form.headgear" :options="selectOptions(availableHeadgear)" label="Headgear" label-icon="mdi:hard-hat" />
          </div>
          <div class="form-field">
            <UInput
              v-model="form.clothing_style"
              label="Clothing Style"
              label-icon="mdi:tshirt-crew-outline"
              placeholder="e.g. casual, military"
            />
          </div>
          <div class="form-field">
            <UInput v-model="form.accessory" label="Accessory" label-icon="mdi:watch-variant" placeholder="e.g. Pip-Boy" />
          </div>
          <div class="form-field">
            <UInput v-model="form.object_held" label="Object Held" label-icon="mdi:hand-back-right-outline" placeholder="e.g. Laser Rifle" />
          </div>
          <div class="form-field form-field-full">
            <USelect v-model="form.pose" :options="selectOptions(POSE_OPTIONS)" label="Pose" label-icon="mdi:human-greeting" />
          </div>
          <div class="form-field form-field-full">
            <USelect v-model="form.background" :options="selectOptions(BACKGROUND_OPTIONS)" label="Background" label-icon="mdi:panorama-outline" />
          </div>
          <div class="form-field form-field-full">
            <UInput
              v-model="form.voice_line_text"
              label="Voice Line"
              label-icon="mdi:comment-quote-outline"
              placeholder="e.g. For the Brotherhood!"
            />
          </div>
        </div>
      </div>
      </div>
    </div>

    <template #footer>
      <div class="editor-footer">
        <UButton variant="ghost" class="utility-button" @click="randomize">
          <Icon icon="mdi:dice-5" class="h-4 w-4" />
          Randomize
        </UButton>
        <div class="editor-footer-actions">
          <UButton variant="ghost" @click="handleCancel">Cancel</UButton>
          <UButton @click="handleSave">Save Changes</UButton>
        </div>
      </div>
    </template>
  </UModal>
</template>

<style scoped>
.editor-workbench {
  display: grid;
  grid-template-columns: 9rem minmax(0, 1fr);
  gap: 1.5rem;
  min-height: 22rem;
}

.section-nav {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0.25rem;
  padding-right: 1rem;
  border-right: 1px solid color-mix(in srgb, var(--color-theme-primary) 22%, transparent);
}

.section-nav-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.625rem 0.5rem;
  border: 0;
  border-left: 2px solid transparent;
  background: transparent;
  color: color-mix(in srgb, var(--color-theme-primary) 65%, transparent);
  font: inherit;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-align: left;
  cursor: pointer;
}

.section-nav-button:hover,
.section-nav-button:focus-visible {
  background: color-mix(in srgb, var(--color-theme-primary) 8%, transparent);
  color: var(--color-theme-primary);
  outline: none;
}

.section-nav-button.active {
  border-left-color: var(--color-theme-primary);
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.section-nav-icon {
  width: 1rem;
  height: 1rem;
}

.editor-scroll {
  max-height: 55vh;
  overflow-y: auto;
  padding: 0.25rem 0.5rem 0.25rem 0;
}

.editor-scroll::-webkit-scrollbar {
  width: 6px;
}

.editor-scroll::-webkit-scrollbar-thumb {
  background: var(--color-theme-glow);
  border-radius: 3px;
}

.editor-section {
  padding-top: 0.25rem;
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

.editor-workbench :deep(input) {
  background: transparent;
  border-color: color-mix(in srgb, var(--color-theme-primary) 32%, transparent);
}

.editor-workbench :deep(input:focus) {
  background: color-mix(in srgb, var(--color-theme-primary) 7%, transparent);
}

.editor-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  width: 100%;
}

.editor-footer-actions {
  display: flex;
  gap: 0.75rem;
}

.utility-button {
  background: color-mix(in srgb, var(--color-theme-primary) 10%, var(--color-surface));
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 45%, transparent);
}

.utility-button:hover:not(:disabled) {
  background: color-mix(in srgb, var(--color-theme-primary) 18%, var(--color-surface));
  border-color: var(--color-theme-primary);
}

@media (max-width: 36rem) {
  .editor-workbench {
    display: block;
    min-height: 0;
  }

  .section-nav {
    flex-direction: row;
    overflow-x: auto;
    margin-bottom: 1rem;
    padding: 0 0 0.5rem;
    border-right: 0;
    border-bottom: 1px solid color-mix(in srgb, var(--color-theme-primary) 22%, transparent);
  }

  .section-nav-button {
    flex-shrink: 0;
    border-bottom: 2px solid transparent;
    border-left: 0;
  }

  .section-nav-button.active {
    border-bottom-color: var(--color-theme-primary);
  }

  .editor-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .editor-footer-actions {
    justify-content: flex-end;
  }
}
</style>
