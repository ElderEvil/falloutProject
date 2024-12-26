import { z } from 'zod'

const RarityEnum = z.enum(['common', 'rare', 'legendary'])

export { RarityEnum }
