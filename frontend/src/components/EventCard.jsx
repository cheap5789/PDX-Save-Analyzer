import { useState } from 'react'
import { useApi } from '../hooks/useApi'

const EVENT_ICONS = {
  age_transition:           { icon: '✨', color: 'var(--color-warning)' },
  ruler_changed:            { icon: '👑', color: 'var(--color-accent)' },
  war_started:              { icon: '⚔️',  color: 'var(--color-danger)' },
  war_ended:                { icon: '🕊️', color: 'var(--color-success)' },
  country_appeared:         { icon: '🌟', color: 'var(--color-warning)' },
  country_annexed:          { icon: '💀', color: 'var(--color-danger)' },
  culture_changed:          { icon: '🎭', color: 'var(--color-accent)' },
  religion_changed:         { icon: '☩️', color: 'var(--color-accent)' },
  great_power_rank_changed: { icon: '📈', color: 'var(--color-warning)' },
  capital_moved:            { icon: '🏛️', color: 'var(--color-accent)' },
  situation_started:        { icon: '⚠️', color: 'var(--color-warning)' },
  situation_ended:          { icon: '✅', color: 'var(--color-success)' },
  situation_changed:        { icon: '🔄', color: 'var(--color-text-muted)' },
}

const DEFAULT_ICON = { icon: '🔵', color: 'var(--color-text-muted)' }

/**
 * Human-readable event label shown as the card title.
 * Converts snake_case type to "Title Case" words.
 */
function eventLabel(type) {
  return (type || 'unknown')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

/**
 * Per-event-type description line shown below the title.
 * Uses localised display names stored in the payload where available,
 * falling back to raw keys with underscores replaced.
 */
function describeEvent(type, payload) {
  if (!payload || typeof payload !== 'object') return ''
  const p = payload

  /** Helper: fall back from display name to raw key (underscores → spaces). */
  const dn = (display, raw) =>
    (display && display !== raw) ? display : (raw || '').replace(/_/g, ' ')

  /** Helper: format an array of tags as a comma-separated string. */
  const tags = (arr) => Array.isArray(arr) ? arr.join(', ') : String(arr || '')

  switch (type) {
    case 'age_transition': {
      const from = dn(p.from_age_display, p.from_age)
      const to   = dn(p.to_age_display,   p.to_age)
      return `${from} → ${to}`
    }

    case 'ruler_changed': {
      const country = dn(p.country, p.tag)
      return `${country}: ${p.from_ruler || '?'} → ${p.to_ruler || '?'}`
    }

    case 'war_started': {
      const name = p.name || (p.name_key || '').replace(/_/g, ' ') || 'Unknown war'
      const atk  = tags(p.attackers)
      const def  = tags(p.defenders)
      return atk && def ? `${name} — ${atk} vs ${def}` : name
    }

    case 'war_ended': {
      const name = p.name || (p.name_key || '').replace(/_/g, ' ') || 'Unknown war'
      return `${name} concluded`
    }

    case 'country_appeared': {
      const country = dn(p.country, p.tag)
      const suffix  = country !== p.tag ? ` (${p.tag})` : ''
      return `${country}${suffix} emerged`
    }

    case 'country_annexed': {
      const country = dn(p.country, p.tag)
      const suffix  = country !== p.tag ? ` (${p.tag})` : ''
      return `${country}${suffix} was annexed`
    }

    case 'culture_changed': {
      const country = dn(p.country, p.tag)
      const from    = dn(p.from_culture, p.from_culture_key)
      const to      = dn(p.to_culture,   p.to_culture_key)
      return `${country}: ${from} → ${to}`
    }

    case 'religion_changed': {
      const country = dn(p.country, p.tag)
      const from    = dn(p.from_religion, p.from_religion_key)
      const to      = dn(p.to_religion,   p.to_religion_key)
      return `${country}: ${from} → ${to}`
    }

    case 'great_power_rank_changed': {
      const country  = dn(p.country, p.tag)
      const entering = p.to_rank <= 8
      const action   = entering ? 'enters great powers' : 'exits great powers'
      const rankInfo = p.from_rank && p.to_rank ? ` (rank ${p.from_rank} → ${p.to_rank})` : ''
      return `${country} ${action}${rankInfo}`
    }

    case 'capital_moved': {
      const country = dn(p.country, p.tag)
      return `${country}: capital relocated`
    }

    case 'situation_started': {
      const name = dn(p.situation_display, p.situation)
      return `${name} began`
    }

    case 'situation_ended': {
      const name = dn(p.situation_display, p.situation)
      return `${name} concluded`
    }

    case 'situation_changed': {
      const name = dn(p.situation_display, p.situation)
      return `${name}: ${(p.from_status || '').replace(/_/g, ' ')} → ${(p.to_status || '').replace(/_/g, ' ')}`
    }

    default: {
      // Generic fallback: show non-internal fields only
      const SKIP = new Set(['name_key', 'war_id', 'participants', 'from_culture_key',
        'to_culture_key', 'from_religion_key', 'to_religion_key', 'situation'])
      return Object.entries(p)
        .filter(([k, v]) => !SKIP.has(k) && v !== null && v !== undefined && v !== '')
        .map(([k, v]) => {
          const label = k.replace(/_/g, ' ')
          const val   = Array.isArray(v) ? v.join(', ') : String(v)
          return `${label}: ${val}`
        })
        .join(' · ')
    }
  }
}

export default function EventCard({ event, onNoteUpdated }) {
  const api = useApi()
  const { icon, color } = EVENT_ICONS[event.event_type] || DEFAULT_ICON
  const label = eventLabel(event.event_type)
  const description = describeEvent(event.event_type, event.payload)

  const [editing, setEditing] = useState(false)
  const [noteText, setNoteText] = useState(event.aar_note || '')
  const [saving, setSaving] = useState(false)

  const hasId = event.id != null  // only DB-persisted events can have notes

  const handleSave = async () => {
    if (!hasId) return
    setSaving(true)
    try {
      await api.updateAarNote(event.id, noteText)
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
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium">{label}</span>
            <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              {event.game_date || ''}
            </span>
            {event.country_tag && (
              <span
                className="text-xs px-1.5 py-0.5 rounded font-mono"
                style={{ background: 'var(--color-surface-alt)', color: 'var(--color-text-muted)' }}
              >
                {event.country_tag}
              </span>
            )}
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
          {description && (
            <div className="text-xs mt-0.5 truncate" style={{ color: 'var(--color-text-muted)' }}>
              {description}
            </div>
          )}
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
