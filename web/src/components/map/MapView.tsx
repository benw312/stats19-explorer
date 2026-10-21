import {
  type GeoJSONSource,
  Map as MlMap,
  type MapGeoJSONFeature,
  type MapLayerMouseEvent,
  type MapMouseEvent,
  NavigationControl,
  ScaleControl,
  type VectorTileSource,
  addProtocol,
  setWorkerUrl,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
// MapLibre 6 ships its worker as a separate ES module that imports a shared chunk.
// '?worker&url' makes Vite bundle the worker *with* its imports (plain '?url' doesn't,
// which breaks the map in production while working in dev).
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import { Protocol } from 'pmtiles'
import { useEffect, useRef } from 'react'
import { TerraDraw, TerraDrawPolygonMode, TerraDrawRectangleMode } from 'terra-draw'
import { TerraDrawMapLibreGLAdapter } from 'terra-draw-maplibre-gl-adapter'

import type { AreaDetail, Bbox } from '../../lib/api'
import { collisionTileUrl } from '../../lib/api'
import type { ApiFilter, AreaSel, LonLat } from '../../lib/filter'
import { type MapViewState, circleRing, parseMapHash } from '../../lib/geo'
import { type Site, sitesGeoJson } from '../../lib/hotspots'
import { junctionTileUrl } from '../../lib/junctions'
import { SITES_BADGE, SITES_BADGE_ACTIVE, SITES_FILL, SITES_SOURCE, addSiteLayers } from './siteLayers'
import { TRAFFIC_POINTS, addTrafficLayers, setSelectedCountPoint, setTrafficVisible } from './trafficLayers'
import {
  JUNCTION_RINGS,
  JUNCTION_SOURCE,
  addJunctionLayers,
  setJunctionRingsByCollisions,
  setJunctionsVisible,
  setSelectedJunction,
} from './junctionLayers'
import {
  RISK_FIRST_LAYER,
  RISK_JUNCTIONS,
  RISK_LINKS,
  addRiskLayers,
  setRiskSelection,
  setRiskVisible,
} from './riskLayers'
import { corridorBbox } from '../../lib/routes'
import { type RouteCollection, addRouteLayers, setRouteData, setRouteHover } from './routeLayers'
import {
  BINS_LABEL_LAYER,
  BINS_LAYER,
  COLLISION_SOURCE,
  HEAT_LAYER,
  POINT_LAYER,
  SELECTED_LAYER,
  baseStyle,
  collisionLayers,
} from './mapStyle'
import styles from './MapView.module.css'

const GB_BOUNDS: Bbox = [-8.7, 49.8, 1.9, 60.95]
const SELECTION_SOURCE = 'selection'
const ACCENT = '#0a6b45'
export const DEFAULT_RADIUS_M = 500

export type DrawMode = 'radius' | 'polygon' | 'rectangle'

let protocolRegistered = false
function registerPmtiles(): void {
  if (protocolRegistered) return
  setWorkerUrl(maplibreWorkerUrl)
  addProtocol('pmtiles', new Protocol().tile)
  protocolRegistered = true
}

export interface MapViewProps {
  filter: ApiFilter
  selectedId: string | null
  heatmap: boolean
  /** Changes whenever the map should fly somewhere: a box (search result, site) or a saved view. */
  flyTo: (({ bbox: Bbox } | { view: MapViewState }) & { key: number }) | null
  area: AreaSel | null
  /** Boundary geometry when the area is an authority (fetched by the parent). */
  authority: AreaDetail | undefined
  drawMode: DrawMode | null
  onSelect: (collisionIndex: string | null) => void
  onAreaDrawn: (area: AreaSel) => void
  /** Cluster sites to draw (hotspot view), with the selected and hovered ranks. */
  sites?: readonly Site[]
  selectedSite?: number | null
  hoverSite?: number | null
  onSiteClick?: (rank: number) => void
  onSiteHover?: (rank: number | null) => void
  /** DfT traffic count points layer, the open count point and its click handler. */
  traffic?: boolean
  selectedCountPoint?: number | null
  onCountPointClick?: (id: number) => void
  /** Junctions layer (from street zoom), the open junction and its click handler. */
  junctions?: boolean
  selectedJunction?: string | null
  onJunctionClick?: (id: string) => void
  /** Risk layer: roads and junctions banded by excess against similar sites. */
  risk?: boolean
  /** False in the Traffic view: collisions are hidden and junction rings stop sizing by them. */
  collisions?: boolean
  /** The open route's links (Routes view), and the link hovered in its strip chart. */
  route?: RouteCollection
  routeHover?: number | null
}

const NO_ROUTE: RouteCollection = { type: 'FeatureCollection', features: [] }

// Collisions fade back while traffic flows or the risk layer are shown, so the layers read apart.
const COLLISION_OPACITY = { normal: { point: 0.92, bins: 0.42 }, dimmed: { point: 0.3, bins: 0.14 } }

interface SelectionCollection {
  type: 'FeatureCollection'
  features: { type: 'Feature'; properties: Record<string, never>; geometry: unknown }[]
}

function selectionGeoJson(area: AreaSel | null, authority: AreaDetail | undefined): SelectionCollection {
  const empty: SelectionCollection = { type: 'FeatureCollection', features: [] }
  if (!area) return empty
  let geometry: unknown
  if (area.type === 'radius') {
    geometry = { type: 'Polygon', coordinates: [circleRing(area.lon, area.lat, area.radiusM)] }
  } else if (area.type === 'polygon') {
    geometry = { type: 'Polygon', coordinates: [area.ring] }
  } else if (authority?.code === area.code) {
    geometry = authority.geometry
  } else {
    return empty
  }
  return { type: 'FeatureCollection', features: [{ type: 'Feature', properties: {}, geometry }] }
}

// A shared link's #map= view must win over the default GB bounds. Read it once, when this
// chunk loads: removing a map (React StrictMode mounts twice in dev) clears the hash.
let pendingHashView = typeof window === 'undefined' ? null : parseMapHash(window.location.hash)

function applyCollisionVisibility(m: MlMap, collisions: boolean, heatmap: boolean): void {
  const show = (id: string, on: boolean) => {
    if (m.getLayer(id)) m.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none')
  }
  show(HEAT_LAYER, collisions && heatmap)
  show(BINS_LAYER, collisions && !heatmap)
  show(BINS_LABEL_LAYER, collisions)
  show(POINT_LAYER, collisions)
  show(SELECTED_LAYER, collisions)
  setJunctionRingsByCollisions(m, collisions)
}

function applyTrafficMode(m: MlMap, traffic: boolean): void {
  const o = traffic ? COLLISION_OPACITY.dimmed : COLLISION_OPACITY.normal
  if (m.getLayer(POINT_LAYER)) m.setPaintProperty(POINT_LAYER, 'circle-opacity', o.point)
  if (m.getLayer(BINS_LAYER)) m.setPaintProperty(BINS_LAYER, 'circle-opacity', o.bins)
}

export function MapView(props: MapViewProps) {
  const { filter, selectedId, heatmap, flyTo, area, authority, drawMode, onSelect, onAreaDrawn } = props
  const { sites = [], selectedSite = null, hoverSite = null, onSiteClick, onSiteHover } = props
  const { traffic = false, selectedCountPoint = null, onCountPointClick } = props
  const { junctions = false, selectedJunction = null, onJunctionClick, risk = false, collisions = true } = props
  const { route = NO_ROUTE, routeHover = null } = props
  const container = useRef<HTMLDivElement>(null)
  const map = useRef<MlMap | null>(null)
  const draw = useRef<TerraDraw | null>(null)
  const callbacks = useRef({ onSelect, onAreaDrawn, onSiteClick, onSiteHover, onCountPointClick, onJunctionClick })
  const drawModeRef = useRef(drawMode)
  const trafficRef = useRef(traffic)
  const countPointRef = useRef(selectedCountPoint)
  const junctionsRef = useRef(junctions)
  const junctionRef = useRef(selectedJunction)
  const riskRef = useRef(risk)
  const collisionsRef = useRef(collisions)
  const heatmapRef = useRef(heatmap)
  useEffect(() => {
    callbacks.current = { onSelect, onAreaDrawn, onSiteClick, onSiteHover, onCountPointClick, onJunctionClick }
    drawModeRef.current = drawMode
  }, [onSelect, onAreaDrawn, onSiteClick, onSiteHover, onCountPointClick, onJunctionClick, drawMode])
  const tileUrl = collisionTileUrl(filter)
  const tileUrlRef = useRef(tileUrl)
  const junctionUrl = junctionTileUrl(filter)
  const filterRef = useRef(filter)
  const selectionJson = JSON.stringify(selectionGeoJson(area, authority))
  const selectionRef = useRef(selectionJson)
  const sitesJson = JSON.stringify(sitesGeoJson(sites, selectedSite, hoverSite))
  const sitesRef = useRef(sitesJson)
  const routeRef = useRef(route)

  // create once
  useEffect(() => {
    if (!container.current) return
    registerPmtiles()
    const initialView = pendingHashView
    const m = new MlMap({
      container: container.current,
      style: baseStyle(window.location.origin),
      bounds: initialView ? undefined : GB_BOUNDS,
      maxBounds: [-14, 48, 6, 62],
      hash: 'map',
      attributionControl: { compact: true },
    })
    m.addControl(new NavigationControl({ visualizePitch: false }), 'top-right')
    m.addControl(new ScaleControl({ unit: 'metric' }), 'bottom-left')

    m.on('load', () => {
      if (initialView) m.jumpTo(initialView)
      pendingHashView = null
      m.addSource(SELECTION_SOURCE, { type: 'geojson', data: JSON.parse(selectionRef.current) })
      m.addLayer({
        id: 'selection-fill',
        type: 'fill',
        source: SELECTION_SOURCE,
        paint: { 'fill-color': ACCENT, 'fill-opacity': 0.06 },
      })
      m.addLayer({
        id: 'selection-line',
        type: 'line',
        source: SELECTION_SOURCE,
        paint: { 'line-color': ACCENT, 'line-width': 2 },
      })
      m.addSource(COLLISION_SOURCE, {
        type: 'vector',
        tiles: [tileUrlRef.current],
        minzoom: 0,
        maxzoom: 16,
        attribution: '',
      })
      for (const layer of collisionLayers()) m.addLayer(layer)
      addJunctionLayers(m, filterRef.current, junctionsRef.current, POINT_LAYER)
      setSelectedJunction(m, junctionRef.current)
      addRiskLayers(m, riskRef.current, POINT_LAYER)
      setRiskSelection(m, countPointRef.current, junctionRef.current)
      addRouteLayers(m, routeRef.current, RISK_FIRST_LAYER)
      addTrafficLayers(m, trafficRef.current)
      applyTrafficMode(m, trafficRef.current || riskRef.current)
      setSelectedCountPoint(m, countPointRef.current)
      addSiteLayers(m, JSON.parse(sitesRef.current))
      applyCollisionVisibility(m, collisionsRef.current, heatmapRef.current)

      const shapeStyle = {
        fillColor: ACCENT,
        fillOpacity: 0.08,
        outlineColor: ACCENT,
        outlineWidth: 2,
      } as const
      const td = new TerraDraw({
        adapter: new TerraDrawMapLibreGLAdapter({ map: m }),
        modes: [
          new TerraDrawPolygonMode({
            styles: {
              ...shapeStyle,
              closingPointColor: ACCENT,
              closingPointWidth: 5,
              closingPointOutlineColor: '#ffffff',
              closingPointOutlineWidth: 2,
            },
          }),
          new TerraDrawRectangleMode({ styles: shapeStyle }),
        ],
      })
      td.start()
      td.on('finish', (id) => {
        const feature = td.getSnapshotFeature(id)
        const ring = (feature?.geometry.coordinates as LonLat[][] | undefined)?.[0]
        td.clear()
        if (ring && ring.length >= 4) callbacks.current.onAreaDrawn({ type: 'polygon', ring })
      })
      draw.current = td
    })

    // Radius tool: one click sets the centre (the slider sets the radius).
    m.on('click', (e: MapMouseEvent) => {
      if (drawModeRef.current !== 'radius') return
      callbacks.current.onAreaDrawn({
        type: 'radius',
        lon: e.lngLat.lng,
        lat: e.lngLat.lat,
        radiusM: DEFAULT_RADIUS_M,
      })
    })
    // A traffic count point under the cursor wins over collisions beneath it.
    // So does a risk-layer road or junction (collisions are dimmed beneath it).
    const over = (e: MapLayerMouseEvent, on: boolean, layers: string[]): boolean =>
      on && m.queryRenderedFeatures(e.point, { layers }).length > 0
    const overTraffic = (e: MapLayerMouseEvent): boolean =>
      over(e, trafficRef.current, [TRAFFIC_POINTS]) || over(e, riskRef.current, [RISK_JUNCTIONS])
    // A risk junction wins over the road it sits on; a junction ring or count point over a
    // risk road wins over the road.
    m.on('click', RISK_JUNCTIONS, (e: MapLayerMouseEvent) => {
      if (drawModeRef.current) return
      const id = e.features?.[0]?.properties?.id
      if (typeof id === 'string') callbacks.current.onJunctionClick?.(id)
    })
    m.on('click', RISK_LINKS, (e: MapLayerMouseEvent) => {
      if (drawModeRef.current) return
      if (over(e, true, [RISK_JUNCTIONS]) || over(e, trafficRef.current, [TRAFFIC_POINTS])) return
      if (over(e, junctionsRef.current, [JUNCTION_RINGS]) || over(e, true, [SITES_BADGE, SITES_BADGE_ACTIVE])) return
      const id = e.features?.[0]?.properties?.id
      if (typeof id === 'number') callbacks.current.onCountPointClick?.(id)
    })
    m.on('click', TRAFFIC_POINTS, (e: MapLayerMouseEvent) => {
      if (drawModeRef.current) return
      if (over(e, riskRef.current, [RISK_JUNCTIONS])) return
      const id = e.features?.[0]?.properties?.id
      if (typeof id === 'number') callbacks.current.onCountPointClick?.(id)
    })
    const overRiskLink = (e: MapLayerMouseEvent): boolean => over(e, riskRef.current, [RISK_LINKS])
    // A junction ring: a collision point inside it, or a count point, wins the click
    // (but collisions give way to the risk layer).
    m.on('click', JUNCTION_RINGS, (e: MapLayerMouseEvent) => {
      if (drawModeRef.current || overTraffic(e)) return
      if (!overRiskLink(e) && over(e, true, [POINT_LAYER])) return
      const id = e.features?.[0]?.properties?.id
      if (typeof id === 'string') callbacks.current.onJunctionClick?.(id)
    })
    m.on('click', POINT_LAYER, (e: MapLayerMouseEvent) => {
      if (drawModeRef.current || overTraffic(e) || overRiskLink(e)) return
      const feature: MapGeoJSONFeature | undefined = e.features?.[0]
      const id = feature?.properties?.id
      callbacks.current.onSelect(typeof id === 'string' ? id : null)
    })
    m.on('click', BINS_LAYER, (e: MapLayerMouseEvent) => {
      if (drawModeRef.current || overTraffic(e) || overRiskLink(e)) return
      m.easeTo({ center: e.lngLat, zoom: Math.min(m.getZoom() + 2.5, 14) })
    })
    // A cluster site: click the circle or its number (a collision point inside wins).
    for (const layer of [SITES_FILL, SITES_BADGE, SITES_BADGE_ACTIVE]) {
      m.on('click', layer, (e: MapLayerMouseEvent) => {
        if (drawModeRef.current) return
        if (layer === SITES_FILL && m.queryRenderedFeatures(e.point, { layers: [POINT_LAYER] }).length) return
        if (overTraffic(e)) return
        const rank = e.features?.[0]?.properties?.rank
        if (typeof rank === 'number') callbacks.current.onSiteClick?.(rank)
      })
      m.on('mousemove', layer, (e: MapLayerMouseEvent) => {
        const rank = e.features?.[0]?.properties?.rank
        callbacks.current.onSiteHover?.(typeof rank === 'number' ? rank : null)
      })
      m.on('mouseleave', layer, () => callbacks.current.onSiteHover?.(null))
    }
    for (const layer of [
      POINT_LAYER,
      BINS_LAYER,
      SITES_BADGE,
      SITES_BADGE_ACTIVE,
      TRAFFIC_POINTS,
      JUNCTION_RINGS,
      RISK_LINKS,
      RISK_JUNCTIONS,
    ]) {
      m.on('mouseenter', layer, () => {
        if (!drawModeRef.current) m.getCanvas().style.cursor = 'pointer'
      })
      m.on('mouseleave', layer, () => {
        if (!drawModeRef.current) m.getCanvas().style.cursor = ''
      })
    }
    map.current = m
    // dev-only handle for visual tests (tree-shaken from production builds)
    if (import.meta.env.DEV) (window as unknown as { __map?: MlMap }).__map = m
    return () => {
      draw.current?.stop()
      draw.current = null
      m.remove()
      map.current = null
    }
  }, [])

  // filter -> tile URL
  useEffect(() => {
    tileUrlRef.current = tileUrl
    const source = map.current?.getSource(COLLISION_SOURCE) as VectorTileSource | undefined
    source?.setTiles([tileUrl])
  }, [tileUrl])

  // filter -> junction tile URL (ring sizes count the filtered collisions)
  useEffect(() => {
    filterRef.current = filter
    const source = map.current?.getSource(JUNCTION_SOURCE) as VectorTileSource | undefined
    source?.setTiles([junctionUrl])
  }, [junctionUrl]) // eslint-disable-line react-hooks/exhaustive-deps -- the URL encodes the filter

  // junctions layer toggle and the open junction
  useEffect(() => {
    junctionsRef.current = junctions
    const m = map.current
    if (m) setJunctionsVisible(m, junctions)
  }, [junctions])

  useEffect(() => {
    junctionRef.current = selectedJunction
    const m = map.current
    if (m) setSelectedJunction(m, selectedJunction)
    if (m) setRiskSelection(m, countPointRef.current, selectedJunction)
  }, [selectedJunction])

  // selection outline
  useEffect(() => {
    selectionRef.current = selectionJson
    const source = map.current?.getSource(SELECTION_SOURCE) as GeoJSONSource | undefined
    source?.setData(JSON.parse(selectionJson))
  }, [selectionJson])

  // cluster sites
  useEffect(() => {
    sitesRef.current = sitesJson
    const source = map.current?.getSource(SITES_SOURCE) as GeoJSONSource | undefined
    source?.setData(JSON.parse(sitesJson))
  }, [sitesJson])

  // draw mode
  useEffect(() => {
    const m = map.current
    if (!m) return
    draw.current?.setMode(drawMode === 'polygon' || drawMode === 'rectangle' ? drawMode : 'static')
    m.getCanvas().style.cursor = drawMode ? 'crosshair' : ''
  }, [drawMode])

  // selection highlight
  useEffect(() => {
    const m = map.current
    if (!m?.getLayer(SELECTED_LAYER)) return
    m.setFilter(SELECTED_LAYER, ['==', ['get', 'id'], selectedId ?? ''])
  }, [selectedId])

  // traffic layer toggle (and dim collisions under it)
  useEffect(() => {
    trafficRef.current = traffic
    const m = map.current
    if (!m?.getLayer(TRAFFIC_POINTS)) return
    setTrafficVisible(m, traffic)
    applyTrafficMode(m, traffic || riskRef.current)
  }, [traffic])

  // risk layer toggle (and dim collisions under it)
  useEffect(() => {
    riskRef.current = risk
    const m = map.current
    if (!m?.getLayer(RISK_LINKS)) return
    setRiskVisible(m, risk)
    applyTrafficMode(m, risk || trafficRef.current)
  }, [risk])

  // open count point ring
  useEffect(() => {
    countPointRef.current = selectedCountPoint
    const m = map.current
    if (m) setSelectedCountPoint(m, selectedCountPoint)
    if (m) setRiskSelection(m, selectedCountPoint, junctionRef.current)
  }, [selectedCountPoint])

  // heat map toggle, and collisions hidden altogether in the Traffic view
  useEffect(() => {
    heatmapRef.current = heatmap
    collisionsRef.current = collisions
    const m = map.current
    if (m?.getLayer(HEAT_LAYER)) applyCollisionVisibility(m, collisions, heatmap)
  }, [heatmap, collisions])

  // fit a newly loaded authority boundary
  const authorityCode = authority?.code
  useEffect(() => {
    if (!authority || !map.current) return
    const [w, s, e, n] = authority.bbox
    map.current.fitBounds(
      [
        [w, s],
        [e, n],
      ],
      { padding: 40, duration: 900 },
    )
  }, [authorityCode]) // eslint-disable-line react-hooks/exhaustive-deps -- refit only when the code changes

  // fly to
  // the open route (fitted when it arrives) and the link hovered in its strip chart
  useEffect(() => {
    routeRef.current = route
    const m = map.current
    if (!m) return
    setRouteData(m, route)
    const box = corridorBbox(route.features)
    if (box) {
      m.fitBounds(
        [
          [box[0], box[1]],
          [box[2], box[3]],
        ],
        { padding: 48, duration: 900, maxZoom: 14 },
      )
    }
  }, [route])

  useEffect(() => {
    const m = map.current
    if (m) setRouteHover(m, routeHover)
  }, [routeHover])

  useEffect(() => {
    if (!flyTo || !map.current) return
    if ('view' in flyTo) {
      map.current.flyTo({ center: flyTo.view.center, zoom: flyTo.view.zoom, duration: 900 })
      return
    }
    const [w, s, e, n] = flyTo.bbox
    map.current.fitBounds(
      [
        [w, s],
        [e, n],
      ],
      { padding: 60, maxZoom: 16, duration: 900 },
    )
  }, [flyTo])

  return <div ref={container} className={styles.map} role="region" aria-label="Collision map" />
}
