import { useState } from 'react'
import { useApi } from '../hooks/useApi'

const EVENT_ICONS = {
  age_transition:      { icon: '\u2728', color: 'var(--color-warning)' },   // sparkles
  ruler_changed:       { icon: '\uD83D\uDC51', color: 'var(--color-accent)' },   // crown
  war_started:         { icon: '\u2694\uFE0F', color: 'var(--color-danger)' },    // swords
  war_ended:           { icon: '\uD83D\uDD4A\uFE0F', color: 'var(--color-success)' },  // dove
  country_appeared:    { icon: '\uD83C\uDF1F', color: 'var(--color-warning)' },   // star
  country_annexed:     { icon: '\uD83D\uDCA0', color: 'var(--color-danger)' },    // diamond
  culture_changed:     { icon: '\uD83C\uDFAD', color: 'var(--color-accent)' },    // masks
  religion_changed:    { icon: '\u2626\uFE0F', color: 'var(--color-accent)' },    // cross
  great_power_shift:   { icon: '\uD83D\uDCC8', color: 'var(--color-warning)' },   // chart up
  situation_started:   { icon: '\u26A0\uFE0F', color: 'var(--color-warning)' },   // warning
  situation_ended:     { icon: '\u2705', color: 'var(--color-success)' },          // check
}

const DEFAULT_ICON = { icon: '\uD83D\uDD35', color: 'var(--color-text-muted)' }

function formatPayload(payload) {
  if (!payload || typeof payload !== 'object') return ''
  return Object.entries(payload)
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`)
    .join(' \u00B7 ')
}

export default function EventCard({ event, onNoteUpdated }) {
  const api = useApi()
  const { icon, color } = EVENT_ICONS[event.event_type] || DEFAULT_ICON
  const label = (event.event_type || 'unknown').replace(/_/g, ' ')

  const [editing, setEditing] = useState(false)
  const [noteText, setNoteText] = useState(event.aar_note || '')
  const [saving, setSaving] = useState(false)

  const hasId = event.id != null  // only DB-persisted events can have notes

  const handleSave = async () => {
    if (!hasId) return
    setSaving(true)
    try {
      const updated = await api.updateAarNote(event.id, noteText)
      if (onNoteUpdated) onNoteUpdated(event.id, noteText)
      setEditing(false)
    } catch {
      // silently fail for now
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = () => {
    setNoteText(event.aar_note || '')
    setEditing(false)
  }

  return (
    <div
      className="rounded-lg p-3 transition-colors"
      style={{ background: 'var(--color-surface)', borderLeft: `3px solid ${color}` }}
    >
      {/* Event header */}
      <div className="flex items-start gap-3">
        <span className="text-lg mt-0.5">{icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium capitalize">{label}</span>
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              {event.game_date || ''}
            </span>
            {hasId && !editing && (
              <button
                onClick={() => setEditing(true)}
                className="ml-auto text-xs px-2 py-0.5 rounded transition-colors"
                style={{
                  background: 'var(--color-surface-alt)',
                  color: 'var(--color-text-muted)',
                  border: '1px solid var(--color-border)',
                }}
              >
                {event.aar_note ? 'Edit note' : 'Add note'}
              </button>
            )}
          </div>
          <div className="text-xs mt-0.5 truncate" style={{ color: 'var(--color-text-muted)' }}>
            {formatPayload(event.payload)}
          </div>
        </div>
      </div>

      {/* Existing note display (when not editing) */}
      {event.aar_note && !editing && (
        <div
          className="mt-2 ml-8 text-xs rounded p-2"
          style={{ background: 'var(--color-surface-alt)', color: 'var(--color-text)' }}
        >
          {event.aar_note}
        </div>
      )}

      {/* Inline note editor */}
      {editing && (
        <div className="mt-2 ml-8 space-y-2">
          <textarea
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            placeholder="Write your AAR note for this event..."
            rows={3}
            className="w-full text-xs rounded p-2 resize-y"
            style={{
              background: 'var(--color-surface-alt)',
              color: 'var(--color-text)',
              border: '1px solid var(--color-border)',
              outline: 'none',
            }}
            autoFocus
          />
          <div className="flex gap-2">
            <button
              onClick={handleSave}
              disabled={saving}
              className="text-xs px-3 py-1 rounded text-white transition-colors"
              style={{
                background: saving ? 'var(--color-surface-alt)' : 'var(--color-accent)',
                cursor: saving ? 'not-allowed' : 'pointer',
              }}
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
            <button
              onClick={handleCancel}
              className="text-xs px-3 py-1 rounded transition-colors"
              style={{
                background: 'var(--color-surface-alt)',
                color: 'var(--color-text-muted)',
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
