/**
 * WarForcesChart — stacked area chart showing army/navy strength over the
 * course of a war.
 *
 * Layout: attacker-side areas stack from 0 upward; defender-side areas stack
 * on top; a separator Line traces the attacker total so the boundary between
 * the two coalitions is always clearly visible.
 *
 * Grouping modes:
 *   "unit_type" — aggregate all participants per side, split by unit category
 *   "country"   — one area per country, top-10 by peak strength (toggle for all)
 *
 * Force types: "army" (inf/cav/art/aux) | "navy" (galley/light/transport/heavy)
 */

import { useState, useEffect, useMemo } from 'react'
import {
  ComposedChart, Area, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { useApi } from '../../hooks/useApi'
import { euDateToNum, fmtYearTick } from '../../utils/formatters'

// ── Color palettes ────────────────────────────────────────────────────────────

const ATK_UNIT = {
  infantry:   '#f97316',  // orange-500
  cavalry:    '#ea580c',  // orange-600
  artillery:  '#fbbf24',  // amber-400
  auxiliary:  '#fde68a',  // amber-200
  galley:     '#f97316',
  light_ship: '#ea580c',
  transport:  '#fbbf24',
  heavy_ship: '#fde68a',
}
const DEF_UNIT = {
  infantry:   '#3b82f6',  // blue-500
  cavalry:    '#1d4ed8',  // blue-700
  artillery:  '#60a5fa',  // blue-400
  auxiliary:  '#bfdbfe',  // blue-200
  galley:     '#3b82f6',
  light_ship: '#1d4ed8',
  transport:  '#60a5fa',
  heavy_ship: '#bfdbfe',
}

const ATK_COUNTRY_PALETTE = [
  '#ef4444','#f97316','#f59e0b','#84cc16',
  '#b45309','#dc2626','#ea580c','#d97706','#65a30d','#991b1b',
]
const DEF_COUNTRY_PALETTE = [
  '#3b82f6','#6366f1','#8b5cf6','#06b6d4',
  '#1d4ed8','#4f46e5','#7c3aed','#0891b2','#0284c7','#4338ca',
]

const LAND_SLOTS  = ['infantry', 'cavalry', 'artillery', 'auxiliary']
const NAVAL_SLOTS = ['galley', 'light_ship', 'transport', 'heavy_ship']

const SLOT_LABELS = {
  infantry: 'Infantry', cavalry: 'Cavalry', artillery: 'Artillery', auxiliary: 'Auxiliary',
  galley: 'Galley', light_ship: 'Light Ship', transport: 'Transport', heavy_ship: 'Heavy Ship',
}

const MAX_SHOWN = 10

// ── Helpers ───────────────────────────────────────────────────────────────────

function sumSlots(arr, slots) {
  if (!Array.isArray(arr)) return 0
  // slots is array of indices 0-7: [inf,cav,art,aux,gal,lgt,trp,hvy]
  return slots.reduce((s, i) => s + (arr[i] || 0), 0)
}

function fmtK(v) {
  if (v == null || isNaN(v)) return ''
  if (v >= 1000) return (v / 1000).toFixed(1).replace(/\.0$/, '') + 'k'
  return Math.round(v).toString()
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function WarForcesChart({ ptId, war, participants }) {
  const api = useApi()
  const [milData, setMilData] = useState([])
  const [loading, setLoading] = useState(false)
  const [groupBy, setGroupBy] = useState('unit_type')   // 'unit_type' | 'country'
  const [forceType, setForceType] = useState('army')    // 'army' | 'navy'
  const [showAll, setShowAll] = useState(false)

  const attackers = useMemo(() => participants.filter(p => p.side === 'Attacker'), [participants])
  const defenders = useMemo(() => participants.filter(p => p.side === 'Defender'), [participants])

  // Fetch military snapshots for all war participants
  useEffect(() => {
    if (!ptId || !participants.length || !war) return
    const tags = participants.map(p => p.country_tag).filter(Boolean)
    if (!tags.length) return

    let cancelled = false
    setLoading(true)
    setMilData([])

    api.getMilitarySnapshots(ptId, {
      country_tags: tags.join(','),
      from_date: war.start_date,
      to_date: war.end_date || undefined,
    }).then(rows => {
      if (!cancelled) setMilData(rows || [])
    }).catch(() => {}).finally(() => {
      if (!cancelled) setLoading(false)
    })

    return () => { cancelled = true }
  }, [ptId, war?.id, participants.length])

  // Build join-date lookup (tag → join_date as numeric for fast comparison)
  const joinDateNum = useMemo(() => {
    const m = {}
    participants.forEach(p => {
      if (p.country_tag && p.join_date) m[p.country_tag] = euDateToNum(p.join_date)
    })
    return m
  }, [participants])

  const attackerTagSet = useMemo(() => new Set(attackers.map(p => p.country_tag).filter(Boolean)), [attackers])
  const defenderTagSet = useMemo(() => new Set(defenders.map(p => p.country_tag).filter(Boolean)), [defenders])

  const slots = forceType === 'army' ? LAND_SLOTS : NAVAL_SLOTS

  // ── "By unit type" chart data ────────────────────────────────────────────
  const unitTypeData = useMemo(() => {
    if (!milData.length || groupBy !== 'unit_type') return []

    const byDate = {}
    milData.forEach(row => {
      const tag = row.country_tag
      if (!tag) return
      const dNum = euDateToNum(row.game_date)
      const jNum = joinDateNum[tag]
      if (jNum && dNum < jNum) return  // country not yet in war at this snapshot

      if (!byDate[row.game_date]) {
        byDate[row.game_date] = {}
        slots.forEach(s => { byDate[row.game_date][`atk_${s}`] = 0; byDate[row.game_date][`def_${s}`] = 0 })
      }
      const d = byDate[row.game_date]
      const prefix = attackerTagSet.has(tag) ? 'atk' : defenderTagSet.has(tag) ? 'def' : null
      if (!prefix) return
      slots.forEach(s => { d[`${prefix}_${s}`] += row[`${s}_strength`] || 0 })
    })

    return Object.entries(byDate)
      .sort(([a], [b]) => euDateToNum(a) - euDateToNum(b))
      .map(([date, d]) => {
        const atk_total = slots.reduce((s, slot) => s + (d[`atk_${slot}`] || 0), 0)
        return { date, dateNum: euDateToNum(date), ...d, atk_total }
      })
  }, [milData, groupBy, forceType, attackerTagSet, defenderTagSet, joinDateNum])

  // ── "By country" chart data ──────────────────────────────────────────────
  const { countryData, visibleAtkTags, visibleDefTags, totalParticipants } = useMemo(() => {
    if (!milData.length || groupBy !== 'country') {
      return { countryData: [], visibleAtkTags: [], visibleDefTags: [], totalParticipants: 0 }
    }

    // Peak strength per tag
    const peak = {}
    milData.forEach(row => {
      if (!row.country_tag) return
      const val = forceType === 'army' ? (row.army_strength || 0) : (row.navy_strength || 0)
      peak[row.country_tag] = Math.max(peak[row.country_tag] || 0, val)
    })

    // Sort each side by peak strength desc
    const atkSorted = [...attackerTagSet].sort((a, b) => (peak[b] || 0) - (peak[a] || 0))
    const defSorted = [...defenderTagSet].sort((a, b) => (peak[b] || 0) - (peak[a] || 0))
    const total = atkSorted.length + defSorted.length

    // Top-10 split proportionally between sides
    const atkCap = showAll ? atkSorted.length : Math.min(atkSorted.length, Math.ceil(MAX_SHOWN * atkSorted.length / total))
    const defCap = showAll ? defSorted.length : Math.min(defSorted.length, MAX_SHOWN - atkCap)
    const visAtk = atkSorted.slice(0, showAll ? undefined : atkCap)
    const visDef = defSorted.slice(0, showAll ? undefined : defCap)
    const allVisible = new Set([...visAtk, ...visDef])

    // All unique dates
    const allDates = [...new Set(milData.map(r => r.game_date))]
      .sort((a, b) => euDateToNum(a) - euDateToNum(b))

    // Build per-date per-tag values
    const tagDateVal = {}
    milData.forEach(row => {
      if (!row.country_tag || !allVisible.has(row.country_tag)) return
      const dNum = euDateToNum(row.game_date)
      const jNum = joinDateNum[row.country_tag]
      const val = jNum && dNum < jNum ? 0
        : forceType === 'army' ? (row.army_strength || 0) : (row.navy_strength || 0)
      if (!tagDateVal[row.country_tag]) tagDateVal[row.country_tag] = {}
      tagDateVal[row.country_tag][row.game_date] = val
    })

    const data = allDates.map(date => {
      const row = { date, dateNum: euDateToNum(date) }
      let atkTotal = 0
      visAtk.forEach(tag => {
        const v = tagDateVal[tag]?.[date] ?? 0
        row[tag] = v
        atkTotal += v
      })
      visDef.forEach(tag => { row[tag] = tagDateVal[tag]?.[date] ?? 0 })
      row.atk_total = atkTotal
      return row
    })

    return { countryData: data, visibleAtkTags: visAtk, visibleDefTags: visDef, totalParticipants: total }
  }, [milData, groupBy, forceType, attackerTagSet, defenderTagSet, joinDateNum, showAll])

  const chartData  = groupBy === 'unit_type' ? unitTypeData : countryData
  const isNavy     = forceType === 'navy'
  const noData     = !loading && chartData.length === 0

  // ── Tooltip label ────────────────────────────────────────────────────────
  const labelFormatter = (_v, payload) => payload?.[0]?.payload?.date ?? ''

  // ── Tooltip value formatter ──────────────────────────────────────────────
  const valueFormatter = (v) => fmtK(v)

  // ── Render controls ──────────────────────────────────────────────────────
  const btnBase = 'px-3 py-1 text-xs rounded transition-colors'
  const btnActive = { background: 'var(--color-accent)', color: '#fff' }
  const btnIdle   = { background: 'var(--color-surface-alt)', color: 'var(--color-text-muted)' }

  return (
    <div className="rounded-lg p-4 space-y-3" style={{ background: 'var(--color-surface)' }}>
      {/* Controls row */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex gap-1">
          <button className={btnBase} style={forceType === 'army' ? btnActive : btnIdle}
            onClick={() => setForceType('army')}>Army</button>
          <button className={btnBase} style={forceType === 'navy' ? btnActive : btnIdle}
            onClick={() => setForceType('navy')}>Navy</button>
        </div>
        <div className="flex gap-1">
          <button className={btnBase} style={groupBy === 'unit_type' ? btnActive : btnIdle}
            onClick={() => setGroupBy('unit_type')}>By unit type</button>
          <button className={btnBase} style={groupBy === 'country' ? btnActive : btnIdle}
            onClick={() => setGroupBy('country')}>By country</button>
        </div>
        {groupBy === 'country' && totalParticipants > MAX_SHOWN && (
          <button className={btnBase} style={showAll ? btnActive : btnIdle}
            onClick={() => setShowAll(v => !v)}>
            {showAll ? `Show top ${MAX_SHOWN}` : `Show all ${totalParticipants}`}
          </button>
        )}
      </div>

      {/* Chart */}
      {loading && (
        <p className="text-xs text-center py-8" style={{ color: 'var(--color-text-muted)' }}>Loading…</p>
      )}
      {noData && !loading && (
        <p className="text-xs text-center py-8" style={{ color: 'var(--color-text-muted)' }}>
          No military data available for this war.
        </p>
      )}
      {!loading && chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={360}>
          <ComposedChart data={chartData} margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
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
              tickFormatter={fmtK}
              tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }}
              stroke="var(--color-border)"
              width={48}
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
              formatter={valueFormatter}
            />
            <Legend
              wrapperStyle={{ fontSize: '11px', color: 'var(--color-text-muted)', paddingTop: '8px' }}
            />

            {groupBy === 'unit_type' ? (
              <>
                {/* Attacker unit areas (warm, bottom) */}
                {slots.map(s => (
                  <Area key={`atk_${s}`} stackId="forces"
                    dataKey={`atk_${s}`} name={`Atk ${SLOT_LABELS[s]}`}
                    fill={ATK_UNIT[s]} stroke="none" fillOpacity={0.85} />
                ))}
                {/* Separator line at attacker total */}
                <Line dataKey="atk_total" name="" dot={false} legendType="none"
                  stroke="rgba(255,255,255,0.6)" strokeWidth={2} strokeDasharray="4 2" />
                {/* Defender unit areas (cool, top) */}
                {slots.map(s => (
                  <Area key={`def_${s}`} stackId="forces"
                    dataKey={`def_${s}`} name={`Def ${SLOT_LABELS[s]}`}
                    fill={DEF_UNIT[s]} stroke="none" fillOpacity={0.85} />
                ))}
              </>
            ) : (
              <>
                {/* Attacker country areas (warm palette, bottom) */}
                {visibleAtkTags.map((tag, i) => (
                  <Area key={`atk_${tag}`} stackId="forces"
                    dataKey={tag} name={`⚔ ${tag}`}
                    fill={ATK_COUNTRY_PALETTE[i % ATK_COUNTRY_PALETTE.length]}
                    stroke="none" fillOpacity={0.85} connectNulls={false} />
                ))}
                {/* Separator line */}
                <Line dataKey="atk_total" name="" dot={false} legendType="none"
                  stroke="rgba(255,255,255,0.6)" strokeWidth={2} strokeDasharray="4 2" />
                {/* Defender country areas (cool palette, top) */}
                {visibleDefTags.map((tag, i) => (
                  <Area key={`def_${tag}`} stackId="forces"
                    dataKey={tag} name={`🛡 ${tag}`}
                    fill={DEF_COUNTRY_PALETTE[i % DEF_COUNTRY_PALETTE.length]}
                    stroke="none" fillOpacity={0.85} connectNulls={false} />
                ))}
              </>
            )}
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* Side legend */}
      <div className="flex gap-6 text-xs justify-center" style={{ color: 'var(--color-text-muted)' }}>
        <span style={{ color: ATK_UNIT.infantry }}>■ Attackers (bottom)</span>
        <span style={{ color: DEF_UNIT.infantry }}>■ Defenders (top)</span>
        <span style={{ borderBottom: '2px dashed rgba(255,255,255,0.5)', paddingBottom: '1px' }}>
          — boundary
        </span>
      </div>
    </div>
  )
}
