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

export default function EventCard({ event }) {
  const { icon, color } = EVENT_ICONS[event.event_type] || DEFAULT_ICON
  const label = (event.event_type || 'unknown').replace(/_/g, ' ')

  return (
    <div
      className="flex items-start gap-3 rounded-lg p-3 transition-colors"
      style={{ background: 'var(--color-surface)', borderLeft: `3px solid ${color}` }}
    >
      <span className="text-lg mt-0.5">{icon}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium capitalize">{label}</span>
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            {event.game_date || ''}
          </span>
        </div>
        <div className="text-xs mt-0.5 truncate" style={{ color: 'var(--color-text-muted)' }}>
          {formatPayload(event.payload)}
        </div>
      </div>
    </div>
  )
}
