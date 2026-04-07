/**
 * ParticipantScoresChart — score_combat over time per war participant.
 *
 * Fetches /api/wars/{ptId}/participant-history?war_id=... and renders one
 * line per country, colored by their side (warm=attacker, cool=defender).
 * Shows top 10 by peak score with a toggle for all.
 */

import { useState, useEffect, useMemo } from 'react'
import {
  LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { useApi } from '../../hooks/useApi'
import { euDateToNum, fmtYearTick, fmtCountry } from '../../utils/formatters'

const ATK_PALETTE = ['#f97316','#ef4444','#f59e0b','#84cc16','#b45309','#ea580c','#d97706','#dc2626','#fbbf24','#65a30d']
const DEF_PALETTE = ['#3b82f6','#6366f1','#8b5cf6','#06b6d4','#1d4ed8','#60a5fa','#4f46e5','#7c3aed','#0891b2','#0284c7']
const MAX_SHOWN = 10

export default function ParticipantScoresChart({ ptId, warId, participants, nameMap }) {
  const api = useApi()
  const [history, setHistory]   = useState([])
  const [loading, setLoading]   = useState(false)
  const [showAll, setShowAll]   = useState(false)

  const attackers = useMemo(() => participants.filter(p => p.side === 'Attacker'), [participants])
  const defenders = useMemo(() => participants.filter(p => p.side === 'Defender'), [participants])
  const attackerTags = useMemo(() => new Set(attackers.map(p => p.country_tag).filter(Boolean)), [attackers])
  const defenderTags = useMemo(() => new Set(defenders.map(p => p.country_tag).filter(Boolean)), [defenders])

  useEffect(() => {
    if (!ptId || !warId) return
    let cancelled = false
    setLoading(true)
    setHistory([])
    api.getWarParticipantHistory(ptId, { war_id: warId })
      .then(rows => { if (!cancelled) setHistory(rows || []) })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [ptId, warId])

  // Select which tags to show
  const { visibleTags, totalCount } = useMemo(() => {
    if (!history.length) return { visibleTags: [], totalCount: 0 }

    // Peak score_combat per tag
    const peak = {}
    history.forEach(r => {
      if (r.country_tag) peak[r.country_tag] = Math.max(peak[r.country_tag] || 0, r.score_combat || 0)
    })
    const allTags = [...new Set(history.map(r => r.country_tag).filter(Boolean))]
    const total   = allTags.length

    if (showAll) return { visibleTags: allTags, totalCount: total }

    // Take top 10 by peak score across both sides
    const topTags = allTags.sort((a, b) => (peak[b] || 0) - (peak[a] || 0)).slice(0, MAX_SHOWN)
    return { visibleTags: topTags, totalCount: total }
  }, [history, showAll])

  // Build time-series: one entry per unique date, one key per visible tag
  const chartData = useMemo(() => {
    if (!visibleTags.length) return []

    const tagSet = new Set(visibleTags)
    const byDate = {}
    history.forEach(r => {
      if (!tagSet.has(r.country_tag)) return
      if (!byDate[r.game_date]) byDate[r.game_date] = { date: r.game_date, dateNum: euDateToNum(r.game_date) }
      byDate[r.game_date][r.country_tag] = r.score_combat || 0
    })

    return Object.values(byDate).sort((a, b) => a.dateNum - b.dateNum)
  }, [history, visibleTags])

  const btnBase   = 'px-3 py-1 text-xs rounded transition-colors'
  const btnActive = { background: 'var(--color-accent)', color: '#fff' }
  const btnIdle   = { background: 'var(--color-surface-alt)', color: 'var(--color-text-muted)' }

  const labelFormatter = (_v, payload) => payload?.[0]?.payload?.date ?? ''

  if (loading) {
    return (
      <div className="rounded-lg p-8 text-center text-xs"
        style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}>
        Loading…
      </div>
    )
  }
  if (!chartData.length) {
    return (
      <div className="rounded-lg p-8 text-center text-xs"
        style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}>
        No participant score history available for this war.
      </div>
    )
  }

  return (
    <div className="rounded-lg p-4 space-y-3" style={{ background: 'var(--color-surface)' }}>
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Combat Score Over Time</span>
        {totalCount > MAX_SHOWN && (
          <button className={btnBase} style={showAll ? btnActive : btnIdle}
            onClick={() => setShowAll(v => !v)}>
            {showAll ? `Show top ${MAX_SHOWN}` : `Show all ${totalCount}`}
          </button>
        )}
      </div>

      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData} margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis
            dataKey="dateNum"
            type="number"
            scale="linear"
            domain={['dataMin', 'dataMax']}
            tickFormatter={fmtYearTick}
            tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }}
            stroke="var(--color-border)"
          />
          <YAxis
            tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }}
            stroke="var(--color-border)"
            width={40}
          />
          <Tooltip
            contentStyle={{
              background: 'var(--color-surface-alt)',
              border: '1px solid var(--color-border)',
              borderRadius: '6px',
              color: 'var(--color-text)',
              fontSize: '11px',
            }}
            labelFormatter={labelFormatter}
            formatter={(v, name) => [v?.toFixed(1) ?? '—', fmtCountry(name, nameMap, { showPrev: false })]}
          />
          <Legend
            formatter={(tag) => fmtCountry(tag, nameMap, { showPrev: false })}
            wrapperStyle={{ fontSize: '11px', color: 'var(--color-text-muted)', paddingTop: '8px' }}
          />
          {visibleTags.map((tag, i) => {
            const isAtk = attackerTags.has(tag)
            const palette = isAtk ? ATK_PALETTE : DEF_PALETTE
            return (
              <Line
                key={tag}
                type="monotone"
                dataKey={tag}
                stroke={palette[i % palette.length]}
                strokeWidth={2}
                dot={false}
                connectNulls
              />
            )
          })}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
