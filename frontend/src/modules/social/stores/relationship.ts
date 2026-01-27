import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import axios from '@/core/plugins/axios'
import type { Relationship, RelationshipCreate, CompatibilityScore } from '../models/relationship'
import { useToast } from '@/core/composables/useToast'
import { getErrorMessage } from '@/core/types/utils'

export const useRelationshipStore = defineStore('relationship', () => {
  const toast = useToast()

  // State
  const relationships = ref<Relationship[]>([])
  const pregnancies = ref<any[]>([])
  const isLoading = ref(false)
  const token = ref<string | null>(null)

  // Computed
  const getRelationshipByDwellers = computed(() => {
    return (dweller1Id: string, dweller2Id: string): Relationship | undefined => {
      return relationships.value.find(
        (r) =>
          (r.dweller_1_id === dweller1Id && r.dweller_2_id === dweller2Id) ||
          (r.dweller_1_id === dweller2Id && r.dweller_2_id === dweller1Id)
      )
    }
  })

  const getPartnerRelationships = computed(() => {
    return relationships.value.filter((r) => r.relationship_type === 'partner')
  })

  const getRomanticRelationships = computed(() => {
    return relationships.value.filter((r) => r.relationship_type === 'romantic')
  })

  // Actions
  async function fetchVaultRelationships(vaultId: string) {
    isLoading.value = true
    try {
      const response = await axios.get(`/api/v1/relationships/vault/${vaultId}`)
      relationships.value = response.data
    } catch (error: unknown) {
      console.error('Failed to fetch relationships:', error)
      toast.error(getErrorMessage(error))
    } finally {
      isLoading.value = false
    }
  }

  async function fetchVaultPregnancies(vaultId: string) {
    try {
      const response = await axios.get(`/api/v1/pregnancies/vault/${vaultId}`)
      pregnancies.value = response.data
    } catch (error: unknown) {
      console.error('Failed to fetch pregnancies:', error)
      toast.error(getErrorMessage(error))
    }
  }

  async function getRelationship(relationshipId: string): Promise<Relationship | null> {
    try {
      const response = await axios.get(`/api/v1/relationships/${relationshipId}`)
      return response.data
    } catch (error: unknown) {
      console.error('Failed to fetch relationship:', error)
      toast.error(getErrorMessage(error))
      return null
    }
  }

  async function createRelationship(data: RelationshipCreate): Promise<Relationship | null> {
    isLoading.value = true
    try {
      const response = await axios.post('/api/v1/relationships/', data)
      const relationship = response.data

      // Add to local state if not already present
      const existing = relationships.value.find((r) => r.id === relationship.id)
      if (!existing) {
        relationships.value.push(relationship)
      }

      toast.success('Relationship created')
      return relationship
    } catch (error: unknown) {
      console.error('Failed to create relationship:', error)
      toast.error(getErrorMessage(error))
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function initiateRomance(relationshipId: string): Promise<Relationship | null> {
    isLoading.value = true
    try {
      const response = await axios.put(`/api/v1/relationships/${relationshipId}/romance`)
      const updated = response.data

      // Update local state
      const index = relationships.value.findIndex((r) => r.id === relationshipId)
      if (index !== -1) {
        relationships.value[index] = updated
      }

      toast.success('Romance initiated!')
      return updated
    } catch (error: unknown) {
      console.error('Failed to initiate romance:', error)
      toast.error(getErrorMessage(error))
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function makePartners(relationshipId: string): Promise<Relationship | null> {
    isLoading.value = true
    try {
      const response = await axios.put(`/api/v1/relationships/${relationshipId}/partner`)
      const updated = response.data

      // Update local state
      const index = relationships.value.findIndex((r) => r.id === relationshipId)
      if (index !== -1) {
        relationships.value[index] = updated
      }

      toast.success('Dwellers are now partners!')
      return updated
    } catch (error: unknown) {
      console.error('Failed to make partners:', error)
      toast.error(getErrorMessage(error))
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function breakUp(relationshipId: string): Promise<boolean> {
    isLoading.value = true
    try {
      await axios.delete(`/api/v1/relationships/${relationshipId}`)

      // Update local state
      const index = relationships.value.findIndex((r) => r.id === relationshipId)
      if (index !== -1 && relationships.value[index]) {
        relationships.value[index]!.relationship_type = 'ex'
        relationships.value[index]!.affinity = Math.max(
          0,
          relationships.value[index]!.affinity - 30
        )
      }

      toast.success('Relationship ended')
      return true
    } catch (error: unknown) {
      console.error('Failed to break up:', error)
      toast.error(getErrorMessage(error))
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function calculateCompatibility(
    dweller1Id: string,
    dweller2Id: string
  ): Promise<CompatibilityScore | null> {
    try {
      const response = await axios.get(
        `/api/v1/relationships/compatibility/${dweller1Id}/${dweller2Id}`
      )
      return response.data
    } catch (error: unknown) {
      console.error('Failed to calculate compatibility:', error)
      toast.error(getErrorMessage(error))
      return null
    }
  }

  async function quickPair(vaultId: string): Promise<Relationship | null> {
    isLoading.value = true
    try {
      const response = await axios.post(`/api/v1/relationships/vault/${vaultId}/quick-pair`)
      const relationship = response.data

      // Add to local state
      relationships.value.push(relationship)

      toast.success('Dwellers paired successfully!')
      return relationship
    } catch (error: unknown) {
      console.error('Failed to quick pair:', error)
      toast.error(getErrorMessage(error))
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function processVaultBreeding(vaultId: string): Promise<any | null> {
    try {
      const response = await axios.post(`/api/v1/relationships/vault/${vaultId}/process`)
      return response.data
    } catch (error: unknown) {
      console.error('Failed to process breeding:', error)
      toast.error(getErrorMessage(error))
      return null
    }
  }

  function clearRelationships() {
    relationships.value = []
  }

  return {
    // State
    relationships,
    isLoading,
    pregnancies,
    token,

    // Computed
    getRelationshipByDwellers,
    getPartnerRelationships,
    getRomanticRelationships,

    // Actions
    fetchVaultRelationships,
    fetchVaultPregnancies,
    getRelationship,
    createRelationship,
    initiateRomance,
    makePartners,
    breakUp,
    calculateCompatibility,
    quickPair,
    processVaultBreeding,
    clearRelationships,
  }
})
