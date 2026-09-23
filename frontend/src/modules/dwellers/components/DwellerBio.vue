<script setup lang="ts">
import { computed } from 'vue'
import DOMPurify from 'dompurify'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/core/components/ui/tooltip'
import { useDwellerDetailContext } from './DwellerDetailContext'
import type { MapPlaceLink } from '../models/dweller'

const ctx = useDwellerDetailContext()

const dweller = computed(() => ctx.dweller.value)
const bio = computed(() => dweller.value?.bio ?? null)
const firstName = computed(() => dweller.value?.first_name ?? '')
const generatingBio = computed(() => ctx.generatingBio.value)
const isAnyGenerating = computed(() => ctx.isAnyGenerating.value)
const vaultId = computed(() => ctx.vaultId.value)
const placeLinks = computed(() => ctx.placeLinks.value)

interface BioEntry {
  source: string
  text: string
  ref?: Record<string, unknown> | null
  created_at?: string | null
}

type SectionKey = 'origin' | 'service' | 'exploration' | 'family' | 'dialogue' | 'other'
type KnownSectionKey = Exclude<SectionKey, 'other'>

interface BioSection {
  key: SectionKey
  label: string
  icon: string
  entries: BioEntry[]
  /** Log sections accumulate entries, so they fold away behind a count. */
  collapsible: boolean
}

const SECTION_ORDER: KnownSectionKey[] = ['origin', 'service', 'exploration', 'family', 'dialogue']

const SECTION_META: Record<
  KnownSectionKey,
  { label: string; icon: string; sources: string[]; collapsible?: boolean }
> = {
  origin: { label: 'ORIGIN', icon: 'mdi:map-marker-radius', sources: ['template', 'legacy'] },
  service: {
    label: 'SERVICE RECORD',
    icon: 'mdi:shield-star-outline',
    sources: ['hazard'],
    collapsible: true,
  },
  exploration: {
    label: 'FIELD LOG',
    icon: 'mdi:map-marker-path',
    sources: ['exploration'],
    collapsible: true,
  },
  family: { label: 'FAMILY RECORD', icon: 'mdi:account-group', sources: ['family'] },
  dialogue: { label: 'TRANSMISSION LOG', icon: 'mdi:message-text-outline', sources: ['dialogue'] },
}

/** `FIELD LOG · 2 entries` — the summary states what is behind the fold. */
function entryCountLabel(count: number): string {
  return `${count} ${count === 1 ? 'entry' : 'entries'}`
}

const normalizedEntries = computed<BioEntry[]>(() => {
  const raw = dweller.value?.bio_entries
  if (!Array.isArray(raw) || raw.length === 0) {
    return bio.value ? [{ source: 'template', text: bio.value }] : []
  }
  return raw
    .map((entry) => ({
      source: String(entry.source ?? 'legacy'),
      text: String(entry.text ?? ''),
      ref: (entry.ref ?? null) as Record<string, unknown> | null,
      created_at: (entry.created_at ?? null) as string | null,
    }))
    .filter((entry) => entry.text.trim().length > 0)
})

// Sources the sections above claim; anything else still renders under RECORD
// rather than disappearing when the backend adds a new entry source.
const KNOWN_SOURCES = new Set(SECTION_ORDER.flatMap((key) => SECTION_META[key].sources))

const sections = computed<BioSection[]>(() => {
  const known: BioSection[] = SECTION_ORDER.map((key) => {
    const meta = SECTION_META[key]
    return {
      key,
      label: meta.label,
      icon: meta.icon,
      entries: normalizedEntries.value.filter((entry) => meta.sources.includes(entry.source)),
      collapsible: meta.collapsible ?? false,
    }
  })
  const knownSources = KNOWN_SOURCES
  const unclaimed = normalizedEntries.value.filter((entry) => !knownSources.has(entry.source))
  if (unclaimed.length > 0) {
    known.push({
      key: 'other',
      label: 'RECORD',
      icon: 'mdi:note-text-outline',
      entries: unclaimed,
      collapsible: false,
    })
  }
  return known.filter((section) => section.entries.length > 0)
})

const PURIFY_OPTIONS = {
  ALLOWED_TAGS: ['br', 'em', 'strong', 'a'],
  ALLOWED_ATTR: ['href', 'class'],
}

