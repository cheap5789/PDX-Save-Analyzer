import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import {
  AreaChart, Area, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, PieChart, Pie, Cell,
} from 'recharts'
import { useApi } from '../../hooks/useApi'
import { usePerfTracker } from '../../hooks/usePerfTracker'
import { useCountryNames } from '../../contexts/CountryNamesContext'
import { fmtCountry } from '../../utils/formatters'

const TYPE_COLORS = {
  peasants:  '#22c55e',
  laborers:  '#3b82f6',
  clergy:    '#8b5cf6',
  nobles:    '#f59e0b',
  tribesmen: '#f97316',
  slaves:    '#ef4444',
  soldiers:  '#06b6d4',
  burghers:  '#ec4899',
}

const PIE_COLORS = [
  '#3b82f6', '#ef4444', '#22c55e', '#f59e0b',
  '#8b5cf6', '#ec4899', '#06b6d4', '#f97316',
  '#14b8a6', '#a855f7', '#84cc16', '#e11d48',
]

const GROUP_BY_OPTIONS = [
  { key: 'type',        label: 'Pop Type'  },
  { key: 'culture_id',  label: 'Culture'   },
  { key: 'religion_id', label: 'Religion'  },
  { key: 'status',      label: 'Status'    },
  { key: 'estate',      label: 'Estate'    },
]

// ─── helpers ─────────────────────────────────────────────────────────────────

function getColor(groupBy, group, index) {
  if (groupBy === 'type') return TYPE_COLORS[group] || PIE_COLORS[index % PIE_COLORS.length]
  return PIE_COLORS[index % PIE_COLORS.length]
}

function fmtMs(ms) {
  return (ms / 1000).toFixed(1) + 's'
}

const tooltipStyle = {
  background:   'var(--color-surface-alt)',
  border:       '1px solid var(--color-border)',
  borderRadius: '6px',
  color:        'var(--color-text)',
  fontSize:     '12px',
}

const ctrlStyle = {
  background: 'var(--color-surface)',
  color:      'var(--color-text)',
  border:     '1px solid var(--color-border)',
  borderRadius: 4,
  padding:    '3px 8px',
  fontSize:   12,
  minWidth:   110,
}

// ─── main component ───────────────────────────────────────────────────────────

