import { useState, useEffect, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { useApi } from '../../hooks/useApi'
import { usePerfTracker } from '../../hooks/usePerfTracker'
import { useGameLocalization } from '../../contexts/GameLocalizationContext.jsx'

const LINE_COLORS = [
  '#3b82f6', '#ef4444', '#22c55e', '#f59e0b',
  '#8b5cf6', '#ec4899', '#06b6d4', '#f97316',
]

export default function ReligionsTab({ status }) {
  const api = useApi()
  const { track } = usePerfTracker('religions')
  const gameLoc = useGameLocalization()
  const [religions, setReligions] = useState([])
  const [snapshots, setSnapshots] = useState([])
  const [selectedField, setSelectedField] = useState('reform_desire')
  const [selectedReligions, setSelectedReligions] = useState([])
  const [loading, setLoading] = useState(false)

  const ptId = status?.playthrough_id

  // Load religion statics + snapshots
  useEffect(() => {
    if (!ptId) return
    let cancelled = false
    Promise.all([
      track('religions', api.getReligions(ptId).catch(() => [])),
      track('rel_snapshots', api.getReligionSnapshots(ptId).catch(() => [])),
    ]).then(([rels, snaps]) => {
      if (cancelled) return
      setReligions(rels)
      setSnapshots(snaps)

      // Auto-select religions that have snapshot data
      const withData = new Set(snaps.map((s) => s.religion_id))
      const autoSelect = rels
        .filter((r) => withData.has(r.id))
        .map((r) => r.id)
      setSelectedReligions(autoSelect)
      setLoading(false)
    })
    return () => { cancelled = true }
  }, [ptId])

  // Name helper: use shared context if loaded, fall back to local statics list
  const fmtReligion = (id) => {
    if (gameLoc?.fmtReligion) return gameLoc.fmtReligion(id)
    const r = religions.find((x) => x.id === id)
    return r?.name || r?.definition || `#${id}`
  }

  // Religions that appear in snapshot data (have dynamic fields)
  const religionsWithData = useMemo(() => {
    const ids = new Set(snapshots.map((s) => s.religion_id))
    return religions.filter((r) => ids.has(r.id))
  }, [religions, snapshots])

  // Transform into chart data: [{ date, "Catholic": 0.03, "Orthodox": 0.01 }, ...]
  const chartData = useMemo(() => {
    if (selectedReligions.length === 0) return []

    // Group snapshots by game_date
    const byDate = {}
    snapshots.forEach((s) => {
      if (!selectedReligions.includes(s.religion_id)) return
      if (!byDate[s.game_date]) byDate[s.game_date] = { date: s.game_date }
      const name = fmtReligion(s.religion_id)
      byDate[s.game_date][name] = s[selectedField]
    })

    return Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date))
  }, [snapshots, selectedReligions, selectedField, gameLoc])  // eslint-disable-line react-hooks/exhaustive-deps

  const selectedNames = selectedReligions.map((id) => fmtReligion(id))

  const SNAPSHOT_FIELDS = [
    { key: 'reform_desire', label: 'Reform Desire' },
    { key: 'tithe', label: 'Tithe' },
    { key: 'saint_power', label: 'Saint Power' },
    { key: 'timed_modifier_count', label: 'Timed Modifiers' },
  ]

  if (!ptId) {
    return (
      <div className="p-6 text-sm" style={{ color: 'var(--color-text-muted)' }}>
        No playthrough loaded. Start the pipeline or load a saved playthrough.
      </div>
    )
  }

  return (
    <div className="p-6 space-y-4">
      {/* Summary */}
      <div className="flex flex-wrap gap-4 items-center">
        <div className="rounded-lg px-4 py-2" style={{ background: 'var(--color-surface)' }}>
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Total religions</span>
          <p className="text-lg font-semibold">{religions.length}</p>
        </div>
        <div className="rounded-lg px-4 py-2" style={{ background: 'var(--color-surface)' }}>
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>With dynamic data</span>
          <p className="text-lg font-semibold">{religionsWithData.length}</p>
        </div>
        <div className="rounded-lg px-4 py-2" style={{ background: 'var(--color-surface)' }}>
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Snapshot points</span>
          <p className="text-lg font-semibold">{snapshots.length}</p>
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap gap-4 items-start">
        {/* Field selector */}
        <div>
          <label className="block text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>Metric</label>
          <div className="flex flex-wrap gap-1">
            {SNAPSHOT_FIELDS.map((f) => (
              <button
                key={f.key}
                onClick={() => setSelectedField(f.key)}
                className="px-2 py-1 text-xs rounded transition-colors"
                style={{
                  background: selectedField === f.key ? 'var(--color-accent)' : 'var(--color-surface)',
                  color: selectedField === f.key ? '#fff' : 'var(--color-text-muted)',
                }}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Religion selector */}
        <div>
          <label className="block text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>Religions</label>
          <div className="flex flex-wrap gap-1">
            {religionsWithData.map((r) => {
              const isSelected = selectedReligions.includes(r.id)
              return (
                <button
                  key={r.id}
                  onClick={() => {
                    setSelectedReligions((prev) =>
                      isSelected ? prev.filter((id) => id !== r.id) : [...prev, r.id]
                    )
                  }}
                  className="px-2 py-1 text-xs rounded transition-colors capitalize"
                  style={{
                    background: isSelected ? 'var(--color-accent)' : 'var(--color-surface)',
                    color: isSelected ? '#fff' : 'var(--color-text-muted)',
                  }}
                >
                  {r.name || r.definition}
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {/* Chart */}
      {chartData.length > 0 ? (
        <div className="rounded-lg p-4" style={{ background: 'var(--color-surface)' }}>
          <h3 className="text-sm font-medium mb-3">
            {SNAPSHOT_FIELDS.find((f) => f.key === selectedField)?.label} over time
          </h3>
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis dataKey="date" tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} stroke="var(--color-border)" />
              <YAxis tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} stroke="var(--color-border)" />
              <Tooltip
                contentStyle={{
                  background: 'var(--color-surface-alt)', border: '1px solid var(--color-border)',
                  borderRadius: '6px', color: 'var(--color-text)', fontSize: '12px',
                }}
              />
              <Legend wrapperStyle={{ fontSize: '12px', color: 'var(--color-text-muted)' }} />
              {selectedNames.map((name, i) => (
                <Line key={name} type="monotone" dataKey={name} stroke={LINE_COLORS[i % LINE_COLORS.length]}
                  strokeWidth={2} dot={false} connectNulls />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="rounded-lg p-8 text-center text-sm"
          style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}>
          {loading ? 'Loading religion data...' : 'No religion snapshot data available yet.'}
        </div>
      )}

      {/* Religion table */}
      <div className="rounded-lg overflow-hidden" style={{ background: 'var(--color-surface)' }}>
        <h3 className="text-sm font-medium px-4 pt-3 pb-2">All Religions ({religions.length})</h3>
        <div className="overflow-x-auto max-h-80 overflow-y-auto">
          <table className="w-full text-xs">
            <thead>
              <tr style={{ background: 'var(--color-surface-alt)', color: 'var(--color-text-muted)' }}>
                <th className="text-left px-3 py-2">ID</th>
                <th className="text-left px-3 py-2">Name</th>
                <th className="text-left px-3 py-2">Group</th>
                <th className="text-center px-3 py-2">Head</th>
                <th className="text-left px-3 py-2">Color</th>
              </tr>
            </thead>
            <tbody>
              {religions.slice(0, 50).map((r) => (
                <tr key={r.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td className="px-3 py-1.5">{r.id}</td>
                  <td className="px-3 py-1.5 capitalize">{r.name || r.definition}</td>
                  <td className="px-3 py-1.5 capitalize">{r.religion_group}</td>
                  <td className="px-3 py-1.5 text-center">{r.has_religious_head ? 'Yes' : ''}</td>
                  <td className="px-3 py-1.5">
                    {r.color_rgb && (
                      <span
                        className="inline-block w-4 h-4 rounded"
                        style={{ background: `rgb(${r.color_rgb.join(',')})` }}
                      />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {religions.length > 50 && (
            <p className="text-xs px-3 py-2" style={{ color: 'var(--color-text-muted)' }}>
              Showing first 50 of {religions.length} religions
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
