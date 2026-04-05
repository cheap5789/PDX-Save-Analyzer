const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'charts', label: 'Charts' },
  { id: 'events', label: 'Events' },
  { id: 'religions', label: 'Religions' },
  { id: 'wars', label: 'Wars' },
  { id: 'territory', label: 'Territory' },
  { id: 'demographics', label: 'Demographics' },
  { id: 'config', label: 'Config' },
]

export default function TabBar({ active, onChange, connected }) {
  return (
    <nav className="flex items-center gap-1 px-4 pt-3 pb-0"
         style={{ borderBottom: '1px solid var(--color-border)' }}>
      {TABS.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className="px-4 py-2 text-sm font-medium rounded-t-lg transition-colors"
          style={{
            background: active === tab.id ? 'var(--color-surface)' : 'transparent',
            color: active === tab.id ? 'var(--color-text)' : 'var(--color-text-muted)',
            borderBottom: active === tab.id ? '2px solid var(--color-accent)' : '2px solid transparent',
          }}
        >
          {tab.label}
        </button>
      ))}
      <div className="ml-auto flex items-center gap-2 pr-2 pb-2">
        <span
          className="inline-block w-2 h-2 rounded-full"
          style={{ background: connected ? 'var(--color-success)' : 'var(--color-danger)' }}
        />
        <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          {connected ? 'Connected' : 'Disconnected'}
        </span>
      </div>
    </nav>
  )
}
