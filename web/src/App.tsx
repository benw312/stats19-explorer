import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react'

import styles from './App.module.css'
import { CollisionPanel } from './components/collision/CollisionPanel'
import { FeedbackButton } from './components/feedback/FeedbackDialog'
import { FilterSheet } from './components/filters/FilterSheet'
import { HotspotPanel } from './components/hotspots/HotspotPanel'
import { JunctionPanel } from './components/junctions/JunctionPanel'
import { JunctionSite } from './components/site/JunctionSite'
import { RoadSite } from './components/site/RoadSite'
import { DrawTools } from './components/map/DrawTools'
import { Legend } from './components/map/Legend'
import type { DrawMode, MapViewProps } from './components/map/MapView'
import { routeGeoJson } from './components/map/routeLayers'
import { RoutesPanel } from './components/routes/RoutesPanel'
import { SchemesPanel } from './components/schemes/SchemesPanel'
import { SearchBox } from './components/search/SearchBox'
import { ExcessSitesPanel } from './components/sites/ExcessSitesPanel'
import { SiteMethodSwitch } from './components/sites/SiteMethodSwitch'
import { SummaryPanel } from './components/summary/SummaryPanel'
import { TrafficPanel } from './components/traffic/TrafficPanel'
import { useUrlFilter } from './hooks/useUrlFilter'
import { useUrlParam } from './hooks/useUrlParam'
import { ApiRequestError, type Meta, getArea, getMeta } from './lib/api'
import {
  type AreaSel,
  type BoundaryType,
  DEFAULT_SPAN_YEARS,
  type UiFilter,
  activeCount,
  toApiFilter,
} from './lib/filter'
import { type MapViewState, circleRing, parseMapHash, ringBbox, unionBbox } from './lib/geo'
import {
  type HotspotParams,
  decodeParams,
  decodeSiteParam,
  encodeParams,
  encodeSiteParam,
  getHotspots,
  siteBbox,
} from './lib/hotspots'
import { getCorridor, parseRoute } from './lib/routes'
import { areaDraft } from './lib/schemes'
import { type SiteMethod, parseSiteMethod } from './lib/siteMethods'

// MapLibre is the bulk of the JS: load it after the shell renders.
const MapView = lazy(() => import('./components/map/MapView').then((m) => ({ default: m.MapView })))

const NEARBY_DEG = 0.004 // ~300-400 m box around a single collision

export default function App() {
  const meta = useQuery({ queryKey: ['meta'], queryFn: ({ signal }) => getMeta(signal), staleTime: Infinity })

  if (meta.isError) {
    return (
      <main className={styles.fatal} role="alert">
        <h1>STATS19 explorer</h1>
        <p>The data service isn’t reachable. Check that the API container is running.</p>
      </main>
    )
  }
  if (!meta.data) {
    return (
      <main className={styles.fatal} aria-busy>
        <p className="eyebrow">Loading data catalogue…</p>
      </main>
    )
  }
  return <Explorer meta={meta.data} />
}

const NARROW_QUERY = '(max-width: 900px)' // matches App.module.css
const SHEET_PREF_KEY = 'stats19.filters'

// A per-viewer convenience: storage can be unavailable (private windows), so never rely on it.
function readSheetPref(): string | null {
  try {
    return window.localStorage.getItem(SHEET_PREF_KEY)
  } catch {
    return null
  }
}

function writeSheetPref(value: 'open' | 'closed'): void {
  try {
    window.localStorage.setItem(SHEET_PREF_KEY, value)
  } catch {
    // not stored: the sheet just opens next time
  }
}
const isNarrow = (): boolean => window.matchMedia(NARROW_QUERY).matches

function areaPhrase(area: AreaSel | null, authorityName: string | undefined): string {
  if (area?.type === 'authority') return authorityName ?? 'the authority'
  if (area?.type === 'radius') return 'the selected circle'
  if (area?.type === 'polygon') return 'the drawn area'
  return 'Great Britain'
}

/** The top-level views (PLAN-009). */
type View = 'area' | 'sites' | 'routes' | 'traffic' | 'schemes'
const VIEWS: readonly { id: View; label: string }[] = [
  { id: 'area', label: 'Area' },
  { id: 'sites', label: 'Sites' },
  { id: 'routes', label: 'Routes' },
  { id: 'traffic', label: 'Traffic' },
  { id: 'schemes', label: 'Schemes' },
]

