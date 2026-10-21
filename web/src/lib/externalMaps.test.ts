import { describe, expect, it } from 'vitest'

import { googleAerialUrl, googleStreetViewUrl } from './externalMaps'

describe('Google Maps links', () => {
  it('opens aerial imagery at the point, one zoom level deeper than MapLibre', () => {
    const url = new URL(googleAerialUrl(-3.539497, 50.641734, 15.3))
    expect(url.origin + url.pathname).toBe('https://www.google.com/maps/@')
    expect(Object.fromEntries(url.searchParams)).toEqual({
      api: '1',
      map_action: 'map',
      center: '50.64173,-3.53950',
      zoom: '16',
      basemap: 'satellite',
    })
  })

  it('clamps the zoom to what Google accepts', () => {
    expect(new URL(googleAerialUrl(0, 51, 23)).searchParams.get('zoom')).toBe('21')
    expect(new URL(googleAerialUrl(0, 51, 0)).searchParams.get('zoom')).toBe('3')
  })

  it('opens Street View at the nearest panorama', () => {
    const url = new URL(googleStreetViewUrl(-3.5, 50.7))
    expect(url.searchParams.get('map_action')).toBe('pano')
    expect(url.searchParams.get('viewpoint')).toBe('50.70000,-3.50000')
  })
})
