import StatusCard from '../StatusCard'
import EventCard from '../EventCard'
import { useCountryNames } from '../../contexts/CountryNamesContext'
import { fmtCountry } from '../../utils/formatters'

export default function OverviewTab({ status, snapshots, events }) {
  // Latest snapshot: last item in the array
  const latestSnapshot = snapshots.length > 0 ? snapshots[snapshots.length - 1] : null

  // Recent events: last 10, newest first
  const recentEvents = [...events].reverse().slice(0, 10)

  return (
    <div className="p-6 space-y-6">
      {/* Status card */}
      <StatusCard status={status} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Latest snapshot summary */}
        <div>
          <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--color-text-muted)' }}>
            Latest Snapshot
          </h3>
          {latestSnapshot ? (
            <SnapshotSummary snapshot={latestSnapshot} />
          ) : (
            <EmptyState text="No snapshots yet. Start the pipeline and play the game." />
          )}
        </div>

        {/* Recent events feed */}
        <div>
          <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--color-text-muted)' }}>
            Recent Events
          </h3>
          {recentEvents.length > 0 ? (
            <div className="space-y-2">
              {recentEvents.map((evt, i) => (
                <EventCard key={`${evt.game_date}-${evt.event_type}-${i}`} event={evt} />
              ))}
            </div>
          ) : (
            <EmptyState text="No events detected yet." />
          )}
        </div>
      </div>
    </div>
  )
}

function SnapshotSummary({ snapshot }) {
  const countries = snapshot.countries || {}
  const tags = Object.keys(countries)
  const nameMap = useCountryNames()

  return (
    <div className="rounded-lg p-4 space-y-3" style={{ background: 'var(--color-surface)' }}>
      <div className="flex items-center gap-4">
        <div>
          <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Game Date</div>
          <div className="text-sm font-medium">{snapshot.game_date || '—'}</div>
        </div>
        <div>
          <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Age</div>
          <div className="text-sm font-medium">{snapshot.current_age || '—'}</div>
        </div>
        <div>
          <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Countries</div>
          <div className="text-sm font-medium">{tags.length}</div>
        </div>
      </div>

      {/* Show first few country values as a quick summary */}
      {tags.slice(0, 3).map((tag) => {
        const data = countries[tag]
        const preview = Object.entries(data || {})
          .filter(([k]) => !k.startsWith('_'))
          .slice(0, 4)
          .map(([k, v]) => `${k}: ${typeof v === 'number' ? v.toFixed(1) : v}`)
          .join(' \u00B7 ')
        return (
          <div key={tag} className="text-xs">
            <span className="font-medium" style={{ color: 'var(--color-accent)' }}>
              {fmtCountry(tag, nameMap)}
            </span>
            <span style={{ color: 'var(--color-text-muted)' }}> {preview}</span>
          </div>
        )
      })}
      {tags.length > 3 && (
        <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          +{tags.length - 3} more countries
        </div>
      )}
    </div>
  )
}

function EmptyState({ text }) {
  return (
    <div
      className="rounded-lg p-6 text-center text-sm"
      style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}
    >
      {text}
    </div>
  )
}
