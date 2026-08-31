<script setup lang="ts">
import { computed } from 'vue'
import DOMPurify from 'dompurify'
import { Icon } from '@iconify/vue'
import UTooltip from '@/core/components/ui/UTooltip.vue'
import UButton from '@/core/components/ui/UButton.vue'
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

const sanitizedBio = computed(() => {
  if (!bio.value) return null
  const clean = DOMPurify.sanitize(bio.value, PURIFY_OPTIONS)

  // Without placeLinks or vaultId, render as-is (backward compatible)
  if (!vaultId.value || !placeLinks.value.length) return clean

  const regex = buildPlaceRegex(placeLinks.value)
  if (!regex) return clean

  // Build a lookup: lowercase place name → locationId
  const lookup = new Map<string, string>()
  for (const link of placeLinks.value) {
    lookup.set(link.name.toLowerCase(), link.locationId)
  }

  // Linkify on a DOM fragment instead of the serialized HTML string. Matching
  // against decoded text-node data makes entity-encoded characters (e.g.
  // `&amp;` already parsed to `&`) resolve correctly; the browser then safely
  // re-encodes entities when serializing the fragment back to HTML.
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
})
</script>

<template>
  <div class="dweller-bio">
    <div class="bio-header">
      <h3 class="bio-title">Biography</h3>
      <div class="header-buttons">
        <UTooltip text="Creates or replaces appearance, portrait, and biography" position="top">
          <UButton
            class="complete-dossier-button"
            variant="ghost"
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
          </UButton>
        </UTooltip>
        <UTooltip text="Creates or replaces this dweller's biography" position="top">
          <UButton
            @click="ctx.actions.generateBio()"
            class="generate-button"
            variant="secondary"
            size="sm"
            :disabled="isAnyGenerating"
          >
            <Icon
              :icon="generatingBio ? 'mdi:loading' : 'mdi:pencil-plus'"
              class="h-5 w-5"
              :class="{ 'animate-spin': generatingBio }"
            />
            <span>{{ bio ? 'Regenerate biography' : 'Generate biography' }}</span>
          </UButton>
        </UTooltip>
        <UTooltip v-if="bio" text="Adds new details while keeping the current biography" position="top">
          <UButton
            class="extend-bio-button"
            variant="secondary"
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
          </UButton>
        </UTooltip>
      </div>
    </div>
    <div class="bio-content">
      <template v-if="sanitizedBio">
        <p class="bio-text" v-html="sanitizedBio"></p>
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
  justify-content: space-between;
  align-items: center;
  border-bottom: 2px solid var(--color-theme-glow);
  padding-bottom: 0.5rem;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.bio-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 8px var(--color-theme-glow);
}

.header-buttons {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.bio-content {
  padding: 1rem;
  background: rgba(0, 0, 0, 0.3);
  border-left: 3px solid var(--color-theme-primary);
  border-radius: 4px;
}

.bio-text {
  max-width: 70ch;
  line-height: 1.7;
  color: var(--color-theme-primary);
  font-size: 1rem;
  text-shadow: 0 0 3px var(--color-theme-glow);
  white-space: pre-wrap;
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
