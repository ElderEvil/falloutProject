import scenes from './wasteland-scenes.json'

export type WastelandSceneId = keyof typeof scenes
export type WastelandSceneRole = 'landscape' | 'battleback'
export const WASTELAND_SCENES = scenes