const SCHEME_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

const AREA_ONLY_NOTE: Partial<Record<View, string>> = {
  traffic:
    'Traffic shows DfT flows only, so just the area applies here. The other filters are about collisions and come back in Area and Sites.',
  routes:
    'Routes compare each road with similar ones over the safety model’s last five years, so just the area applies here. The other filters come back in Area and Sites.',
  schemes:
    'Schemes count collisions in their own saved footprints and periods, so the filters don’t apply here. They come back in Area and Sites.',
}

/** The URL's view, with links from before PLAN-009 mapped on (hotspots → Sites, clusters). */
function parseView(raw: string | null): View | null {
  if (raw === 'hotspots') return 'sites'
  return VIEWS.some((v) => v.id === raw) ? (raw as View) : null
}

function Explorer({ meta }: { meta: Meta }) {
  const [filter, setUrlFilter] = useUrlFilter(meta.coverage.last_year)
  const apiFilter = useMemo(() => toApiFilter(filter), [filter])
  const [selected, setSelected] = useState<string | null>(null)
  const [viewRaw, setViewRaw] = useUrlParam('view')
  const [smRaw, setSmRaw] = useUrlParam('sm')
  const [hsRaw, setHsRaw] = useUrlParam('hs')
  const [siteRaw, setSiteRaw] = useUrlParam('site')
  const view = parseView(viewRaw)
  const siteMethod: SiteMethod = viewRaw === 'hotspots' ? 'clusters' : parseSiteMethod(smRaw)
  const hotspotsOpen = view === 'sites' && siteMethod === 'clusters'
  const excessOpen = view === 'sites' && siteMethod === 'excess'
  const trafficOpen = view === 'traffic'
  const routesOpen = view === 'routes'
  const [scRaw, setScRaw] = useUrlParam('sc')
  const schemeId = scRaw && SCHEME_ID.test(scRaw) ? scRaw : null
  const [rtRaw, setRtRaw] = useUrlParam('rt')
  const road = parseRoute(rtRaw)
  const [routeHover, setRouteHover] = useState<number | null>(null)
  const setView = useCallback((next: View | null) => setViewRaw(next), [setViewRaw])
  const [cpRaw, setCpRaw] = useUrlParam('cp')
  const countPoint = cpRaw && /^\d{1,9}$/.test(cpRaw) ? Number(cpRaw) : null
  const [trafficLayer, setTrafficLayer] = useState(trafficOpen)
  const [jnRaw, setJnRaw] = useUrlParam('jn')
  const junctionId = jnRaw && /^[0-9A-Za-z_-]{1,64}$/.test(jnRaw) ? jnRaw : null
  const [junctionLayer, setJunctionLayer] = useState(junctionId !== null)
  const [riskLayer, setRiskLayer] = useState(excessOpen || routesOpen)
  const hsParams = useMemo(() => decodeParams(hsRaw), [hsRaw])
  const siteParam = decodeSiteParam(siteRaw)
  const siteRank = siteParam?.rank ?? null
  const [hoverSite, setHoverSite] = useState<number | null>(null)
  const [wide, setWide] = useState(false)
  // Site pages (junction, road, cluster) open wide on desktop (PLAN-009 V3).
  const [siteWide, setSiteWide] = useState(true)
  const [heatmap, setHeatmap] = useState(false)
  const [flyTo, setFlyTo] = useState<MapViewProps['flyTo']>(null)
  // Desktop remembers whether the filters were folded away; phones always start closed.
  const [sheetOpen, setSheetOpen] = useState(() => !isNarrow() && readSheetPref() !== 'closed')
  // The user's own show/hide (the header button, the sheet's Hide): remembered on desktop.
  const showSheet = (open: boolean) => {
    setSheetOpen(open)
    if (!isNarrow()) writeSheetPref(open ? 'open' : 'closed')
  }
  const [drawMode, setDrawMode] = useState<DrawMode | null>(null)
  const [boundaryType, setBoundaryType] = useState<BoundaryType>(
    filter.area?.type === 'authority' ? filter.area.boundaryType : 'highway_authority',
  )
  // Site ranks belong to one run: a new filter or method clears the open site.
  const setFilter = useCallback(
    (next: UiFilter) => {
      setUrlFilter(next)
      setSiteRaw(null)
    },
    [setUrlFilter, setSiteRaw],
  )
  const setHsParams = (p: HotspotParams) => {
    setHsRaw(encodeParams(p) || null)
    setSiteRaw(null)
  }

  const area = filter.area
  const authorityKey = area?.type === 'authority' ? `${area.boundaryType}/${area.code}` : null

  const authority = useQuery({
    queryKey: ['area', authorityKey],
    queryFn: ({ signal }) => {
      if (area?.type !== 'authority') throw new Error('no authority selected')
      return getArea(area.boundaryType, area.code, signal)
    },
    enabled: authorityKey !== null,
    staleTime: Infinity,
  })

  const hotspots = useQuery({
    queryKey: ['hotspots', JSON.stringify(apiFilter), JSON.stringify(hsParams)],
    queryFn: ({ signal }) => getHotspots(apiFilter, hsParams, signal),
    // Both Sites methods: "worse than expected" rows and site pages link the cluster they're in.
    enabled: view === 'sites' && area !== null,
    placeholderData: keepPreviousData,
    retry: (count, error) => !(error instanceof ApiRequestError && error.code === 'too_large') && count < 1,
  })
  const sites = hotspotsOpen && area ? (hotspots.data?.sites ?? []) : []
  const clusterSites = view === 'sites' && area ? (hotspots.data?.sites ?? []) : []

  const corridor = useQuery({
    queryKey: ['corridor', road, JSON.stringify(apiFilter.area ?? null)],
    queryFn: ({ signal }) => {
      if (road === null) throw new Error('no route selected')
      return getCorridor(road, apiFilter.area, signal)
    },
    enabled: routesOpen && road !== null,
    placeholderData: keepPreviousData,
  })
  const routeLinks = routesOpen && road !== null && !corridor.isPlaceholderData ? corridor.data?.links : undefined
  const routeGeo = useMemo(() => routeGeoJson(routeLinks ?? null), [routeLinks])

  // Old links: view=hotspots becomes Sites → Clusters; an area with no view opens Area.
  useEffect(() => {
    if (viewRaw === 'hotspots') {
      setSmRaw('clusters')
      setViewRaw('sites')
    } else if (viewRaw === null && filter.area !== null) {
      setViewRaw('area')
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps -- once, on load

  // Shrinking a desktop window to narrow: the sheet and panels overlay the map there,
  // so close the sheet rather than show both at once (FU-014).
  useEffect(() => {
    const narrow = window.matchMedia(NARROW_QUERY)
    const onChange = (e: MediaQueryListEvent) => {
      if (e.matches) setSheetOpen(false)
    }
    narrow.addEventListener('change', onChange)
    return () => narrow.removeEventListener('change', onChange)
  }, [])

  // Esc cancels drawing.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setDrawMode(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const setArea = useCallback(
    (next: AreaSel | null) => {
      setFilter({ ...filter, area: next })
      if (next) {
        if (view === null) setView('area')
        setSelected(null)
      }
    },
    [filter, setFilter, view, setView],
  )

  const onAreaDrawn = useCallback(
    (drawn: AreaSel) => {
      setDrawMode(null)
      setArea(drawn)
      if (drawn.type === 'radius') {
        setFlyTo({ bbox: ringBbox(circleRing(drawn.lon, drawn.lat, drawn.radiusM)), key: Date.now() })
      }
    },
    [setArea],
  )

  const select = useCallback((id: string | null) => {
    setSelected(id)
    if (id && isNarrow()) setSheetOpen(false)
  }, [])

  const openFromList = (id: string, lonLat: [number, number] | null) => {
    select(id)
    if (lonLat) {
      const [x, y] = lonLat
      setFlyTo({ bbox: [x - NEARBY_DEG, y - NEARBY_DEG, x + NEARBY_DEG, y + NEARBY_DEG], key: Date.now() })
    }
  }

  // The map view before a site was opened, so "All sites" can return to it (FU-027).
  const viewBeforeSite = useRef<MapViewState | null>(null)
  const openSite = (rank: number | null) => {
    setSelected(null)
    if (rank === null) {
      setSiteRaw(null)
      const saved = viewBeforeSite.current
      viewBeforeSite.current = null
      const allSites = unionBbox(sites.map((x) => siteBbox(x)))
      if (saved) setFlyTo({ view: saved, key: Date.now() })
      else if (allSites) setFlyTo({ bbox: allSites, key: Date.now() })
      return
    }
    if (siteRank === null) viewBeforeSite.current = parseMapHash(window.location.hash)
    setSiteRaw(encodeSiteParam(rank, hotspots.data?.data_load ?? null))
    const site = sites.find((x) => x.rank === rank)
    if (site) setFlyTo({ bbox: siteBbox({ ...site, radius_m: site.radius_m * 3 }), key: Date.now() })
  }

  const openCountPoint = useCallback(
    (id: number | null) => {
      setCpRaw(id === null ? null : String(id))
      if (id !== null) {
        setSelected(null)
        setJnRaw(null)
        if (isNarrow()) setSheetOpen(false)
      }
    },
    [setCpRaw, setJnRaw],
  )

  // From a junction or road page to the cluster site containing it (Sites → Clusters).
  const openCluster = (rank: number) => {
    setJnRaw(null)
    setCpRaw(null)
    setSmRaw('clusters')
    setViewRaw('sites')
    setSiteRaw(encodeSiteParam(rank, hotspots.data?.data_load ?? null))
    const site = clusterSites.find((x) => x.rank === rank)
    if (site) setFlyTo({ bbox: siteBbox({ ...site, radius_m: site.radius_m * 3 }), key: Date.now() })
  }

  const openJunction = useCallback(
    (id: string) => {
      setSelected(null)
      setJnRaw(id)
      if (isNarrow()) setSheetOpen(false)
    },
    [setJnRaw],
  )

  const closeView = () => {
    setView(null)
    setCpRaw(null)
  }

  // A saved scheme (V5): from "Save as scheme" anywhere, or the Schemes list.
  const openScheme = (id: string | null) => {
    setSelected(null)
    setJnRaw(null)
    setCpRaw(null)
    setScRaw(id)
    if (id !== null) setView('schemes')
  }
  const zoomToBbox = useCallback((bbox: [number, number, number, number]) => setFlyTo({ bbox, key: Date.now() }), [])

  // A view brings the layers it needs; leaving one keeps whatever the user has on.
  const openView = (next: View) => {
    setSelected(null)
    setJnRaw(null)
    setCpRaw(null)
    if (view === next) {
      setView(null)
      return
    }
    if (next === 'traffic') setTrafficLayer(true)
    if ((next === 'sites' && siteMethod === 'excess') || next === 'routes') setRiskLayer(true)
    setView(next)
  }

  const setSiteMethod = (m: SiteMethod) => {
    setSmRaw(m === 'excess' ? null : m)
    setSiteRaw(null)
    setJnRaw(null)
    setCpRaw(null)
    if (m === 'excess') setRiskLayer(true)
  }
  const openRoad = (next: string | null) => {
    setRtRaw(next)
    setRouteHover(null)
    setJnRaw(null)
    setCpRaw(null)
  }
  const methodSwitch = <SiteMethodSwitch method={siteMethod} onMethod={setSiteMethod} />

  const zoomTo = ([x, y]: [number, number]) =>
    setFlyTo({
      bbox: [x - NEARBY_DEG * 2, y - NEARBY_DEG * 2, x + NEARBY_DEG * 2, y + NEARBY_DEG * 2],
      key: Date.now(),
    })

  const roadOpen = countPoint !== null && !trafficOpen
  const panel = selected
    ? 'record'
    : junctionId
      ? 'junction'
      : roadOpen
        ? 'road'
        : hotspotsOpen
          ? 'clusters'
          : excessOpen
            ? 'excess'
            : (view ?? null)
  const schemePageOpen = panel === 'schemes' && schemeId !== null

  const activeFilters = activeCount(filter, meta.coverage.last_year)
  const sitePageOpen =
    (panel === 'junction' && !trafficOpen) ||
    panel === 'road' ||
    (panel === 'clusters' && siteRank !== null) ||
    schemePageOpen
  const isWide = sitePageOpen ? siteWide : (panel === 'area' || panel === 'clusters' || panel === 'schemes') && wide
  const sitePageProps = {
    filter: apiFilter,
    clusters: clusterSites,
    onCluster: openCluster,
    onCountPoint: openCountPoint,
    onJunction: openJunction,
    onZoom: zoomTo,
    onOpenCollision: openFromList,
    onOpenScheme: openScheme,
    wide: siteWide,
    onToggleWide: () => setSiteWide(!siteWide),
  }

  return (
    <div
      className={styles.shell}
      data-panel={panel ? 'open' : 'closed'}
      data-sheet={sheetOpen ? 'open' : 'closed'}
      data-wide={isWide ? (sitePageOpen ? 'site' : 'yes') : 'no'}
    >
      <header className={styles.header}>
        <div className={styles.brand}>
          <span className={styles.mark} aria-hidden />
          <h1 className={styles.name}>
            STATS19 <span>explorer</span>
          </h1>
        </div>
        <button
          type="button"
          className={styles.sheetToggle}
          aria-expanded={sheetOpen}
          aria-controls="filter-sheet"
          title={sheetOpen ? 'Hide filters' : 'Show filters'}
          onClick={() => showSheet(!sheetOpen)}
        >
          Filters
          {activeFilters > 0 && <span className={styles.toggleCount}>{activeFilters}</span>}
        </button>
        <SearchBox onPick={(r) => setFlyTo({ bbox: r.bbox, key: Date.now() })} />
        <nav className={styles.views} aria-label="Views">
          {VIEWS.map((v) => (
            <button
              key={v.id}
              type="button"
              className={styles.viewTab}
              aria-pressed={view === v.id}
              onClick={() => openView(v.id)}
            >
              {v.label}
            </button>
          ))}
        </nav>
        <p className={styles.coverage}>
          <span className="eyebrow">Data</span>{' '}
          <span className="mono">
            {meta.coverage.first_year}–{meta.coverage.last_year}
          </span>{' '}
          · {meta.coverage.collisions.toLocaleString('en-GB')} collisions ·{' '}
          <a className={styles.aboutLink} href="/about" target="_blank" rel="noopener">
            About the data
          </a>
        </p>
        <FeedbackButton className={styles.feedback} />
      </header>

      <div className={styles.sheet} id="filter-sheet">
        <FilterSheet
          meta={meta}
          filter={filter}
          onChange={setFilter}
          boundaryType={boundaryType}
          onBoundaryType={setBoundaryType}
          onArea={setArea}
          areaOnly={view ? AREA_ONLY_NOTE[view] : undefined}
          onHide={() => showSheet(false)}
        />
      </div>

      <main className={styles.map}>
        <Suspense fallback={<p className={styles.mapLoading}>Loading map…</p>}>
          <MapView
            filter={apiFilter}
            selectedId={selected}
            heatmap={heatmap}
            flyTo={flyTo}
            area={area}
            authority={authority.data}
            drawMode={drawMode}
            onSelect={select}
            onAreaDrawn={onAreaDrawn}
            sites={sites}
            selectedSite={siteRank}
            hoverSite={hoverSite}
            onSiteClick={(rank) => openSite(rank)}
            onSiteHover={setHoverSite}
            collisions={!trafficOpen}
            traffic={trafficLayer}
            selectedCountPoint={countPoint}
            onCountPointClick={openCountPoint}
            junctions={junctionLayer}
            selectedJunction={junctionId}
            onJunctionClick={openJunction}
            risk={riskLayer && !trafficOpen}
            route={routeGeo}
            routeHover={routeHover}
          />
        </Suspense>
        <DrawTools mode={drawMode} hasArea={area !== null} onMode={setDrawMode} onClear={() => setArea(null)} />
        <Legend
          heatmap={heatmap}
          onToggleHeatmap={() => setHeatmap(!heatmap)}
          traffic={trafficLayer}
          onToggleTraffic={() => setTrafficLayer(!trafficLayer)}
          junctions={junctionLayer}
          onToggleJunctions={() => setJunctionLayer(!junctionLayer)}
          risk={riskLayer}
          onToggleRisk={() => setRiskLayer(!riskLayer)}
          collisions={!trafficOpen}
        />
      </main>

      {panel === 'record' && selected && (
        <div className={styles.panel}>
          <CollisionPanel
            collisionIndex={selected}
            backLabel={
              hotspotsOpen
                ? siteRank
                  ? `Back to site ${siteRank}`
                  : 'Back to sites'
                : junctionId
                  ? 'Back to junction'
                  : view === 'area'
                    ? 'Back to area'
                    : undefined
            }
            onClose={() => setSelected(null)}
          />
        </div>
      )}
      {panel === 'junction' && junctionId && (
        <div className={styles.panel}>
          {trafficOpen ? (
            <JunctionPanel
              id={junctionId}
              filter={apiFilter}
              onCountPoint={(id) => {
                setTrafficLayer(true)
                openCountPoint(id)
              }}
              onZoom={zoomTo}
              onClose={() => setJnRaw(null)}
              trafficOnly
            />
          ) : (
            <JunctionSite id={junctionId} onClose={() => setJnRaw(null)} {...sitePageProps} />
          )}
        </div>
      )}
      {panel === 'road' && countPoint !== null && (
        <div className={styles.panel}>
          <RoadSite id={countPoint} onClose={() => setCpRaw(null)} {...sitePageProps} />
        </div>
      )}
      {panel === 'excess' && (
        <div className={styles.panel}>
          <ExcessSitesPanel
            area={apiFilter.area}
            areaLabel={areaPhrase(area, authority.data?.name)}
            clusters={clusterSites}
            methodSwitch={methodSwitch}
            onCountPoint={openCountPoint}
            onJunction={openJunction}
            onClose={closeView}
          />
        </div>
      )}
      {panel === 'clusters' && (
        <div className={styles.panel}>
          <HotspotPanel
            filter={apiFilter}
            hasArea={area !== null}
            params={hsParams}
            result={hotspots}
            baseLabel={areaPhrase(area, authority.data?.name)}
            period={{ from: filter.yearFrom, to: filter.yearTo, latest: meta.coverage.last_year }}
            site={siteRank}
            staleSiteLink={
              siteParam?.load != null && hotspots.data !== undefined && hotspots.data.data_load !== siteParam.load
            }
            hover={hoverSite}
            wide={siteRank !== null ? siteWide : wide}
            onParams={setHsParams}
            onLatestFiveYears={() =>
              setFilter({
                ...filter,
                yearFrom: meta.coverage.last_year - DEFAULT_SPAN_YEARS + 1,
                yearTo: meta.coverage.last_year,
              })
            }
            onSite={openSite}
            onHover={setHoverSite}
            onZoomSite={(rank) => openSite(rank)}
            onToggleWide={() => (siteRank !== null ? setSiteWide(!siteWide) : setWide(!wide))}
            onOpenCollision={openFromList}
            onJunction={openJunction}
            onCountPoint={openCountPoint}
            onOpenScheme={openScheme}
            methodSwitch={methodSwitch}
            onClose={closeView}
          />
        </div>
      )}
      {panel === 'routes' && (
        <div className={styles.panel}>
          <RoutesPanel
            area={apiFilter.area}
            areaLabel={areaPhrase(area, authority.data?.name)}
            road={road}
            corridor={corridor}
            onRoad={openRoad}
            onCountPoint={openCountPoint}
            onJunction={openJunction}
            onHoverLink={setRouteHover}
            onOpenScheme={openScheme}
            onClose={closeView}
          />
        </div>
      )}
      {panel === 'traffic' && (
        <div className={styles.panel}>
          <TrafficPanel
            filter={apiFilter}
            areaLabel={areaPhrase(area, authority.data?.name)}
            countPoint={countPoint}
            layerOn={trafficLayer}
            onToggleLayer={() => setTrafficLayer(!trafficLayer)}
            onCountPoint={openCountPoint}
            onZoom={zoomTo}
            onClose={closeView}
          />
        </div>
      )}
      {panel === 'area' && (
        <div className={styles.panel}>
          <SummaryPanel
            meta={meta}
            filter={apiFilter}
            wide={wide}
            onToggleWide={() => setWide(!wide)}
            onOpenCollision={openFromList}
            onPickAuthority={(code) => setArea({ type: 'authority', boundaryType: 'highway_authority', code })}
            schemeDraft={areaDraft(area, authority.data)}
            onOpenScheme={openScheme}
            onClose={closeView}
          />
        </div>
      )}
      {panel === 'schemes' && (
        <div className={styles.panel}>
          <SchemesPanel
            selected={schemeId}
            onSelect={openScheme}
            wide={schemeId !== null ? siteWide : wide}
            onToggleWide={() => (schemeId !== null ? setSiteWide(!siteWide) : setWide(!wide))}
            onJunction={openJunction}
            onCountPoint={openCountPoint}
            onZoomBbox={zoomToBbox}
            onClose={closeView}
          />
        </div>
      )}
    </div>
  )
}
