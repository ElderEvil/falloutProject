import { apiPost } from '@/core/utils/api'
import type { Dweller } from '../models/dweller'

const generate = (url: string): Promise<Dweller> =>
  apiPost<Dweller>(url, null, { skipErrorNotification: true })

export const generateDwellerInfo = (id: string): Promise<Dweller> =>
  generate(`/api/v1/dwellers/${id}/generate_with_ai/`)

export const generateDwellerBio = (id: string): Promise<Dweller> =>
  generate(`/api/v1/dwellers/${id}/generate_backstory/`)

export const extendDwellerBio = (id: string): Promise<Dweller> =>
  generate(`/api/v1/dwellers/${id}/extend_bio/`)

export const generateDwellerPortrait = (id: string): Promise<Dweller> =>
  generate(`/api/v1/dwellers/${id}/generate_photo/?force=true`)

export const generateDwellerAppearance = (id: string): Promise<Dweller> =>
  generate(`/api/v1/dwellers/${id}/generate_visual_attributes/`)
