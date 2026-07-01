import { ref, computed } from 'vue'
import { defineStore, acceptHMRUpdate } from 'pinia'
import * as http from '@/core/plugins/httpClient'
import type { Pregnancy } from '../models/pregnancy'
import type { Relationship, RelationshipCreate, CompatibilityScore } from '../models/relationship'
import { useToast } from '@/core/composables/useToast'
import { handleStoreError } from '@/core/utils/errorHandler'

export const useRelationshipStore = defineStore('relationship', () => {
  const toast = useToast()

  // State
  const relationships = ref<Relationship[]>([])
  const pregnancies = ref<Pregnancy[]>([])
  const isLoading = ref(false)

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
      relationships.value = await http.apiGet<Relationship[]>(`/api/v1/relationships/vault/${vaultId}`)
    } catch (error: unknown) {
      toast.error(handleStoreError(error, 'Failed to fetch relationships'))
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function fetchVaultPregnancies(vaultId: string) {
    try {
      pregnancies.value = await http.apiGet<Pregnancy[]>(`/api/v1/pregnancies/vault/${vaultId}`)
    } catch (error: unknown) {
      toast.error(handleStoreError(error, 'Failed to fetch pregnancies'))
      throw error
    }
  }

  async function getRelationship(relationshipId: string): Promise<Relationship | null> {
    try {
      return await http.apiGet<Relationship>(`/api/v1/relationships/${relationshipId}`)
    } catch (error: unknown) {
      toast.error(handleStoreError(error, 'Failed to fetch relationship'))
      return null
    }
  }

  async function createRelationship(data: RelationshipCreate): Promise<Relationship | null> {
    isLoading.value = true
    try {
      const relationship = await http.apiPost<Relationship>('/api/v1/relationships/', data)

      // Add to local state if not already present
      const existing = relationships.value.find((r) => r.id === relationship.id)
      if (!existing) {
        relationships.value.push(relationship)
      }

      toast.success('Relationship created')
      return relationship
    } catch (error: unknown) {
      toast.error(handleStoreError(error, 'Failed to create relationship'))
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function initiateRomance(relationshipId: string): Promise<Relationship | null> {
    isLoading.value = true
    try {
      const updated = await http.apiPut<Relationship>(`/api/v1/relationships/${relationshipId}/romance`)

      // Update local state
      const index = relationships.value.findIndex((r) => r.id === relationshipId)
      if (index !== -1) {
        relationships.value[index] = updated
      }

      toast.success('Romance initiated!')
      return updated
    } catch (error: unknown) {
      toast.error(handleStoreError(error, 'Failed to initiate romance'))
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function makePartners(relationshipId: string): Promise<Relationship | null> {
    isLoading.value = true
    try {
      const updated = await http.apiPut<Relationship>(`/api/v1/relationships/${relationshipId}/partner`)

      // Update local state
      const index = relationships.value.findIndex((r) => r.id === relationshipId)
      if (index !== -1) {
        relationships.value[index] = updated
      }

      toast.success('Dwellers are now partners!')
      return updated
    } catch (error: unknown) {
      toast.error(handleStoreError(error, 'Failed to make partners'))
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function breakUp(relationshipId: string): Promise<boolean> {
    isLoading.value = true
    try {
      await http.apiDelete(`/api/v1/relationships/${relationshipId}`)

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
      toast.error(handleStoreError(error, 'Failed to break up'))
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
      return await http.apiGet<CompatibilityScore>(
        `/api/v1/relationships/compatibility/${dweller1Id}/${dweller2Id}`
      )
    } catch (error: unknown) {
      toast.error(handleStoreError(error, 'Failed to calculate compatibility'))
      return null
    }
  }

  async function quickPair(vaultId: string): Promise<Relationship | null> {
    isLoading.value = true
    try {
      const relationship = await http.apiPost<Relationship>(`/api/v1/relationships/vault/${vaultId}/quick-pair`)

      // Add to local state
      relationships.value.push(relationship)

      toast.success('Dwellers paired successfully!')
      return relationship
    } catch (error: unknown) {
      toast.error(handleStoreError(error, 'Failed to quick pair'))
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function processVaultBreeding(vaultId: string): Promise<any | null> {
    try {
      return await http.apiPost<any>(`/api/v1/relationships/vault/${vaultId}/process`)
    } catch (error: unknown) {
      toast.error(handleStoreError(error, 'Failed to process breeding'))
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

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useRelationshipStore, import.meta.hot))
}