/** Build a regex that matches any place name (case-insensitive). */
function buildPlaceRegex(links: MapPlaceLink[]): RegExp | null {
  if (!links.length) return null
  const sorted = [...links].sort((a, b) => b.name.length - a.name.length)
  const pattern = sorted.map((l) => l.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')
  return new RegExp(pattern, 'gi')
}

// Place-name linkification runs on a DOM fragment instead of the serialized
// HTML string: matching decoded text-node data resolves entity-encoded
// characters (e.g. `&amp;` already parsed to `&`) correctly, and the browser
// safely re-encodes entities when serializing the fragment back to HTML.
function linkifyText(text: string): string {
  const clean = DOMPurify.sanitize(text, PURIFY_OPTIONS)
  if (!vaultId.value || !placeLinks.value.length) return clean

  const regex = buildPlaceRegex(placeLinks.value)
  if (!regex) return clean

  const lookup = new Map<string, string>()
  for (const link of placeLinks.value) {
    lookup.set(link.name.toLowerCase(), link.locationId)
  }

  const container = document.createElement('div')
  container.innerHTML = clean

  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT)
  const textNodes: Text[] = []
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    textNodes.push(node as Text)
  }

  for (const node of textNodes) {
    const matches = [...node.data.matchAll(regex)]
    if (!matches.length) continue

    const fragment = document.createDocumentFragment()
    let cursor = 0
    for (const match of matches) {
      const index = match.index ?? 0
      if (index > cursor) {
        fragment.appendChild(document.createTextNode(node.data.slice(cursor, index)))
      }
      const locationId = lookup.get(match[0].toLowerCase())
      if (locationId) {
        const anchor = document.createElement('a')
        anchor.setAttribute('href', `/vault/${vaultId.value}/map?place=${locationId}`)
        anchor.className = 'bio-place-link'
        anchor.textContent = match[0]
        fragment.appendChild(anchor)
      } else {
        fragment.appendChild(document.createTextNode(match[0]))
      }
      cursor = index + match[0].length
    }
    if (cursor < node.data.length) {
      fragment.appendChild(document.createTextNode(node.data.slice(cursor)))
    }
    node.parentNode?.replaceChild(fragment, node)
  }

  return container.innerHTML
}

function entryHtml(text: string): string {
  return linkifyText(text)
}
</script>

