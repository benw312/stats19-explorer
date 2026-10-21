/** Self-hosted OSM basemap (Protomaps PMTiles) + collision layers. */

import { GRAYSCALE, type Flavor, layers } from '@protomaps/basemaps'
import type {
  CircleLayerSpecification,
  HeatmapLayerSpecification,
  StyleSpecification,
  SymbolLayerSpecification,
} from 'maplibre-gl'

import { SEVERITIES } from '../../lib/severity'

// Grayscale, warmed towards the paper tone so severity colours carry the weight.
const PAPER: Flavor = {
  ...GRAYSCALE,
  background: '#e9e6dd',
  earth: '#f2f0ea',
  water: '#d3dbde',
  park_a: '#e7eadf',
  park_b: '#e7eadf',
  wood_a: '#e3e7da',
  wood_b: '#e3e7da',
  buildings: '#e2ded3',
  roads_label_minor_halo: '#f2f0ea',
  roads_label_major_halo: '#f2f0ea',
  city_label_halo: '#f2f0ea',
  subplace_label_halo: '#f2f0ea',
  address_label_halo: '#f2f0ea',
}

export const COLLISION_SOURCE = 'collisions'
export const POINT_LAYER = 'collision-points'
export const SELECTED_LAYER = 'collision-selected'
export const BINS_LAYER = 'collision-bins'
export const BINS_LABEL_LAYER = 'collision-bins-label'
export const HEAT_LAYER = 'collision-heat'
// The server decides per tile: aggregated bins (zoomed out, or very dense areas) or points.
export const POINT_ZOOM = 11 // must match api/tiles.py

const severityColour = [
  'match',
  ['get', 'severity'],
  ...SEVERITIES.flatMap((s) => [s.code, s.hex]),
  '#7a8089',
] as unknown as string

export function baseStyle(origin: string): StyleSpecification {
  return {
    version: 8,
    glyphs: `${origin}/basemap/fonts/{fontstack}/{range}.pbf`,
    sprite: `${origin}/basemap/sprites/light`,
    sources: {
      protomaps: {
        type: 'vector',
        url: `pmtiles://${origin}/basemap/gb.pmtiles`,
        attribution:
          '© <a href="https://openstreetmap.org/copyright">OpenStreetMap</a> · ' +
          'Collision data © DfT (OGL) · Contains OS data © Crown copyright',
      },
    },
    layers: layers('protomaps', PAPER, { lang: 'en' }),
  }
}

export const collisionLayers = (): (
  CircleLayerSpecification | SymbolLayerSpecification | HeatmapLayerSpecification
)[] => [
  {
    id: HEAT_LAYER,
    type: 'heatmap',
    source: COLLISION_SOURCE,
    'source-layer': 'collision_bins',
    layout: { visibility: 'none' },
    paint: {
      'heatmap-weight': ['interpolate', ['linear'], ['get', 'n'], 0, 0, 50, 1],
      'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 5, 0.6, 10, 1.4],
      'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 5, 8, 10, 22],
      'heatmap-color': [
        'interpolate',
        ['linear'],
        ['heatmap-density'],
        0,
        'rgba(242,240,234,0)',
        0.2,
        '#f3d9a4',
        0.45,
        '#eda34c',
        0.7,
        '#c4521f',
        1,
        '#7c1a1d',
      ],
      'heatmap-opacity': 0.85,
    },
  },
  {
    id: BINS_LAYER,
    type: 'circle',
    source: COLLISION_SOURCE,
    'source-layer': 'collision_bins',
    paint: {
      'circle-color': '#1c2126',
      'circle-opacity': 0.42,
      'circle-radius': ['interpolate', ['linear'], ['sqrt', ['get', 'n']], 1, 2, 10, 5, 40, 10, 120, 15],
      'circle-stroke-color': '#1c2126',
      'circle-stroke-opacity': 0.55,
      'circle-stroke-width': 0.75,
    },
  },
  {
    id: BINS_LABEL_LAYER,
    type: 'symbol',
    source: COLLISION_SOURCE,
    'source-layer': 'collision_bins',
    filter: ['>=', ['get', 'n'], 100],
    layout: {
      'text-field': ['to-string', ['get', 'n']],
      'text-font': ['Noto Sans Medium'],
      'text-size': 10,
      'text-allow-overlap': false,
      'text-padding': 4,
    },
    paint: {
      'text-color': '#1c2126',
      'text-halo-color': 'rgba(242,240,234,0.9)',
      'text-halo-width': 1.4,
    },
  },
  {
    id: POINT_LAYER,
    type: 'circle',
    source: COLLISION_SOURCE,
    'source-layer': 'collisions',
    paint: {
      'circle-color': severityColour,
      // severity is also encoded by size, so colour is never the only cue
      'circle-radius': [
        'interpolate',
        ['linear'],
        ['zoom'],
        11,
        ['match', ['get', 'severity'], 1, 4, 2, 3, 2.2],
        16,
        ['match', ['get', 'severity'], 1, 9, 2, 7, 5.5],
      ],
      'circle-stroke-color': ['match', ['get', 'severity'], 1, '#1c2126', '#fbfaf7'],
      'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 11, 0.5, 16, 1.5],
      'circle-opacity': 0.92,
    },
  },
  {
    id: SELECTED_LAYER,
    type: 'circle',
    source: COLLISION_SOURCE,
    'source-layer': 'collisions',
    filter: ['==', ['get', 'id'], ''],
    paint: {
      'circle-color': 'rgba(0,0,0,0)',
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 11, 9, 16, 16],
      'circle-stroke-color': '#0a6b45',
      'circle-stroke-width': 3,
    },
  },
]
