import { defineStore } from 'pinia'
import axios from '@/core/plugins/axios'
import type { Dweller } from '../models/dweller'
import { getErrorMessage } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import { useDwellerFilterStore } from './dwellerFilter'

export const useDwellerGenerationStore = defineStore('dwellerGeneration', () => {
  const toast = useToast()
  const filterStore = useDwellerFilterStore()

  const requestConfig = (token: string) => ({
    headers: { Authorization: `Bearer ${token}` },
    _skipErrorNotification: true,
  })

  const showGenerationError = (error: unknown, context: string) => {
    toast.error(`${context}: ${getErrorMessage(error)}`)
  }

  async function generateDwellerInfo(id: string, token: string): Promise<Dweller | null> {
    try {
      const response = await axios.post(`/api/v1/dwellers/${id}/generate_with_ai/`, null, requestConfig(token))
      filterStore.detailedDwellers[id] = response.data
      toast.success('Dweller info generated successfully!')
      return filterStore.detailedDwellers[id] ?? null
    } catch (error) {
      showGenerationError(error, `Failed to generate info for dweller ${id}`)
      return null
    }
  }

  async function generateDwellerBio(id: string, token: string): Promise<Dweller | null> {
    try {
      const response = await axios.post(`/api/v1/dwellers/${id}/generate_backstory/`, null, requestConfig(token))
      filterStore.detailedDwellers[id] = response.data
      toast.success('Biography generated successfully!')
      return filterStore.detailedDwellers[id] ?? null
    } catch (error) {
      showGenerationError(error, `Failed to generate biography for dweller ${id}`)
      return null
    }
  }

  async function extendDwellerBio(id: string, token: string): Promise<Dweller | null> {
    try {
      const response = await axios.post(`/api/v1/dwellers/${id}/extend_bio/`, null, requestConfig(token))
      filterStore.detailedDwellers[id] = response.data
      toast.success('Biography extended successfully!')
      return filterStore.detailedDwellers[id] ?? null
    } catch (error) {
      showGenerationError(error, `Failed to extend biography for dweller ${id}`)
      return null
    }
  }

  async function generateDwellerPortrait(id: string, token: string): Promise<Dweller | null> {
    try {
      // force=true allows regeneration even if a photo already exists
      const response = await axios.post(
        `/api/v1/dwellers/${id}/generate_photo/?force=true`,
        null,
        requestConfig(token)
      )
      filterStore.detailedDwellers[id] = response.data
      toast.success('Portrait generated successfully!')
      return filterStore.detailedDwellers[id] ?? null
    } catch (error) {
      showGenerationError(error, `Failed to generate portrait for dweller ${id}`)
      return null
    }
  }

  async function generateDwellerAppearance(id: string, token: string): Promise<Dweller | null> {
    try {
      const response = await axios.post(
        `/api/v1/dwellers/${id}/generate_visual_attributes/`,
        null,
        requestConfig(token)
      )
      filterStore.detailedDwellers[id] = response.data
      toast.success('Appearance generated successfully!')
      return filterStore.detailedDwellers[id] ?? null
    } catch (error) {
      showGenerationError(error, `Failed to generate appearance for dweller ${id}`)
      return null
    }
  }

  return {
    generateDwellerInfo,
    generateDwellerBio,
    extendDwellerBio,
    generateDwellerPortrait,
    generateDwellerAppearance,
  }
})
