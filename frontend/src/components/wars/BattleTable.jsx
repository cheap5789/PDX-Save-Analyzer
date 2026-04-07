/**
 * BattleTable — sortable table of detected battles for a war.
 *
 * Columns: Date | Type | Attacker | Atk Forces | Atk Losses | Defender |
 *          Def Forces | Def Losses | Winner | Score Δ
 *
 * Forces/losses are 8-slot JSON arrays; we sum land slots [0-3] for land
 * battles and naval slots [4-7] for naval battles.
 */

import { useMemo, useState } from 'react'
import { fmtCountry } from '../../utils/formatters'

// Column definitions
const COLS = [
  { key: 'game_date',       label: 'Date',        align: 'left'  },
  { key: 'type',            label: 'Type',        align: 'left'  },
  { key: 'atk_name',        label: 'Attacker',    align: 'left'  },
  { key: 'atk_forces',      label: 'Atk Forces',  align: 'right' },
  { key: 'atk_losses_sum',  label: 'Atk Losses',  align: 'right' },
  { key: 'def_name',        label: 'Defender',    align: 'left'  },
  { key: 'def_forces',      label: 'Def Forces',  align: 'right' },
  { key: 'def_losses_sum',  label: 'Def Losses',  align: 'right' },
  { key: 'winner',          label: 'Winner',      align: 'left'  },
  { key: 'war_score_delta', label: 'Score Δ',     align: 'right' },
]

function slotSum(arr, isLand) {
  if (!Array.isArray(arr)) return 0
  const indices = isLand ? [0, 1, 2, 3] : [4, 5, 6, 7]
  return indices.reduce((s, i) => s + (arr[i] || 0), 0)
}

function fmtNum(v) {
  if (v == null || isNaN(v)) return '—'
  const n = Math.round(v)
  return n >= 1000 ? (n / 1000).toFixed(1).replace(/\.0$/, '') + 'k' : n.toString()
}

export default function BattleTable({ battles, participants, nameMap }) {
  const [sortKey, setSortKey]   = useState('game_date')
  const [sortDir, setSortDir]   = useState('asc')

  // Build id → tag lookup from participants
  const idToTag = useMemo(() => {
    const m = {}
    ;(participants || []).forEach(p => { if (p.country_id) m[p.country_id] = p.country_tag })
    return m
  }, [participants])

  // Enrich battle rows with derived fields
  const rows = useMemo(() => {
    return (battles || []).map(b => {
      const isLand = b.is_land !== false
      const atkTag  = idToTag[b.attacker_country_id] || null
      const defTag  = idToTag[b.defender_country_id] || null
      return {
        ...b,
        type:           isLand ? 'Land' : 'Naval',
        atk_name:       atkTag ? fmtCountry(atkTag, nameMap, { showPrev: false }) : (b.attacker_country_id ? `#${b.attacker_country_id}` : '—'),
        atk_forces:     slotSum(b.attacker_forces, isLand),
        atk_losses_sum: slotSum(b.attacker_losses, isLand),
        def_name:       defTag ? fmtCountry(defTag, nameMap, { showPrev: false }) : (b.defender_country_id ? `#${b.defender_country_id}` : '—'),
        def_forces:     slotSum(b.defender_forces, isLand),
        def_losses_sum: slotSum(b.defender_losses, isLand),
        winner:         b.war_attacker_win == null ? '—' : b.war_attacker_win ? 'Attacker' : 'Defender',
        _atkTag: atkTag,
        _defTag: defTag,
      }
    })
  }, [battles, idToTag, nameMap])

  // Sort
  const sorted = useMemo(() => {
    return [...rows].sort((a, b) => {
      let va = a[sortKey], vb = b[sortKey]
      if (va == null) va = sortDir === 'asc' ? Infinity : -Infinity
      if (vb == null) vb = sortDir === 'asc' ? Infinity : -Infinity
      if (typeof va === 'string' && typeof vb === 'string') {
        return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va)
      }
      return sortDir === 'asc' ? va - vb : vb - va
    })
  }, [rows, sortKey, sortDir])

  const handleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('asc') }
  }

  const arrow = (key) => sortKey === key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''

  if (!battles?.length) {
    return (
      <div className="rounded-lg p-8 text-center text-xs"
        style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}>
        No battles recorded for this war yet.
      </div>
    )
  }

  return (
    <div className="rounded-lg overflow-hidden" style={{ background: 'var(--color-surface)' }}>
      <div className="px-4 py-2 flex items-center justify-between"
        style={{ background: 'var(--color-surface-alt)', borderBottom: '1px solid var(--color-border)' }}>
        <span className="text-xs font-medium">{sorted.length} battle{sorted.length !== 1 ? 's' : ''}</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'var(--color-surface-alt)' }}>
              {COLS.map(col => (
                <th
                  key={col.key}
                  onClick={() => handleSort(col.key)}
                  className="px-3 py-2 cursor-pointer select-none whitespace-nowrap"
                  style={{
                    textAlign: col.align,
                    color: sortKey === col.key ? 'var(--color-accent)' : 'var(--color-text-muted)',
                    borderBottom: '1px solid var(--color-border)',
                    fontWeight: 500,
                  }}
                >
                  {col.label}{arrow(col.key)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((b, i) => (
              <tr
                key={b.id}
                style={{
                  background: i % 2 === 0 ? 'transparent' : 'var(--color-surface-alt)',
                  borderBottom: '1px solid var(--color-border)',
                }}
              >
                <td className="px-3 py-1.5 whitespace-nowrap">{b.game_date}</td>
                <td className="px-3 py-1.5">
                  <span style={{
                    color: b.type === 'Land' ? '#84cc16' : '#38bdf8',
                    fontWeight: 500,
                  }}>{b.type}</span>
                </td>
                <td className="px-3 py-1.5 whitespace-nowrap" style={{ color: '#f97316' }}>
                  {b.atk_name}
                </td>
                <td className="px-3 py-1.5 text-right">{fmtNum(b.atk_forces)}</td>
                <td className="px-3 py-1.5 text-right" style={{ color: '#f87171' }}>
                  {fmtNum(b.atk_losses_sum)}
                </td>
                <td className="px-3 py-1.5 whitespace-nowrap" style={{ color: '#60a5fa' }}>
                  {b.def_name}
                </td>
                <td className="px-3 py-1.5 text-right">{fmtNum(b.def_forces)}</td>
                <td className="px-3 py-1.5 text-right" style={{ color: '#818cf8' }}>
                  {fmtNum(b.def_losses_sum)}
                </td>
                <td className="px-3 py-1.5">
                  {b.winner === '—' ? (
                    <span style={{ color: 'var(--color-text-muted)' }}>—</span>
                  ) : (
                    <span style={{ color: b.winner === 'Attacker' ? '#f97316' : '#60a5fa', fontWeight: 500 }}>
                      {b.winner}
                    </span>
                  )}
                </td>
                <td className="px-3 py-1.5 text-right">
                  {b.war_score_delta != null ? (
                    <span style={{ color: b.war_score_delta >= 0 ? '#4ade80' : '#f87171' }}>
                      {b.war_score_delta >= 0 ? '+' : ''}{b.war_score_delta?.toFixed(1)}
                    </span>
                  ) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
