import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useApi } from './hooks/useApi'
import { useWebSocket } from './hooks/useWebSocket'
import { CountryNamesContext } from './contexts/CountryNamesContext'
import TabBar from './components/TabBar'
import OverviewTab from './components/tabs/OverviewTab'
import ChartsTab from './components/tabs/ChartsTab'
import EventsTab from './components/tabs/EventsTab'
import ConfigTab from './components/tabs/ConfigTab'
import ReligionsTab from './components/tabs/ReligionsTab'
import WarsTab from './components/tabs/WarsTab'
import TerritoryTab from './components/tabs/TerritoryTab'
import DemographicsTab from './components/tabs/DemographicsTab'

export default function App() {
  const api = useApi()
  const { connected, status: wsStatus, snapshots: liveSnapshots, events: liveEvents, clearHistory } = useWebSocket()
  const [activeTab, setActiveTab] = useState('overview')
  const [restStatus, setRestStatus] = useState(null)

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
      api.getEvents(ptId, {}).catch(() => []),
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

  // Callback when an AAR note is updated
  const handleEventNoteUpdated = useCallback((eventId, noteText) => {
    setHistoricalEvents((prev) =>
      prev.map((e) => (e.id === eventId ? { ...e, aar_note: noteText } : e))
    )
  }, [])

  // Build tag → display name lookup from all snapshots (_name embedded by backend)
  const tagNameMap = useMemo(() => {
    const map = {}
    for (const snap of allSnapshots) {
      for (const [tag, data] of Object.entries(snap.countries || {})) {
        if (!map[tag] && data._name) map[tag] = data._name
      }
    }
    return map
  }, [allSnapshots])

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
    <CountryNamesContext.Provider value={tagNameMap}>
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--color-bg)' }}>
      {/* Header */}
      <header className="px-6 pt-4 pb-0">
        <h1 className="text-xl font-bold tracking-tight">PDX Save Analyzer</h1>
      </header>

      {/* Tab bar with connection indicator */}
      <TabBar active={activeTab} onChange={setActiveTab} connected={connected} />

      {/* Tab content */}
      <main className="flex-1 overflow-y-auto">
        {activeTab === 'overview' && (
          <OverviewTab status={status} snapshots={allSnapshots} events={allEvents} />
        )}
        {activeTab === 'charts' && (
          <ChartsTab snapshots={allSnapshots} status={status} />
        )}
        {activeTab === 'events' && (
          <EventsTab events={allEvents} status={status} onEventNoteUpdated={handleEventNoteUpdated} />
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
          <DemographicsTab status={status} />
        )}
        {activeTab === 'config' && (
          <ConfigTab status={status} onStatusChange={handleStatusChange} />
        )}
      </main>
    </div>
    </CountryNamesContext.Provider>
  )
}
