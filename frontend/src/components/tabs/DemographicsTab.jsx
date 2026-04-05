import { useState, useEffect, useMemo } from 'react'
import {
  AreaChart, Area, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, PieChart, Pie, Cell,
} from 'recharts'
import { useApi } from '../../hooks/useApi'

const TYPE_COLORS = {
  peasants: '#22c55e',
  laborers: '#3b82f6',
  clergy: '#8b5cf6',
  nobles: '#f59e0b',
  tribesmen: '#f97316',
  slaves: '#ef4444',
  soldiers: '#06b6d4',
  burghers: '#ec4899',
}

const PIE_COLORS = [
  '#3b82f6', '#ef4444', '#22c55e', '#f59e0b',
  '#8b5cf6', '#ec4899', '#06b6d4', '#f97316',
  '#14b8a6', '#a855f7', '#84cc16', '#e11d48',
]

const GROUP_BY_OPTIONS = [
  { key: 'type', label: 'Pop Type' },
  { key: 'culture_id', label: 'Culture' },
  { key: 'religion_id', label: 'Religion' },
  { key: 'status', label: 'Status' },
  { key: 'estate', label: 'Estate' },
]

export default function DemographicsTab({ status }) {
  const api = useApi()
  const [groupBy, setGroupBy] = useState('type')
  const [aggregates, setAggregates] = useState([])
  const [loading, setLoading] = useState(false)
  const [viewMode, setViewMode] = useState('trends') // 'trends' | 'breakdown'

  const ptId = status?.playthrough_id

  // Load aggregated pop data
  useEffect(() => {
    if (!ptId) return
    let cancelled = false
    api.getPopAggregates(ptId, { group_by: groupBy })
      .then((data) => { if (!cancelled) setAggregates(data) })
      .catch(() => { if (!cancelled) setAggregates([]) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [ptId, groupBy])

  // Get all unique group values and dates
  const { groups, dates } = useMemo(() => {
    const groupSet = new Set()
    const dateSet = new Set()
    aggregates.forEach((a) => {
      const groupVal = a[groupBy] ?? 'Unknown'
      groupSet.add(String(groupVal))
      dateSet.add(a.game_date)
    })
    return {
      groups: Array.from(groupSet).sort(),
      dates: Array.from(dateSet).sort(),
    }
  }, [aggregates, groupBy])

  // Stacked area chart data: [{ date, peasants: 1234, clergy: 456, ... }, ...]
  const trendData = useMemo(() => {
    if (dates.length === 0) return []

    const byDate = {}
    dates.forEach((d) => { byDate[d] = { date: d } })

    aggregates.forEach((a) => {
      const groupVal = String(a[groupBy] ?? 'Unknown')
      const d = a.game_date
      if (byDate[d]) {
        byDate[d][groupVal] = (a.total_size || 0) * 1000
      }
    })

    return Object.values(byDate)
  }, [aggregates, dates, groupBy])

  // Latest snapshot breakdown for pie chart
  const latestBreakdown = useMemo(() => {
    if (dates.length === 0) return []
    const lastDate = dates[dates.length - 1]
    return aggregates
      .filter((a) => a.game_date === lastDate)
      .map((a) => ({
        name: String(a[groupBy] ?? 'Unknown'),
        value: (a.total_size || 0) * 1000,
        count: a.pop_count,
        avgSat: a.avg_satisfaction,
        avgLit: a.avg_literacy,
      }))
      .sort((a, b) => b.value - a.value)
  }, [aggregates, dates, groupBy])

  // Satisfaction trend: [{ date, peasants: 0.4, clergy: 0.45, ... }]
  const satData = useMemo(() => {
    if (dates.length === 0 || groupBy !== 'type') return []

    const byDate = {}
    dates.forEach((d) => { byDate[d] = { date: d } })

    aggregates.forEach((a) => {
      const groupVal = String(a[groupBy] ?? 'Unknown')
      if (byDate[a.game_date] && a.avg_satisfaction != null) {
        byDate[a.game_date][groupVal] = Math.round(a.avg_satisfaction * 1000) / 1000
      }
    })

    return Object.values(byDate)
  }, [aggregates, dates, groupBy])

  // Literacy trend
  const litData = useMemo(() => {
    if (dates.length === 0 || groupBy !== 'type') return []

    const byDate = {}
    dates.forEach((d) => { byDate[d] = { date: d } })

    aggregates.forEach((a) => {
      const groupVal = String(a[groupBy] ?? 'Unknown')
      if (byDate[a.game_date] && a.avg_literacy != null) {
        byDate[a.game_date][groupVal] = Math.round(a.avg_literacy * 100) / 100
      }
    })

    return Object.values(byDate)
  }, [aggregates, dates, groupBy])

  const getColor = (group, index) => {
    if (groupBy === 'type') return TYPE_COLORS[group] || PIE_COLORS[index % PIE_COLORS.length]
    return PIE_COLORS[index % PIE_COLORS.length]
  }

  if (!ptId) {
    return (
      <div className="p-6 text-sm" style={{ color: 'var(--color-text-muted)' }}>
        No playthrough loaded. Start the pipeline or load a saved playthrough.
      </div>
    )
  }

  return (
    <div className="p-6 space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap gap-4 items-start">
        <div>
          <label className="block text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>Group by</label>
          <div className="flex flex-wrap gap-1">
            {GROUP_BY_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                onClick={() => setGroupBy(opt.key)}
                className="px-2 py-1 text-xs rounded transition-colors"
                style={{
                  background: groupBy === opt.key ? 'var(--color-accent)' : 'var(--color-surface)',
                  color: groupBy === opt.key ? '#fff' : 'var(--color-text-muted)',
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="block text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>View</label>
          <div className="flex gap-1">
            <button onClick={() => setViewMode('trends')}
              className="px-2 py-1 text-xs rounded transition-colors"
              style={{
                background: viewMode === 'trends' ? 'var(--color-accent)' : 'var(--color-surface)',
                color: viewMode === 'trends' ? '#fff' : 'var(--color-text-muted)',
              }}>
              Trends
            </button>
            <button onClick={() => setViewMode('breakdown')}
              className="px-2 py-1 text-xs rounded transition-colors"
              style={{
                background: viewMode === 'breakdown' ? 'var(--color-accent)' : 'var(--color-surface)',
                color: viewMode === 'breakdown' ? '#fff' : 'var(--color-text-muted)',
              }}>
              Breakdown
            </button>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="rounded-lg p-8 text-center text-sm"
          style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}>
          Loading demographics data...
        </div>
      ) : aggregates.length === 0 ? (
        <div className="rounded-lg p-8 text-center text-sm"
          style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}>
          No population data available yet.
        </div>
      ) : viewMode === 'trends' ? (
        <>
          {/* Population size stacked area */}
          <div className="rounded-lg p-4" style={{ background: 'var(--color-surface)' }}>
            <h3 className="text-sm font-medium mb-3">Population Size by {GROUP_BY_OPTIONS.find((o) => o.key === groupBy)?.label}</h3>
            <ResponsiveContainer width="100%" height={350}>
              <AreaChart data={trendData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="date" tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} stroke="var(--color-border)" />
                <YAxis
                  tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }}
                  stroke="var(--color-border)"
                  tickFormatter={(v) => {
                    if (v >= 1_000_000) return (v / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M'
                    if (v >= 1_000) return (v / 1_000).toFixed(1).replace(/\.0$/, '') + 'K'
                    return Math.round(v).toString()
                  }}
                />
                <Tooltip
                  contentStyle={{
                    background: 'var(--color-surface-alt)', border: '1px solid var(--color-border)',
                    borderRadius: '6px', color: 'var(--color-text)', fontSize: '12px',
                  }}
                  formatter={(v, name) => [v.toLocaleString(undefined, { maximumFractionDigits: 0 }), name]}
                />
                <Legend wrapperStyle={{ fontSize: '12px', color: 'var(--color-text-muted)' }} />
                {groups.map((g, i) => (
                  <Area key={g} type="monotone" dataKey={g} stackId="1"
                    fill={getColor(g, i)} stroke={getColor(g, i)} fillOpacity={0.6} />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Satisfaction trend (only for type grouping) */}
          {groupBy === 'type' && satData.length > 0 && (
            <div className="rounded-lg p-4" style={{ background: 'var(--color-surface)' }}>
              <h3 className="text-sm font-medium mb-3">Average Satisfaction by Type</h3>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={satData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="date" tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} stroke="var(--color-border)" />
                  <YAxis domain={[0, 1]} tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} stroke="var(--color-border)" />
                  <Tooltip
                    contentStyle={{
                      background: 'var(--color-surface-alt)', border: '1px solid var(--color-border)',
                      borderRadius: '6px', color: 'var(--color-text)', fontSize: '12px',
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: '12px', color: 'var(--color-text-muted)' }} />
                  {groups.map((g, i) => (
                    <Line key={g} type="monotone" dataKey={g} stroke={getColor(g, i)}
                      strokeWidth={2} dot={false} connectNulls />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Literacy trend (only for type grouping) */}
          {groupBy === 'type' && litData.length > 0 && (
            <div className="rounded-lg p-4" style={{ background: 'var(--color-surface)' }}>
              <h3 className="text-sm font-medium mb-3">Average Literacy by Type (%)</h3>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={litData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
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
                  {groups.map((g, i) => (
                    <Line key={g} type="monotone" dataKey={g} stroke={getColor(g, i)}
                      strokeWidth={2} dot={false} connectNulls />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      ) : (
        /* Breakdown view — pie chart + table */
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Pie chart */}
          <div className="rounded-lg p-4" style={{ background: 'var(--color-surface)' }}>
            <h3 className="text-sm font-medium mb-3">
              Current Composition ({dates[dates.length - 1]})
            </h3>
            <ResponsiveContainer width="100%" height={350}>
              <PieChart>
                <Pie
                  data={latestBreakdown}
                  dataKey="value"
                  nameKey="name"
                  cx="50%" cy="50%"
                  outerRadius={130}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(1)}%`}
                  labelLine={{ stroke: 'var(--color-text-muted)' }}
                >
                  {latestBreakdown.map((entry, i) => (
                    <Cell key={entry.name} fill={getColor(entry.name, i)} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: 'var(--color-surface-alt)', border: '1px solid var(--color-border)',
                    borderRadius: '6px', color: 'var(--color-text)', fontSize: '12px',
                  }}
                  formatter={(val) => val.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Breakdown table */}
          <div className="rounded-lg overflow-hidden" style={{ background: 'var(--color-surface)' }}>
            <h3 className="text-sm font-medium px-4 pt-3 pb-2">Breakdown Details</h3>
            <div className="overflow-x-auto max-h-80 overflow-y-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr style={{ background: 'var(--color-surface-alt)', color: 'var(--color-text-muted)' }}>
                    <th className="text-left px-3 py-2">{GROUP_BY_OPTIONS.find((o) => o.key === groupBy)?.label}</th>
                    <th className="text-right px-3 py-2">Count</th>
                    <th className="text-right px-3 py-2">Total Size</th>
                    <th className="text-right px-3 py-2">Avg Sat</th>
                    <th className="text-right px-3 py-2">Avg Lit</th>
                  </tr>
                </thead>
                <tbody>
                  {latestBreakdown.map((row, i) => (
                    <tr key={row.name} style={{ borderBottom: '1px solid var(--color-border)' }}>
                      <td className="px-3 py-1.5 capitalize flex items-center gap-2">
                        <span className="inline-block w-3 h-3 rounded-sm" style={{ background: getColor(row.name, i) }} />
                        {row.name}
                      </td>
                      <td className="px-3 py-1.5 text-right">{row.count.toLocaleString()}</td>
                      <td className="px-3 py-1.5 text-right">{row.value.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                      <td className="px-3 py-1.5 text-right">
                        {row.avgSat != null ? (row.avgSat * 100).toFixed(1) + '%' : '—'}
                      </td>
                      <td className="px-3 py-1.5 text-right">
                        {row.avgLit != null ? row.avgLit.toFixed(1) + '%' : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
