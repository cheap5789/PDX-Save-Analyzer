import { useState, useEffect, useMemo, useCallback } from 'react'
import { useApi } from '../../hooks/useApi'
import EventCard from '../EventCard'

const EVENT_TYPES = [
  'all',
  'age_transition',
  'ruler_changed',
  'war_started',
  'war_ended',
  'country_appeared',
  'country_annexed',
  'culture_changed',
  'religion_changed',
  'great_power_shift',
  'situation_started',
  'situation_ended',
]

/**
 * EventsTab — merges historical events (from REST, with aar_note + id) and
 * live events (from WebSocket, no id yet). Historical events load once when
 * the playthrough_id becomes available.
 */
export default function EventsTab({ events: liveEvents, status }) {
  const api = useApi()
  const [filter, setFilter] = useState('all')
  const [historicalEvents, setHistoricalEvents] = useState([])
  const [loadedPlaythrough, setLoadedPlaythrough] = useState(null)

  // Load historical events from DB when playthrough is known
  useEffect(() => {
    const ptId = status?.playthrough_id
    if (!ptId || ptId === loadedPlaythrough) return

    api.getEvents(ptId, {})
      .then((data) => {
        // Parse payload if it's a string
        const parsed = data.map((e) => ({
          ...e,
          payload: typeof e.payload === 'string' ? JSON.parse(e.payload) : e.payload,
        }))
        setHistoricalEvents(parsed)
        setLoadedPlaythrough(ptId)
      })
      .catch(() => {})
  }, [status?.playthrough_id])

  // Merge: historical (with ids + notes) + live (new ones not yet in DB).
  // Live events that match a historical event by date+type are skipped (already loaded).
  const allEvents = useMemo(() => {
    const historicalKeys = new Set(
      historicalEvents.map((e) => `${e.game_date}|${e.event_type}`)
    )
    const newLive = liveEvents.filter(
      (e) => !historicalKeys.has(`${e.game_date}|${e.event_type}`)
    )
    return [...historicalEvents, ...newLive]
  }, [historicalEvents, liveEvents])

  const filtered = useMemo(() => {
    const list = filter === 'all' ? allEvents : allEvents.filter((e) => e.event_type === filter)
    return [...list].reverse()
  }, [allEvents, filter])

  // Callback when a note is saved — update the historical events list in place
  const handleNoteUpdated = useCallback((eventId, noteText) => {
    setHistoricalEvents((prev) =>
      prev.map((e) => (e.id === eventId ? { ...e, aar_note: noteText } : e))
    )
  }, [])

  return (
    <div className="p-6 space-y-4">
      {/* Filter bar */}
      <div>
        <label className="block text-xs mb-2" style={{ color: 'var(--color-text-muted)' }}>
          Filter by type
        </label>
        <div className="flex flex-wrap gap-1">
          {EVENT_TYPES.map((type) => {
            const count = type === 'all'
              ? allEvents.length
              : allEvents.filter((e) => e.event_type === type).length
            return (
              <button
                key={type}
                onClick={() => setFilter(type)}
                className="px-2 py-1 text-xs rounded capitalize transition-colors"
                style={{
                  background: filter === type ? 'var(--color-accent)' : 'var(--color-surface)',
                  color: filter === type ? '#fff' : 'var(--color-text-muted)',
                }}
              >
                {type.replace(/_/g, ' ')} ({count})
              </button>
            )
          })}
        </div>
      </div>

      {/* Event feed */}
      {filtered.length > 0 ? (
        <div className="space-y-2">
          {filtered.map((evt, i) => (
            <EventCard
              key={evt.id ?? `${evt.game_date}-${evt.event_type}-${i}`}
              event={evt}
              onNoteUpdated={handleNoteUpdated}
            />
          ))}
        </div>
      ) : (
        <div
          className="rounded-lg p-8 text-center text-sm"
          style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}
        >
          {allEvents.length === 0
            ? 'No events detected yet. Start the pipeline and play the game.'
            : `No events of type "${filter.replace(/_/g, ' ')}".`}
        </div>
      )}
    </div>
  )
}
