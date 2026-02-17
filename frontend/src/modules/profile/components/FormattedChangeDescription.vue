<script setup lang="ts">
/**
 * FormattedChangeDescription - Safely renders changelog descriptions with markdown-style formatting
 * Prevents XSS by avoiding v-html and using Vue's text rendering with manual formatting
 */
import { computed } from 'vue'

interface Props {
  description: string
}

const props = defineProps<Props>()

// Parse description into segments with formatting info
interface Segment {
  type: 'text' | 'code' | 'bold' | 'link'
  content: string
  href?: string
}

const segments = computed<Segment[]>(() => {
  const text = props.description
  const result: Segment[] = []
  let remaining = text
  let position = 0

  // Process text and extract formatted segments
  while (remaining.length > 0) {
    // Check for code blocks (backticks)
    const codeMatch = remaining.match(/^`([^`]+)`/)
    if (codeMatch) {
      result.push({
        type: 'code',
        content: codeMatch[1],
      })
      remaining = remaining.slice(codeMatch[0].length)
      position += codeMatch[0].length
      continue
    }

    // Check for bold text (**)
    const boldMatch = remaining.match(/^\*\*([^*]+)\*\*/)
    if (boldMatch) {
      result.push({
        type: 'bold',
        content: boldMatch[1],
      })
      remaining = remaining.slice(boldMatch[0].length)
      position += boldMatch[0].length
      continue
    }

    // Check for URLs
    const urlMatch = remaining.match(/^(https?:\/\/[^\s]+)/)
    if (urlMatch) {
      result.push({
        type: 'link',
        content: urlMatch[1],
        href: urlMatch[1],
      })
      remaining = remaining.slice(urlMatch[0].length)
      position += urlMatch[0].length
      continue
    }

    // Regular text - consume until next special character (backtick, **, or http(s)://)
    const backtickIdx = remaining.indexOf('`')
    const boldIdx = remaining.indexOf('**')
    const httpIdx = remaining.indexOf('http://')
    const httpsIdx = remaining.indexOf('https://')

    // Find the minimum index (first occurrence of any special token)
    const indices = [backtickIdx, boldIdx, httpIdx, httpsIdx].filter((idx) => idx !== -1)
    const nextSpecial = indices.length > 0 ? Math.min(...indices) : -1

    if (nextSpecial === -1) {
      // No more special characters - consume rest as plain text
      if (remaining.length > 0) {
        result.push({
          type: 'text',
          content: remaining,
        })
      }
      break
    } else {
      // Consume text up to next special character
      const textSegment = remaining.slice(0, nextSpecial)
      if (textSegment.length > 0) {
        result.push({
          type: 'text',
          content: textSegment,
        })
      }
      remaining = remaining.slice(nextSpecial)
      position += nextSpecial
    }
  }

  return result
})
</script>

<template>
  <span class="inline">
    <template v-for="(segment, index) in segments" :key="index">
      <!-- Plain text -->
      <span v-if="segment.type === 'text'">{{ segment.content }}</span>

      <!-- Code block -->
      <code
        v-else-if="segment.type === 'code'"
        class="bg-gray-800 px-1 rounded text-green-300 font-mono text-xs"
      >
        {{ segment.content }}
      </code>

      <!-- Bold text -->
      <strong v-else-if="segment.type === 'bold'" class="text-white font-semibold">
        {{ segment.content }}
      </strong>

      <!-- Link -->
      <a
        v-else-if="segment.type === 'link'"
        :href="segment.href"
        target="_blank"
        rel="noopener noreferrer"
        class="text-green-400 hover:text-green-300 underline"
      >
        {{ segment.content }}
      </a>
    </template>
  </span>
</template>