export default function DemographicsTab({ status, allSnapshots }) {
  const api       = useApi()
  const { track } = usePerfTracker('demographics')
  const nameMap   = useCountryNames()
  const ptId      = status?.playthrough_id

  // ── Available dates from snapshots ──
  const snapshotDates = useMemo(() => (
    [...new Set(allSnapshots.map((s) => s.game_date))].sort()
  ), [allSnapshots])

  // ── Date range state ──
  const [fromDate, setFromDate] = useState(null)
  const [toDate,   setToDate]   = useState(null)

  // Seed to latest snapshot when dates become available
  useEffect(() => {
    if (snapshotDates.length > 0 && fromDate === null) {
      const last = snapshotDates[snapshotDates.length - 1]
      setFromDate(last)
      setToDate(last)
    }
  }, [snapshotDates, fromDate])

  // ── Country picker ──
  const [countries, setCountries] = useState([])        // CountryResponse[]
  const [selectedCanon, setSelectedCanon] = useState(null)  // canonical_tag or null = all

  useEffect(() => {
    if (!ptId) return
    api.getCountries(ptId)
      .then((data) => {
        const list = data || []
        setCountries(list)
        // Auto-select player's country
        const playerTag = status?.country_tag
        if (playerTag) {
          const match = list.find((c) => c.tag === playerTag)
          if (match) setSelectedCanon(match.canonical_tag)
        }
      })
      .catch(() => setCountries([]))
  }, [ptId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Group countries by canonical_tag so each entry in the dropdown
  // represents a succession chain (e.g. CAS + SPA → "SPA (+1)")
  const countryGroups = useMemo(() => {
    const grouped = {}
    for (const c of countries) {
      const canon = c.canonical_tag
      if (!grouped[canon]) grouped[canon] = { canonical_tag: canon, tags: [] }
      grouped[canon].tags.push(c.tag)
    }
    return Object.values(grouped).sort((a, b) =>
      a.canonical_tag.localeCompare(b.canonical_tag)
    )
  }, [countries])

  // Expand the selected canonical tag to all predecessor + current tags for the query
  const ownerTagsForQuery = useMemo(() => {
    if (!selectedCanon) return null   // no filter = all countries
    const group = countryGroups.find((g) => g.canonical_tag === selectedCanon)
    return group ? group.tags : [selectedCanon]
  }, [selectedCanon, countryGroups])

  // ── Dimension picker ──
  const [groupBy, setGroupBy] = useState('type')

  // ── Data state ──
  const [aggregates, setAggregates] = useState([])
  const [loading,    setLoading]    = useState(false)
  const [loadError,  setLoadError]  = useState(null)  // null | 'cancelled' | string

  // ── Elapsed timer ──
  const [elapsed,       setElapsed]       = useState(0)
  const elapsedTimerRef                   = useRef(null)
  const startTimeRef                      = useRef(null)

  const startTimer = useCallback(() => {
    startTimeRef.current = Date.now()
    setElapsed(0)
    elapsedTimerRef.current = setInterval(
      () => setElapsed(Date.now() - startTimeRef.current),
      100,
    )
  }, [])

  const stopTimer = useCallback(() => {
    if (elapsedTimerRef.current) {
      clearInterval(elapsedTimerRef.current)
      elapsedTimerRef.current = null
    }
  }, [])

  useEffect(() => () => stopTimer(), [stopTimer])

  // ── Load handler ──
  const handleLoad = useCallback(() => {
    if (!ptId || !fromDate) return
    setLoading(true)
    setLoadError(null)
    setAggregates([])
    startTimer()

    const effectiveTo = toDate || fromDate
    const label = `pop_aggregates(${groupBy}, ${fromDate}..${effectiveTo}${selectedCanon ? `, ${selectedCanon}` : ''})`

    track(label, api.getPopAggregates(ptId, {
      group_by:   groupBy,
      from_date:  fromDate,
      to_date:    effectiveTo,
      owner_tags: ownerTagsForQuery || undefined,
    }))
      .then((data) => setAggregates(data || []))
      .catch((err) => {
        if (err?.name === 'AbortError' || err?.message?.toLowerCase().includes('abort')) {
          setLoadError('cancelled')
        } else {
          setLoadError(err?.message || 'Failed to load data')
        }
        setAggregates([])
      })
      .finally(() => {
        setLoading(false)
        stopTimer()
      })
  }, [ptId, fromDate, toDate, groupBy, ownerTagsForQuery, selectedCanon, api, track, startTimer, stopTimer])

  // ── Derived chart data ──
  const isTimeSeries = fromDate && toDate && fromDate !== toDate

  const { groups, dates } = useMemo(() => {
    const groupSet = new Set()
    const dateSet  = new Set()
    aggregates.forEach((a) => {
      groupSet.add(String(a[groupBy] ?? 'Unknown'))
      dateSet.add(a.game_date)
    })
    return {
      groups: Array.from(groupSet).sort(),
      dates:  Array.from(dateSet).sort(),
    }
  }, [aggregates, groupBy])

  // Stacked area: [{ date, peasants: 1234, clergy: 456, … }]
  const trendData = useMemo(() => {
    if (dates.length === 0) return []
    const byDate = Object.fromEntries(dates.map((d) => [d, { date: d }]))
    aggregates.forEach((a) => {
      const g = String(a[groupBy] ?? 'Unknown')
      if (byDate[a.game_date]) byDate[a.game_date][g] = (a.total_size || 0) * 1000
    })
    return Object.values(byDate)
  }, [aggregates, dates, groupBy])

  // Pie/table: single date point
  const breakdownData = useMemo(() => {
    if (dates.length === 0) return []
    const target = dates[0]   // point-in-time → only one date; time series covered by trendData
    return aggregates
      .filter((a) => a.game_date === target)
      .map((a) => ({
        name:   String(a[groupBy] ?? 'Unknown'),
        value:  (a.total_size || 0) * 1000,
        count:  a.pop_count,
        avgSat: a.avg_satisfaction,
        avgLit: a.avg_literacy,
      }))
      .sort((a, b) => b.value - a.value)
  }, [aggregates, dates, groupBy])

  // Satisfaction & literacy lines (type grouping only)
  const buildLineData = (field, rounder) => {
    if (dates.length === 0 || groupBy !== 'type') return []
    const byDate = Object.fromEntries(dates.map((d) => [d, { date: d }]))
    aggregates.forEach((a) => {
      const g = String(a[groupBy] ?? 'Unknown')
      if (byDate[a.game_date] && a[field] != null)
        byDate[a.game_date][g] = rounder(a[field])
    })
    return Object.values(byDate)
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const satData = useMemo(() => buildLineData('avg_satisfaction', (v) => Math.round(v * 1000) / 1000), [aggregates, dates, groupBy])
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const litData = useMemo(() => buildLineData('avg_literacy',     (v) => Math.round(v * 100) / 100),   [aggregates, dates, groupBy])

  // ── Early-out: no playthrough ──
  if (!ptId) {
    return (
      <div className="p-6 text-sm" style={{ color: 'var(--color-text-muted)' }}>
        No playthrough loaded. Start the pipeline or load a saved playthrough.
      </div>
    )
  }

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className="p-6 space-y-4">

      {/* ── Controls bar ── */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'flex-end' }}>

        {/* Country picker */}
        <div>
          <div className="text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>Country</div>
          <select
            value={selectedCanon || ''}
            onChange={(e) => setSelectedCanon(e.target.value || null)}
            style={{ ...ctrlStyle, minWidth: 170 }}
          >
            <option value="">All countries</option>
            {countryGroups.map((g) => (
              <option key={g.canonical_tag} value={g.canonical_tag}>
                {fmtCountry(g.canonical_tag, nameMap)}
                {g.tags.length > 1 ? ` (+${g.tags.length - 1})` : ''}
              </option>
            ))}
          </select>
        </div>

        {/* From date */}
        <div>
          <div className="text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>From</div>
          <select
            value={fromDate || ''}
            onChange={(e) => {
              const d = e.target.value
              setFromDate(d)
              if (toDate && toDate < d) setToDate(d)
            }}
            style={ctrlStyle}
          >
            {snapshotDates.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>

        {/* To date */}
        <div>
          <div className="text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>To</div>
          <select
            value={toDate || ''}
            onChange={(e) => setToDate(e.target.value)}
            style={ctrlStyle}
          >
            {snapshotDates
              .filter((d) => d >= (fromDate || ''))
              .map((d) => <option key={d} value={d}>{d}</option>)
            }
          </select>
        </div>

        {/* Group by */}
        <div>
          <div className="text-xs mb-1" style={{ color: 'var(--color-text-muted)' }}>Group by</div>
          <div style={{ display: 'flex', gap: 4 }}>
            {GROUP_BY_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                onClick={() => setGroupBy(opt.key)}
                style={{
                  background: groupBy === opt.key ? 'var(--color-accent)' : 'var(--color-surface)',
                  color:      groupBy === opt.key ? '#fff' : 'var(--color-text-muted)',
                  border:     '1px solid var(--color-border)',
                  borderRadius: 4,
                  padding:    '3px 8px',
                  fontSize:   12,
                  cursor:     'pointer',
                  transition: 'background 0.15s, color 0.15s',
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Load button */}
        <button
          onClick={handleLoad}
          disabled={loading || !fromDate}
          style={{
            background:   loading ? 'var(--color-surface)' : 'var(--color-accent)',
            color:        loading ? 'var(--color-text-muted)' : '#fff',
            border:       '1px solid var(--color-border)',
            borderRadius: 6,
            padding:      '4px 16px',
            fontSize:     13,
            fontWeight:   600,
            cursor:       loading || !fromDate ? 'not-allowed' : 'pointer',
            opacity:      !fromDate ? 0.5 : 1,
            transition:   'background 0.15s, color 0.15s',
            alignSelf:    'flex-end',
            minWidth:     90,
          }}
        >
          {loading ? `${fmtMs(elapsed)}` : 'Load'}
        </button>
      </div>

      {/* ── Mode badge (show when data is loaded) ── */}
      {aggregates.length > 0 && (
        <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
          {isTimeSeries
            ? `Time series · ${dates.length} date(s) · ${fromDate} → ${toDate}`
            : `Point-in-time · ${fromDate}`}
          {selectedCanon && ` · ${fmtCountry(selectedCanon, nameMap)}`}
          {ownerTagsForQuery && ownerTagsForQuery.length > 1 && (
            <span style={{ marginLeft: 4, opacity: 0.6 }}>
              (incl. {ownerTagsForQuery.slice(0, -1).join(', ')})
            </span>
          )}
        </div>
      )}

      {/* ── Status / content area ── */}
      {loadError === 'cancelled' ? (
        <StatusBox>Request cancelled.</StatusBox>
      ) : loadError ? (
        <StatusBox color="#ef4444">Error: {loadError}</StatusBox>
      ) : loading ? (
        <StatusBox>
          <div>Loading demographics… {fmtMs(elapsed)}</div>
          <div style={{ fontSize: 11, marginTop: 4, opacity: 0.65 }}>
            Use the Abort button (top-right) to cancel.
          </div>
        </StatusBox>
      ) : aggregates.length === 0 ? (
        <StatusBox>
          {snapshotDates.length === 0
            ? 'No snapshot data available yet.'
            : 'Select options above and click Load.'}
        </StatusBox>
      ) : isTimeSeries ? (
        <TimeSeries
          trendData={trendData}
          satData={satData}
          litData={litData}
          groups={groups}
          groupBy={groupBy}
          getColor={getColor}
          tooltipStyle={tooltipStyle}
        />
      ) : (
        <PointInTime
          breakdownData={breakdownData}
          fromDate={fromDate}
          groupBy={groupBy}
          getColor={getColor}
          tooltipStyle={tooltipStyle}
        />
      )}
    </div>
  )
}

// ─── sub-components ───────────────────────────────────────────────────────────

function StatusBox({ children, color }) {
  return (
    <div
      className="rounded-lg p-8 text-center text-sm"
      style={{ background: 'var(--color-surface)', color: color || 'var(--color-text-muted)' }}
    >
      {children}
    </div>
  )
}

function ChartCard({ title, height = 320, children }) {
  return (
    <div className="rounded-lg p-4" style={{ background: 'var(--color-surface)' }}>
      {title && <h3 className="text-sm font-medium mb-3">{title}</h3>}
      <ResponsiveContainer width="100%" height={height}>
        {children}
      </ResponsiveContainer>
    </div>
  )
}

const axisStyle  = { fill: 'var(--color-text-muted)', fontSize: 11 }
const gridStyle  = { stroke: 'var(--color-border)' }

function yTickFmt(v) {
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M'
  if (v >= 1_000)     return (v / 1_000).toFixed(1).replace(/\.0$/, '')     + 'K'
  return Math.round(v).toString()
}

function TimeSeries({ trendData, satData, litData, groups, groupBy, getColor, tooltipStyle }) {
  const label = GROUP_BY_OPTIONS.find((o) => o.key === groupBy)?.label

  return (
    <div className="space-y-4">
      {/* Population stacked area */}
      <ChartCard title={`Population by ${label}`} height={350}>
        <AreaChart data={trendData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" {...gridStyle} />
          <XAxis dataKey="date" tick={axisStyle} stroke="var(--color-border)" />
          <YAxis tick={axisStyle} stroke="var(--color-border)" tickFormatter={yTickFmt} />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(v, name) => [v.toLocaleString(undefined, { maximumFractionDigits: 0 }), name]}
          />
          <Legend wrapperStyle={{ fontSize: '12px', color: 'var(--color-text-muted)' }} />
          {groups.map((g, i) => (
            <Area key={g} type="monotone" dataKey={g} stackId="1"
              fill={getColor(groupBy, g, i)} stroke={getColor(groupBy, g, i)} fillOpacity={0.6} />
          ))}
        </AreaChart>
      </ChartCard>

      {/* Satisfaction (type only) */}
      {groupBy === 'type' && satData.length > 0 && (
        <ChartCard title="Average Satisfaction by Type" height={280}>
          <LineChart data={satData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" {...gridStyle} />
            <XAxis dataKey="date" tick={axisStyle} stroke="var(--color-border)" />
            <YAxis domain={[0, 1]} tick={axisStyle} stroke="var(--color-border)" />
            <Tooltip contentStyle={tooltipStyle} />
            <Legend wrapperStyle={{ fontSize: '12px', color: 'var(--color-text-muted)' }} />
            {groups.map((g, i) => (
              <Line key={g} type="monotone" dataKey={g} stroke={getColor(groupBy, g, i)}
                strokeWidth={2} dot={false} connectNulls />
            ))}
          </LineChart>
        </ChartCard>
      )}

      {/* Literacy (type only) */}
      {groupBy === 'type' && litData.length > 0 && (
        <ChartCard title="Average Literacy by Type (%)" height={280}>
          <LineChart data={litData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" {...gridStyle} />
            <XAxis dataKey="date" tick={axisStyle} stroke="var(--color-border)" />
            <YAxis tick={axisStyle} stroke="var(--color-border)" />
            <Tooltip contentStyle={tooltipStyle} />
            <Legend wrapperStyle={{ fontSize: '12px', color: 'var(--color-text-muted)' }} />
            {groups.map((g, i) => (
              <Line key={g} type="monotone" dataKey={g} stroke={getColor(groupBy, g, i)}
                strokeWidth={2} dot={false} connectNulls />
            ))}
          </LineChart>
        </ChartCard>
      )}
    </div>
  )
}

function PointInTime({ breakdownData, fromDate, groupBy, getColor, tooltipStyle }) {
  const label = GROUP_BY_OPTIONS.find((o) => o.key === groupBy)?.label

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* Pie */}
      <ChartCard title={`Composition at ${fromDate} — ${label}`} height={350}>
        <PieChart>
          <Pie
            data={breakdownData}
            dataKey="value"
            nameKey="name"
            cx="50%" cy="50%"
            outerRadius={130}
            label={({ name, percent }) => `${name} ${(percent * 100).toFixed(1)}%`}
            labelLine={{ stroke: 'var(--color-text-muted)' }}
          >
            {breakdownData.map((entry, i) => (
              <Cell key={entry.name} fill={getColor(groupBy, entry.name, i)} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(val) => val.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          />
        </PieChart>
      </ChartCard>

      {/* Table */}
      <div className="rounded-lg overflow-hidden" style={{ background: 'var(--color-surface)' }}>
        <h3 className="text-sm font-medium px-4 pt-3 pb-2">Breakdown Details</h3>
        <div className="overflow-x-auto" style={{ maxHeight: 350, overflowY: 'auto' }}>
          <table className="w-full text-xs">
            <thead style={{ position: 'sticky', top: 0 }}>
              <tr style={{ background: 'var(--color-surface-alt)', color: 'var(--color-text-muted)' }}>
                <th className="text-left px-3 py-2">{label}</th>
                <th className="text-right px-3 py-2">Count</th>
                <th className="text-right px-3 py-2">Total Size</th>
                <th className="text-right px-3 py-2">Avg Sat</th>
                <th className="text-right px-3 py-2">Avg Lit</th>
              </tr>
            </thead>
            <tbody>
              {breakdownData.map((row, i) => (
                <tr key={row.name} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td className="px-3 py-1.5 capitalize">
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                      <span
                        style={{
                          display: 'inline-block', width: 10, height: 10,
                          borderRadius: 2, flexShrink: 0,
                          background: getColor(groupBy, row.name, i),
                        }}
                      />
                      {row.name}
                    </span>
                  </td>
                  <td className="px-3 py-1.5 text-right">{row.count.toLocaleString()}</td>
                  <td className="px-3 py-1.5 text-right">
                    {row.value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </td>
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
  )
}
