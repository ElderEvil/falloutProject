import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { relationshipApi, type ProcessVaultBreedingResponse } from '../api/relationship'
import type { Relationship, RelationshipCreate, CompatibilityScore } from '../models/relationship'
import { isRelationshipType, PARTNER_LINKED_RELATIONSHIP_TYPES } from '../models/relationship'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'

export const useRelationshipStore = defineStore('relationship', () => {
  const toast = useToast()

  // State
  const relationships = ref<Relationship[]>([])
  const isLoading = ref(false)
  let mutationVersion = 0

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
    return relationships.value.filter((r) =>
      isRelationshipType(r.relationship_type, PARTNER_LINKED_RELATIONSHIP_TYPES)
    )
  })

  const getRomanticRelationships = computed(() => {
    return relationships.value.filter((r) => r.relationship_type === 'romantic')
  })

  function updateRelationship(updated: Relationship) {
    mutationVersion++
    const index = relationships.value.findIndex((relationship) => relationship.id === updated.id)
    if (index !== -1) {
      relationships.value[index] = { ...relationships.value[index], ...updated }
    }
  }

  // Actions
  async function fetchVaultRelationships(
    vaultId: string,
    { silent = false }: { silent?: boolean } = {}
  ) {
    if (!silent) isLoading.value = true
    const versionAtStart = mutationVersion
    try {
      const fetched = await relationshipApi.getByVault(vaultId)
      if (versionAtStart === mutationVersion) relationships.value = fetched
    } catch (error: unknown) {
      handleStoreError(error, 'Failed to fetch relationships', !silent)
      throw error
    } finally {
      if (!silent) isLoading.value = false
    }
  }

  async function getRelationship(relationshipId: string): Promise<Relationship | null> {
    try {
      return await relationshipApi.get(relationshipId)
    } catch (error: unknown) {
      handleStoreError(error, 'Failed to fetch relationship')
      return null
    }
  }

  async function createRelationship(data: RelationshipCreate): Promise<Relationship | null> {
    isLoading.value = true
    try {
      const relationship = await relationshipApi.create(data)
      mutationVersion++

      // Add to local state if not already present
      const existing = relationships.value.find((r) => r.id === relationship.id)
      if (!existing) {
        relationships.value.push(relationship)
      }

      toast.success('Relationship created')
      return relationship
    } catch (error: unknown) {
      handleStoreError(error, 'Failed to create relationship')
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function initiateRomance(relationshipId: string): Promise<Relationship | null> {
    isLoading.value = true
    try {
      const updated = await relationshipApi.initiateRomance(relationshipId)

      updateRelationship(updated)

      toast.success('Romance initiated!')
      return updated
    } catch (error: unknown) {
      handleStoreError(error, 'Failed to initiate romance')
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function makePartners(relationshipId: string): Promise<Relationship | null> {
    isLoading.value = true
    try {
      const updated = await relationshipApi.makePartners(relationshipId)

      updateRelationship(updated)

      toast.success('Dwellers are now partners!')
      return updated
    } catch (error: unknown) {
      handleStoreError(error, 'Failed to make partners')
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function marry(relationshipId: string): Promise<Relationship | null> {
    isLoading.value = true
    try {
      const updated = await relationshipApi.marry(relationshipId)

      updateRelationship(updated)

      toast.success('Dwellers are now married!')
      return updated
    } catch (error: unknown) {
      handleStoreError(error, 'Failed to marry dwellers')
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function breakUp(relationshipId: string): Promise<boolean> {
    isLoading.value = true
    try {
      await relationshipApi.breakUp(relationshipId)
      mutationVersion++

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
      handleStoreError(error, 'Failed to break up')
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
      return await relationshipApi.getCompatibility(dweller1Id, dweller2Id)
    } catch (error: unknown) {
      handleStoreError(error, 'Failed to calculate compatibility')
      return null
    }
  }

  async function processVaultBreeding(
    vaultId: string
  ): Promise<ProcessVaultBreedingResponse | null> {
    try {
      return await relationshipApi.processVaultBreeding(vaultId)
    } catch (error: unknown) {
      handleStoreError(error, 'Failed to process breeding')
      return null
    }
  }

  function clearRelationships() {
    mutationVersion++
    relationships.value = []
  }

  return {
    // State
    relationships,
    isLoading,

    // Computed
    getRelationshipByDwellers,
    getPartnerRelationships,
    getRomanticRelationships,

    // Actions
    fetchVaultRelationships,
    getRelationship,
    createRelationship,
    initiateRomance,
    makePartners,
    marry,
    breakUp,
    calculateCompatibility,
    processVaultBreeding,
    clearRelationships,
  }
})
