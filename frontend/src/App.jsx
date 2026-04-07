import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useApi } from './hooks/useApi'
import { useWebSocket } from './hooks/useWebSocket'
import { CountryNamesContext } from './contexts/CountryNamesContext'
import { GameLocalizationProvider } from './contexts/GameLocalizationContext.jsx'
import { PerfProvider } from './contexts/PerfContext'
import { AbortProvider, useAbortContext } from './contexts/AbortContext.jsx'
import PerfPanel from './components/PerfPanel'
import TabBar from './components/TabBar'
import OverviewTab from './components/tabs/OverviewTab'
import ChartsTab from './components/tabs/ChartsTab'
import EventsTab from './components/tabs/EventsTab'
import ConfigTab from './components/tabs/ConfigTab'
import ReligionsTab from './components/tabs/ReligionsTab'
import WarsTab from './components/tabs/WarsTab'
import TerritoryTab from './components/tabs/TerritoryTab'
import DemographicsTab from './components/tabs/DemographicsTab'

/** Header extracted so it can consume AbortContext (which lives inside App's JSX tree). */
function AppHeader({ perfOpen, setPerfOpen }) {
  const abort = useAbortContext()
  const hasActive = abort?.activeCount > 0

  return (
    <header className="px-6 pt-4 pb-0 flex items-center justify-between">
      <h1 className="text-xl font-bold tracking-tight">PDX Save Analyzer</h1>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {/* Abort button — top-right, always visible */}
        <button
          onClick={() => abort?.abortAll()}
          title={hasActive ? `Cancel ${abort.activeCount} active request(s)` : 'No active requests'}
          disabled={!hasActive}
          style={{
            background: hasActive ? '#ef4444' : 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 6,
            padding: '3px 9px',
            cursor: hasActive ? 'pointer' : 'not-allowed',
            fontSize: 13,
            color: hasActive ? '#fff' : 'var(--color-text-muted)',
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            opacity: hasActive ? 1 : 0.5,
            transition: 'background 0.15s, color 0.15s, opacity 0.15s',
          }}
        >
          {/* Spinning dot when active */}
          {hasActive && (
            <span style={{
              width: 7, height: 7, borderRadius: '50%', background: '#fff',
              display: 'inline-block', animation: 'pulse 1s infinite',
            }} />
          )}
          <span style={{ fontSize: 11, fontWeight: 500 }}>
            {hasActive ? `Abort (${abort.activeCount})` : 'Abort'}
          </span>
        </button>

        {/* Perf panel toggle */}
        <button
          onClick={() => setPerfOpen((v) => !v)}
          title="Toggle performance monitor"
          style={{
            background: perfOpen ? 'var(--color-accent)' : 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 6,
            padding: '3px 9px',
            cursor: 'pointer',
            fontSize: 13,
            color: perfOpen ? '#fff' : 'var(--color-text-muted)',
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            transition: 'background 0.15s, color 0.15s',
          }}
        >
          <span>⏱</span>
          <span style={{ fontSize: 11, fontWeight: 500 }}>Perf</span>
        </button>
      </div>
    </header>
  )
}

