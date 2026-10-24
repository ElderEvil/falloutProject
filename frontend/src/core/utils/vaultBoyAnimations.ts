export type VaultBoyAnimationId =
  | 'rush-success'
  | 'rush-failure'
  | 'baby'
  | 'food-low'
  | 'happiness-low'
  | 'ok'
  | 'power-low'
  | 'storage'
  | 'water-low'

type Frame = readonly [x: number, y: number, width: number, height: number]
export interface VaultBoyAnimation {
  title: string
  sheet: string
  sheetSize?: readonly [width: number, height: number]
  canvas: readonly [width: number, height: number]
  frames: readonly Frame[]
  sequence: readonly number[]
}

// Atlas rectangles are unequal. Pose numbers follow source position, not playback order.
// Each sequence plays a gesture once, then holds its final pose.
export const VAULT_BOY_ANIMATIONS: Record<VaultBoyAnimationId, VaultBoyAnimation> = {
  'rush-success': {
    title: 'Rush success',
    sheet: '/assets/vault-boy/VaultBoy_AnimationsRushOk.webp',
    canvas: [544, 480],
    frames: [
      [0, 90, 400, 475],
      [400, 90, 388, 475],
      [788, 90, 390, 475],
      [1178, 90, 422, 475],
      [0, 565, 385, 459],
      [385, 565, 405, 459],
      [790, 565, 490, 459],
    ],
    sequence: [4, 1, 3, 0, 5, 2, 6],
  },
  'rush-failure': {
    title: 'Rush failure',
    sheet: '/assets/vault-boy/VaultBoy_AnimationsRushFail.webp',
    canvas: [544, 480],
    frames: [
      [0, 90, 512, 465],
      [512, 90, 437, 465],
      [949, 90, 401, 465],
      [0, 555, 409, 469],
      [409, 555, 414, 469],
      [823, 555, 461, 469],
      [1284, 555, 491, 469],
    ],
    sequence: [2, 4, 5, 1, 6, 3, 0],
  },
  baby: {
    title: 'Baby announcement',
    sheet: '/assets/vault-boy/VaultBoy_AnimationsBaby.webp',
    canvas: [544, 520],
    frames: [
      [0, 45, 367, 483],
      [369, 45, 478, 483],
      [849, 65, 395, 476],
      [1, 530, 380, 494],
      [389, 533, 396, 491],
      [787, 543, 411, 481],
      [1200, 554, 424, 470],
    ],
    // Rest → lower hand → open fingers → curl → raise thumb → extend.
    sequence: [0, 2, 6, 5, 4, 3, 1],
  },
  ok: {
    title: 'All good',
    sheet: '/assets/vault-boy/VaultBoy_AnimationsOk.webp',
    canvas: [544, 520],
    frames: [
      [0, 110, 353, 459],
      [355, 111, 400, 458],
      [758, 105, 389, 469],
      [0, 571, 380, 453],
      [443, 576, 402, 448],
      [1149, 565, 464, 459],
      [1615, 556, 394, 468],
    ],
    sequence: [0, 3, 4, 1, 6, 2, 5],
  },
  'food-low': {
    title: 'Low food',
    sheet: '/assets/vault-boy/VaultBoy_AnimationsFoodLow.webp',
    canvas: [544, 520],
    frames: [
      [0, 13, 414, 505],
      [428, 95, 446, 458],
      [884, 51, 401, 495],
      [1314, 116, 391, 465],
      [0, 520, 426, 504],
      [428, 555, 454, 469],
      [884, 548, 428, 476],
      [1314, 583, 438, 441],
    ],
    // Raise the empty can, then tip it toward the mouth. Skip the near-duplicate low-hand pose.
    sequence: [7, 1, 6, 0, 4, 2, 3],
  },
  'water-low': {
    title: 'Low water',
    sheet: '/assets/vault-boy/VaultBoy_AnimationsWaterLow.webp',
    canvas: [544, 520],
    frames: [
      [0, 98, 470, 459],
      [477, 94, 459, 469],
      [959, 103, 459, 459],
      [1420, 113, 465, 453],
      [0, 559, 475, 465],
      [477, 565, 480, 459],
      [959, 564, 459, 460],
      [1420, 568, 463, 456],
    ],
    // Reach for the tap, turn the valve, then check the dry spout with an open palm.
    sequence: [2, 7, 6, 5, 0, 4],
  },
  'power-low': {
    title: 'Low power',
    sheet: '/assets/vault-boy/VaultBoy_AnimationsPowerLow.webp',
    canvas: [544, 520],
    frames: [
      [0, 94, 418, 464],
      [420, 117, 397, 448],
      [827, 98, 334, 466],
      [0, 560, 418, 464],
      [420, 567, 405, 457],
      [827, 566, 321, 458],
      [1211, 554, 294, 470],
      [1507, 554, 294, 470],
    ],
    // Candle goes out → lift lighter → ignite → lower lighter with the candle relit.
    sequence: [0, 3, 4, 5, 6, 7, 2],
  },
  'happiness-low': {
    title: 'Low happiness',
    sheet: '/assets/vault-boy/VaultBoy_AnimationsHappynessLow.webp',
    canvas: [544, 520],
    frames: [
      [0, 66, 363, 478],
      [365, 32, 343, 500],
      [1056, 45, 332, 510],
      [0, 546, 363, 478],
      [365, 534, 354, 490],
      [721, 511, 333, 513],
      [1056, 557, 363, 467],
      [1421, 565, 363, 459],
    ],
    // Open-eyed sigh → eyelids close → head settles into a slump.
    sequence: [5, 2, 1, 4, 7, 6, 3],
  },
  storage: {
    title: 'Storage full',
    sheet: '/assets/vault-boy/VaultBoy_AnimationsStorage.webp',
    canvas: [544, 520],
    frames: [
      [0, 30, 448, 488],
      [463, 48, 439, 477],
      [930, 72, 450, 474],
      [1398, 85, 448, 465],
      [0, 520, 451, 504],
      [463, 527, 456, 497],
      [930, 549, 461, 475],
      [1398, 552, 442, 472],
    ],
    // The load tips left, then right, before settling upright with a strained expression.
    sequence: [2, 6, 5, 4, 0, 1, 7, 3],
  },
}

export const VAULT_BOY_FRAME_MS = 180
