import scenes from './wasteland-scenes.json'

export type WastelandSceneId = keyof typeof scenes
export type WastelandSceneFrame = 'wide' | 'encounter'
export const WASTELAND_SCENES = scenes

interface SceneImage {
  src: string
  width: number
  height: number
}

export const widestSceneImage = (variants: readonly SceneImage[]): SceneImage | undefined =>
  variants.reduce<SceneImage | undefined>(
    (widest, image) => (!widest || image.width > widest.width ? image : widest),
    undefined
  )