export default function App() {
  const api = useApi()
  const { connected, status: wsStatus, snapshots: liveSnapshots, events: liveEvents, backfillProgress, clearHistory } = useWebSocket()
  const [activeTab, setActiveTab] = useState('overview')
  const [restStatus, setRestStatus] = useState(null)

  // Perf panel — hidden by default, persists across tab navigation
  const [perfOpen, setPerfOpen] = useState(false)

  // Historical data loaded from REST (browse mode or pipeline reconnect)
  const [historicalSnapshots, setHistoricalSnapshots] = useState([])
  const [historicalEvents, setHistoricalEvents] = useState([])
  const loadedPlaythroughRef = useRef(null)

  // Track which status source was most recently updated so we pick the right one
  const [lastStatusSource, setLastStatusSource] = useState('rest') // 'rest' | 'ws'

  // On mount: fetch status via REST (auto-reconnect logic)
  useEffect(() => {
    api.getStatus()
      .then((s) => {
        setRestStatus(s)
        setLastStatusSource('rest')
        if (!s.running && !s.playthrough_id) {
          setActiveTab('config')
        } else if (s.playthrough_id) {
          // Server already has an active playthrough — load its data
          fetchPlaythroughData(s.playthrough_id)
        }
      })
      .catch(() => {
        setActiveTab('config')
      })
  }, [])

  // When WS sends a new status, mark it as most recent
  useEffect(() => {
    if (wsStatus) setLastStatusSource('ws')
  }, [wsStatus])

  // Use whichever status was updated most recently
  const status = lastStatusSource === 'ws' ? (wsStatus || restStatus) : (restStatus || wsStatus)

  // --- Data fetching for a playthrough ---
  const fetchPlaythroughData = useCallback((ptId) => {
    if (!ptId || ptId === loadedPlaythroughRef.current) return
    loadedPlaythroughRef.current = ptId

    Promise.all([
      api.getSnapshots(ptId, {}).catch(() => []),
      // Small fetch for OverviewTab's recent-events feed — EventsTab does its own full query
      api.getEvents(ptId, { limit: 20 }).catch(() => []),
    ]).then(([snaps, evts]) => {
      // Flatten REST snapshots to match WebSocket shape:
      // REST: { id, playthrough_id, game_date, recorded_at, data: { countries, ... } }
      // WS:   { game_date, countries, current_age, ... }
      const parsedSnaps = snaps.map((s) => {
        const data = typeof s.data === 'string' ? JSON.parse(s.data) : (s.data || {})
        return { game_date: s.game_date, ...data }
      })
      const parsedEvts = evts.map((e) => ({
        ...e,
        payload: typeof e.payload === 'string' ? JSON.parse(e.payload) : e.payload,
      }))
      setHistoricalSnapshots(parsedSnaps)
      setHistoricalEvents(parsedEvts)
    })
  }, [api])

  // Also react to WS status changes that bring a new playthrough_id
  // (e.g., pipeline auto-detects a new save and starts tracking)
  useEffect(() => {
    if (wsStatus?.playthrough_id) {
      fetchPlaythroughData(wsStatus.playthrough_id)
    }
  }, [wsStatus?.playthrough_id, fetchPlaythroughData])

  // Merge historical + live snapshots
  const allSnapshots = useMemo(() => {
    if (liveSnapshots.length === 0) return historicalSnapshots
    const historicalDates = new Set(historicalSnapshots.map((s) => s.game_date))
    const newLive = liveSnapshots.filter((s) => !historicalDates.has(s.game_date))
    return [...historicalSnapshots, ...newLive]
  }, [historicalSnapshots, liveSnapshots])

  // Merge historical + live events
  const allEvents = useMemo(() => {
    if (liveEvents.length === 0) return historicalEvents
    const historicalKeys = new Set(
      historicalEvents.map((e) => `${e.game_date}|${e.event_type}`)
    )
    const newLive = liveEvents.filter(
      (e) => !historicalKeys.has(`${e.game_date}|${e.event_type}`)
    )
    return [...historicalEvents, ...newLive]
  }, [historicalEvents, liveEvents])

  // Build tag → { name, color, prevTags } metadata from snapshots
  // (_name, _color, _prev_tags are embedded by the backend's snapshot.py)
  const tagMetaMap = useMemo(() => {
    const map = {}
    for (const snap of allSnapshots) {
      for (const [tag, data] of Object.entries(snap.countries || {})) {
        if (!map[tag]) map[tag] = {}
        if (!map[tag].name     && data._name)      map[tag].name     = data._name
        if (!map[tag].color    && data._color)     map[tag].color    = data._color
        if (!map[tag].prevTags && data._prev_tags) map[tag].prevTags = data._prev_tags
      }
    }
    return map
  }, [allSnapshots])

  // Selected countries — lifted here so the selection persists across tab changes.
  // Auto-seed with the player tag on first status arrival.
  const [selectedCountries, setSelectedCountries] = useState([])
  useEffect(() => {
    const tag = status?.country_tag
    if (tag && selectedCountries.length === 0) {
      setSelectedCountries([tag])
    }
  }, [status?.country_tag])

  // Callback for ConfigTab to update status after start/stop/load
  const handleStatusChange = useCallback((newStatus) => {
    setRestStatus(newStatus)
    setLastStatusSource('rest') // REST action just happened — trust REST status

    if (newStatus.running || newStatus.playthrough_id) {
      setActiveTab('overview')
      // Directly trigger data fetch for the playthrough
      if (newStatus.playthrough_id) {
        fetchPlaythroughData(newStatus.playthrough_id)
      }
    }

    // If pipeline stopped with no playthrough, clear everything
    if (!newStatus.running && !newStatus.playthrough_id) {
      setHistoricalSnapshots([])
      setHistoricalEvents([])
      loadedPlaythroughRef.current = null
      clearHistory()
    }
  }, [clearHistory, fetchPlaythroughData])

  return (
    <PerfProvider>
    <AbortProvider>
    <CountryNamesContext.Provider value={tagMetaMap}>
    <GameLocalizationProvider playthroughId={status?.playthrough_id}>
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--color-bg)' }}>

      {/* Header */}
      <AppHeader perfOpen={perfOpen} setPerfOpen={setPerfOpen} />

      {/* Tab bar with connection indicator */}
      <TabBar active={activeTab} onChange={setActiveTab} connected={connected} />

      {/* Main content + optional perf panel side-by-side */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>
        {/* Tab content */}
        <main style={{ flex: 1, overflowY: 'auto' }}>
          {activeTab === 'overview' && (
            <OverviewTab status={status} snapshots={allSnapshots} events={allEvents} />
          )}
          {activeTab === 'charts' && (
            <ChartsTab
              snapshots={allSnapshots}
              status={status}
              selectedCountries={selectedCountries}
              onSelectedCountriesChange={setSelectedCountries}
            />
          )}
          {activeTab === 'events' && (
            <EventsTab
              playthroughId={status?.playthrough_id}
              liveEvents={liveEvents}
              status={status}
            />
          )}
          {activeTab === 'religions' && (
            <ReligionsTab status={status} />
          )}
          {activeTab === 'wars' && (
            <WarsTab status={status} />
          )}
          {activeTab === 'territory' && (
            <TerritoryTab status={status} />
          )}
          {activeTab === 'demographics' && (
            <DemographicsTab
              status={status}
              allSnapshots={allSnapshots}
            />
          )}
          {activeTab === 'config' && (
            <ConfigTab status={status} onStatusChange={handleStatusChange} backfillProgress={backfillProgress} />
          )}
        </main>

        {/* Perf panel — persists across tab navigation */}
        {perfOpen && <PerfPanel onClose={() => setPerfOpen(false)} />}
      </div>

    </div>
    </GameLocalizationProvider>
    </CountryNamesContext.Provider>
    </AbortProvider>
    </PerfProvider>
  )
}