<template>
  <div class="dweller-bio">
    <div class="bio-header">
      <div class="header-buttons">
        <TooltipProvider :delay-duration="200">
          <Tooltip>
            <TooltipTrigger as-child>
              <Button
                class="complete-dossier-button"
                variant="outline"
                size="sm"
                :disabled="isAnyGenerating"
                @click="ctx.actions.generateAll()"
              >
                <Icon
                  :icon="ctx.generatingAI.value ? 'mdi:loading' : 'mdi:sparkles'"
                  class="h-5 w-5"
                  :class="{ 'animate-spin': ctx.generatingAI.value }"
                />
                <span>Complete dossier</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">Creates or replaces appearance, portrait, and biography</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger as-child>
              <Button
                @click="ctx.actions.generateBio()"
                class="generate-button"
                variant="outline"
                size="sm"
                :disabled="isAnyGenerating"
              >
                <Icon
                  :icon="generatingBio ? 'mdi:loading' : 'mdi:pencil-plus'"
                  class="h-5 w-5"
                  :class="{ 'animate-spin': generatingBio }"
                />
                <span>{{ bio ? 'Regenerate biography' : 'Generate biography' }}</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">Creates or replaces this dweller's biography</TooltipContent>
          </Tooltip>

          <Tooltip v-if="bio">
            <TooltipTrigger as-child>
              <Button
                class="extend-bio-button"
                variant="outline"
                size="sm"
                :disabled="isAnyGenerating"
                @click="ctx.actions.extendBio()"
              >
                <Icon
                  :icon="generatingBio ? 'mdi:loading' : 'mdi:text-long'"
                  class="h-5 w-5"
                  :class="{ 'animate-spin': generatingBio }"
                />
                <span>Extend biography</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">Adds new details while keeping the current biography</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    </div>

    <div class="bio-content">
      <template v-if="sections.length > 0">
        <div class="bio-text bio-sections">
          <!-- Log sections render as <details> so the header itself is the toggle;
               prose sections stay plain. One entry-list block serves both. -->
          <component
            v-for="(section, index) in sections"
            :is="section.collapsible ? 'details' : 'section'"
            :key="section.key"
            class="bio-section"
            :class="`bio-section-${section.key}`"
          >
            <component
              :is="section.collapsible ? 'summary' : 'div'"
              class="bio-section-rule"
              :class="{ 'rule-first': index === 0 }"
            >
              <Icon :icon="section.icon" class="bio-section-icon" />
              <span class="bio-section-label">{{ section.label }}</span>
              <span v-if="section.collapsible" class="bio-section-count">{{
                entryCountLabel(section.entries.length)
              }}</span>
              <span class="bio-section-dashes" aria-hidden="true"></span>
              <Icon
                v-if="section.collapsible"
                icon="mdi:chevron-right"
                class="bio-section-chevron"
                :ariaHidden="true"
              />
            </component>
            <ul class="bio-entry-list">
              <li
                v-for="(entry, entryIndex) in section.entries"
                :key="`${section.key}-${entryIndex}`"
                class="bio-entry"
              >
                <span v-if="section.key !== 'origin'" class="bio-entry-marker" aria-hidden="true"
                  >&gt;</span
                >
                <p class="bio-entry-text" v-html="entryHtml(entry.text)"></p>
              </li>
            </ul>
          </component>
        </div>
      </template>
      <template v-else>
        <div class="bio-placeholder">
          <p class="placeholder-text">No biography available for {{ firstName }} yet.</p>
          <p class="placeholder-hint">Click "Generate" to create a unique backstory!</p>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.dweller-bio {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.bio-header {
  display: flex;
  justify-content: flex-start;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

.header-buttons {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

/* The inset box hugs the 70ch reading column instead of stretching the panel:
   text stays at comfortable line length, and the dead space simply disappears. */
.bio-content {
  max-width: 75ch;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.3);
  border-left: 3px solid var(--color-theme-primary);
  border-radius: 4px;
}

.bio-sections {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.bio-section-rule {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.bio-section-icon {
  width: 0.9rem;
  height: 0.9rem;
  flex-shrink: 0;
  color: var(--color-theme-primary);
  opacity: 0.65;
}

.bio-section-label {
  flex-shrink: 0;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.18em;
  color: var(--color-theme-primary);
  opacity: 0.75;
}

/* Dashed rule reads as the terminal `------` section separator. */
.bio-section-dashes {
  flex: 1;
  min-width: 2rem;
  border-bottom: 1px dashed var(--color-theme-primary);
  opacity: 0.35;
}

/* Collapsible log sections: the summary is the toggle, so it carries the pointer
   affordance and a focus ring, and the native disclosure marker is replaced by a
   chevron that rotates with the section. */
summary.bio-section-rule {
  cursor: pointer;
  list-style: none;
  border-radius: 2px;
}

summary.bio-section-rule::-webkit-details-marker {
  display: none;
}

summary.bio-section-rule:focus-visible {
  outline: 2px solid var(--color-theme-primary);
  outline-offset: 2px;
}

.bio-section-count {
  flex-shrink: 0;
  font-size: 0.7rem;
  letter-spacing: 0.05em;
  color: var(--color-theme-primary);
  opacity: 0.55;
  text-transform: none;
}

/* Reads as `FIELD LOG · 2 entries` without baking a glyph into the count string,
   so the rendered text stays "2 entries" for anyone reading the DOM or a test. */
.bio-section-count::before {
  content: '· ';
}

.bio-section-chevron {
  flex-shrink: 0;
  width: 0.9rem;
  height: 0.9rem;
  color: var(--color-theme-primary);
  opacity: 0.65;
  transition: transform 0.15s ease;
}

.bio-section[open] .bio-section-chevron {
  transform: rotate(90deg);
}

.bio-entry-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.bio-entry {
  display: flex;
  gap: 0.6rem;
  padding-left: 0.5rem;
}

.bio-entry-marker {
  flex-shrink: 0;
  color: var(--color-theme-primary);
  opacity: 0.55;
  font-size: 0.9rem;
  line-height: 1.7;
}

.bio-entry-text,
.bio-text {
  max-width: 70ch;
  margin: 0;
  line-height: 1.7;
  color: var(--color-theme-primary);
  font-size: 1rem;
  text-shadow: 0 0 3px var(--color-theme-glow);
  white-space: pre-wrap;
}

/* The origin story is the dweller's own voice: the inset and rule mark it as a
   quoted passage. Italic is deliberately not used — this is the longest prose
   on the page and slanting it all hurts extended reading. */
.bio-section-origin .bio-entry-text {
  padding-left: 0.85rem;
  border-left: 2px solid color-mix(in srgb, var(--color-theme-primary) 35%, transparent);
  opacity: 0.92;
}

.bio-placeholder {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  text-align: center;
  padding: 2rem 1rem;
}

.placeholder-text {
  color: var(--color-theme-primary);
  font-size: 1rem;
  text-shadow: 0 0 2px var(--color-theme-glow);
  opacity: 0.7;
}

.placeholder-hint {
  color: var(--color-theme-primary);
  font-size: 0.875rem;
  font-style: italic;
  text-shadow: 0 0 2px var(--color-theme-glow);
  opacity: 0.5;
}

.bio-text :deep(.bio-place-link) {
  color: var(--color-theme-primary);
  text-decoration: underline;
  text-underline-offset: 2px;
  cursor: pointer;
  transition: text-shadow 0.2s ease;
}

.bio-text :deep(.bio-place-link:hover) {
  text-shadow: 0 0 6px var(--color-theme-glow);
}
</style>
