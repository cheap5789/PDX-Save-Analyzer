import { useState, useMemo, useCallback } from 'react'
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
 * EventsTab — receives merged historical + live events from App.jsx.
 * Handles filtering by type and inline AAR note editing.
 */
export default function EventsTab({ events: allEvents, status, onEventNoteUpdated }) {
  const [filter, setFilter] = useState('all')

  const filtered = useMemo(() => {
    const list = filter === 'all' ? allEvents : allEvents.filter((e) => e.event_type === filter)
    return [...list].reverse()
  }, [allEvents, filter])

  // Callback when a note is saved — propagate up to App
  const handleNoteUpdated = useCallback((eventId, noteText) => {
    if (onEventNoteUpdated) onEventNoteUpdated(eventId, noteText)
  }, [onEventNoteUpdated])

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
