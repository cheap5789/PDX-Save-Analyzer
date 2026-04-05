export default function StatusCard({ status }) {
  if (!status) {
    return (
      <div className="rounded-lg p-4" style={{ background: 'var(--color-surface)' }}>
        <p style={{ color: 'var(--color-text-muted)' }}>Loading status...</p>
      </div>
    )
  }

  const running = status.running
  const items = [
    { label: 'Game', value: status.game || '—' },
    {
      label: 'Country',
      value: status.country_tag
        ? (status.country_name && status.country_name !== status.country_tag
            ? `${status.country_name} (${status.country_tag})`
            : status.country_tag)
        : '—',
    },
    { label: 'Game Date', value: status.game_date || '—' },
    { label: 'Frequency', value: status.snapshot_freq || '—' },
    { label: 'Snapshots', value: status.snapshot_count ?? '—' },
    { label: 'Events', value: status.event_count ?? '—' },
  ]

  return (
    <div className="rounded-lg p-4" style={{ background: 'var(--color-surface)' }}>
      <div className="flex items-center gap-2 mb-3">
        <span
          className="inline-block w-3 h-3 rounded-full"
          style={{ background: running ? 'var(--color-success)' : 'var(--color-text-muted)' }}
        />
        <span className="font-medium text-sm">
          {running ? 'Pipeline Running' : 'Pipeline Idle'}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-3">
        {items.map((item) => (
          <div key={item.label}>
            <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>{item.label}</div>
            <div className="text-sm font-medium">{item.value}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
