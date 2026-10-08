import { describe, it, expect } from 'vitest'
import { clusterMarkers, DEFAULT_CLUSTER_CELL_SIZE } from '@/modules/map/utils/clusterMarkers'

describe('clusterMarkers', () => {
  it('returns no clusters for no points', () => {
    expect(clusterMarkers([])).toEqual([])
  })

  it('passes a lone point through as a singleton cluster at its exact position', () => {
    const clusters = clusterMarkers([{ id: 'a', x: 30, y: 40 }])

    expect(clusters).toHaveLength(1)
    expect(clusters[0].x).toBe(30)
    expect(clusters[0].y).toBe(40)
    expect(clusters[0].members).toEqual([{ id: 'a', x: 30, y: 40 }])
  })

  it('merges points sharing a cell into one cluster centered on them', () => {
    const clusters = clusterMarkers([
      { id: 'a', x: 20, y: 20 },
      { id: 'b', x: 24, y: 22 },
      { id: 'c', x: 30, y: 28 },
    ])

    expect(clusters).toHaveLength(1)
    expect(clusters[0].members.map((member) => member.id)).toEqual(['a', 'b', 'c'])
    expect(clusters[0].x).toBeCloseTo((20 + 24 + 30) / 3)
    expect(clusters[0].y).toBeCloseTo((20 + 22 + 28) / 3)
  })

  it('keeps points in different cells as separate clusters', () => {
    const clusters = clusterMarkers([
      { id: 'a', x: 10, y: 10 },
      { id: 'b', x: 90, y: 90 },
    ])

    expect(clusters).toHaveLength(2)
    expect(clusters.map((cluster) => cluster.members.map((member) => member.id))).toEqual([
      ['a'],
      ['b'],
    ])
  })

  it('splits a shared cell as zoom shrinks the cell size', () => {
    const points = [
      { id: 'a', x: 0, y: 0 },
      { id: 'b', x: 6, y: 0 },
    ]

    const overview = clusterMarkers(points, { zoom: 1 })
    expect(overview).toHaveLength(1)
    expect(overview[0].members).toHaveLength(2)

    const zoomed = clusterMarkers(points, { zoom: 4 })
    expect(zoomed).toHaveLength(2)
    expect(zoomed.every((cluster) => cluster.members.length === 1)).toBe(true)
  })

  it('honors a custom cell size', () => {
    const points = [
      { id: 'a', x: 0, y: 0 },
      { id: 'b', x: 6, y: 0 },
    ]

    expect(clusterMarkers(points, { cellSize: DEFAULT_CLUSTER_CELL_SIZE })).toHaveLength(1)
    expect(clusterMarkers(points, { cellSize: 4 })).toHaveLength(2)
  })

  it('is deterministic and independent of input order', () => {
    const points = [
      { id: 'delta', x: 21, y: 30 },
      { id: 'alpha', x: 20, y: 31 },
      { id: 'charlie', x: 90, y: 90 },
      { id: 'bravo', x: 22, y: 29 },
    ]

    const forward = clusterMarkers(points, { zoom: 2 })
    const reversed = clusterMarkers([...points].reverse(), { zoom: 2 })
    const repeat = clusterMarkers(points, { zoom: 2 })

    expect(reversed).toEqual(forward)
    expect(repeat).toEqual(forward)
    // Clusters come back in id order (cell keys sort lexicographically).
    expect(forward.map((cluster) => cluster.members.map((member) => member.id))).toEqual([
      ['charlie'],
      ['alpha', 'bravo', 'delta'],
    ])
  })
})
