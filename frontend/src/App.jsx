import { useState, useEffect, useCallback } from 'react'
import { useApi } from './hooks/useApi'
import { useWebSocket } from './hooks/useWebSocket'
import TabBar from './components/TabBar'
import OverviewTab from './components/tabs/OverviewTab'
import ChartsTab from './components/tabs/ChartsTab'
import EventsTab from './components/tabs/EventsTab'
import ConfigTab from './components/tabs/ConfigTab'

export default function App() {
  const api = useApi()
  const { connected, status: wsStatus, snapshots, events } = useWebSocket()
  const [activeTab, setActiveTab] = useState('overview')
  const [restStatus, setRestStatus] = useState(null)

  // On mount: fetch status via REST (auto-reconnect logic)
  useEffect(() => {
    api.getStatus()
      .then((s) => {
        setRestStatus(s)
        // If pipeline is not running, default to config tab
        if (!s.running) setActiveTab('config')
      })
      .catch(() => {
        // Server not reachable — show config
        setActiveTab('config')
      })
  }, [])

  // Merge: prefer WS status (real-time) over REST status (initial)
  const status = wsStatus || restStatus

  // Callback for ConfigTab to update status after start/stop
  const handleStatusChange = useCallback((newStatus) => {
    setRestStatus(newStatus)
    if (newStatus.running) setActiveTab('overview')
  }, [])

  return (
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
          <OverviewTab status={status} snapshots={snapshots} events={events} />
        )}
        {activeTab === 'charts' && (
          <ChartsTab snapshots={snapshots} status={status} />
        )}
        {activeTab === 'events' && (
          <EventsTab events={events} />
        )}
        {activeTab === 'config' && (
          <ConfigTab status={status} onStatusChange={handleStatusChange} />
        )}
      </main>
    </div>
  )
}
