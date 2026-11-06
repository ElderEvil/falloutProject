export interface Transform {
  x: number
  y: number
  rotation: number
  scale_x: number
  scale_y: number
}
export interface Matrix {
  a: number
  b: number
  c: number
  d: number
  tx: number
  ty: number
}
export interface Attachment {
  name: string
  image: string
  width: number
  height: number
}
export interface Animation {
  name: string
  duration: number
}
export interface Skeleton {
  bones: Array<{ name: string; parent: number | null; setup: Transform }>
  slots: Array<{ name: string; bone: number; attachment: string | null }>
  animations: Animation[]
  skin: string | null
  validate(): string | null
}
export class Pose {
  constructor(skeleton: Skeleton)
  local: Transform[]
  world: Matrix[]
  attachment: Array<string | null>
  color: number[][]
  reset(skeleton: Skeleton): void
  apply(skeleton: Skeleton, animation: Animation, time: number, alpha: number): void
  updateWorld(skeleton: Skeleton): void
  slotAttachment(skeleton: Skeleton, slot: number): Attachment | null
}
export interface TextureEntry {
  tex: { texture: WebGLTexture }
}
export type TextureLookup = (name: string) => TextureEntry | null
export function readSkeletonJson(
  json: unknown,
  name?: string
): { skeleton: Skeleton; warnings: string[] }
export function writeSkeletonJson(skeleton: Skeleton): {
  json: Record<string, unknown>
  warnings: string[]
}
export function parseAtlas(text: string): unknown
export class WebGLRenderer {
  constructor(gl: WebGLRenderingContext)
  drawCalls: number
  atlasTextures(atlas: unknown, images: Record<string, HTMLImageElement>): TextureLookup
  imageTextures(images: Record<string, HTMLImageElement>): TextureLookup
  begin(width: number, height: number, camera: { x: number; y: number; zoom: number }): void
  drawSkeleton(skeleton: Skeleton, pose: Pose, lookup: TextureLookup): void
  end(): void
  dispose(): void
}
