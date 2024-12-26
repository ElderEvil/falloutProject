import type { Vault, Resource } from '@/types/vault.types'

export function createResourceManager(getVault: () => Vault | null) {
  function updateResource(type: Resource['type'], amount: number) {
    const vault = getVault()
    if (!vault) return false

    const resource = vault.resources.find((r) => r.type === type)
    if (!resource) return false

    resource.amount = Math.max(0, Math.min(resource.amount + amount, resource.capacity))
    return true
  }

  function getResourceLevel(type: Resource['type']) {
    const vault = getVault()
    if (!vault) return 0

    const resource = vault.resources.find((r) => r.type === type)
    return resource ? resource.amount / resource.capacity : 0
  }

  return {
    updateResource,
    getResourceLevel
  }
}
