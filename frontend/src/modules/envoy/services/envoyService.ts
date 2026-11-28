import { apiGet, apiPost } from '@/core/utils/api'
import type { EnvoyConfig, EnvoyFiling, EnvoySignal } from '../models/envoy'

const base = (vaultId: string) => `/api/v1/vaults/${vaultId}/envoy`

export const envoyService = {
  /** Every live vault with this vault's relation, plus the radio-range flag. */
  signals: (vaultId: string) => apiGet<EnvoySignal[]>(`${base(vaultId)}/signals`),
  /** File the only Slice 1 filing; the canned dispatch carries no message body. */
  hail: (vaultId: string, targetVaultId: string) =>
    apiPost<EnvoyFiling>(`${base(vaultId)}/hail`, { target_vault_id: targetVaultId }),
  respond: (vaultId: string, filingId: string, accept: boolean) =>
    apiPost<EnvoyFiling>(`${base(vaultId)}/filings/${filingId}/respond`, { accept }),
  /** Both directions of this vault's filings, newest first. */
  log: (vaultId: string) => apiGet<EnvoyFiling[]>(`${base(vaultId)}/log`),
  /** The server's effective knobs, so the terminal never invents a rule. */
  config: (vaultId: string) => apiGet<EnvoyConfig>(`${base(vaultId)}/config`),
}
