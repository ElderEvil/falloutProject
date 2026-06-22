import { defineStore } from 'pinia'
import axios from '@/core/plugins/axios'
import type { Dweller } from '../models/dweller'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import { useDwellerFilterStore } from './dwellerFilter'

export const useDwellerGenerationStore = defineStore('dwellerGeneration', () => {
  const toast = useToast()
  const filterStore = useDwellerFilterStore()

  async function generateDwellerInfo(id: string, token: string): Promise<Dweller | null> {
    try {
      const response = await axios.post(`/api/v1/dwellers/${id}/generate_with_ai/`, null, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      filterStore.detailedDwellers[id] = response.data
      toast.success('Dweller info generated successfully!')
      return filterStore.detailedDwellers[id] ?? null
    } catch (error) {
      handleStoreError(error, `Failed to generate info for dweller ${id}`)
      toast.error('Failed to generate dweller info')
      return null
    }
  }

  async function generateDwellerBio(id: string, token: string): Promise<Dweller | null> {
    try {
      const response = await axios.post(`/api/v1/dwellers/${id}/generate_backstory/`, null, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      filterStore.detailedDwellers[id] = response.data
      toast.success('Biography generated successfully!')
      return filterStore.detailedDwellers[id] ?? null
    } catch (error) {
      handleStoreError(error, `Failed to generate biography for dweller ${id}`)
      toast.error('Failed to generate biography')
      return null
    }
  }

  async function generateDwellerPortrait(id: string, token: string): Promise<Dweller | null> {
    try {
      // force=true allows regeneration even if a photo already exists
      const response = await axios.post(`/api/v1/dwellers/${id}/generate_photo/?force=true`, null, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      filterStore.detailedDwellers[id] = response.data
      toast.success('Portrait generated successfully!')
      return filterStore.detailedDwellers[id] ?? null
    } catch (error) {
      handleStoreError(error, `Failed to generate portrait for dweller ${id}`)
      toast.error('Failed to generate portrait')
      return null
    }
  }

  async function generateDwellerAppearance(id: string, token: string): Promise<Dweller | null> {
    try {
      const response = await axios.post(
        `/api/v1/dwellers/${id}/generate_visual_attributes/`,
        null,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )
      filterStore.detailedDwellers[id] = response.data
      toast.success('Appearance generated successfully!')
      return filterStore.detailedDwellers[id] ?? null
    } catch (error) {
      handleStoreError(error, `Failed to generate appearance for dweller ${id}`)
      toast.error('Failed to generate appearance')
      return null
    }
  }

  return {
    generateDwellerInfo,
    generateDwellerBio,
    generateDwellerPortrait,
    generateDwellerAppearance,
  }
})
