import axios from '@/core/plugins/axios'

export type RadioMode = 'recruitment' | 'happiness'

/** Switch a vault's radio between recruitment and happiness mode. */
export async function setRadioMode(vaultId: string, mode: RadioMode): Promise<string> {
  const response = await axios.put(`/api/v1/radio/vault/${vaultId}/mode`, null, { params: { mode } })
  return response.data.radio_mode
}
