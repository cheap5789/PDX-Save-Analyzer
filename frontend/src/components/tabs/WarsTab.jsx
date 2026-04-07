/**
 * WarsTab — redesigned war analysis tab.
 *
 * Layout:
 *   Summary cards → sidebar (war list) + main detail
 *
 * Main detail tabs:
 *   Summary  — war header, participant panels, siege summary, score chart
 *   Forces   — stacked area chart (WarForcesChart)
 *   Battles  — sortable battle table (BattleTable)
 *   Scores   — participant combat score over time (ParticipantScoresChart)
 */

import { useState, useEffect, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { useApi } from '../../hooks/useApi'
import { useCountryNames } from '../../contexts/CountryNamesContext'
import { fmtCountry, euDateToNum, fmtYearTick } from '../../utils/formatters'
import { usePerfTracker } from '../../hooks/usePerfTracker'
import WarForcesChart from '../wars/WarForcesChart'
import BattleTable from '../wars/BattleTable'
import ParticipantScoresChart from '../wars/ParticipantScoresChart'

// ── Small helpers ─────────────────────────────────────────────────────────────

function TabButton({ id, label, active, badge, onClick }) {
  return (
    <button
      onClick={() => onClick(id)}
      className="px-4 py-2 text-xs font-medium transition-colors whitespace-nowrap relative"
      style={{
        borderBottom: active ? '2px solid var(--color-accent)' : '2px solid transparent',
        color: active ? 'var(--color-accent)' : 'var(--color-text-muted)',
        background: 'transparent',
      }}
    >
      {label}
      {badge != null && badge > 0 && (
        <span className="ml-1 px-1.5 py-0.5 rounded-full text-xs" style={{
          background: 'var(--color-surface-alt)',
          color: 'var(--color-text-muted)',
          fontSize: '10px',
        }}>{badge}</span>
      )}
    </button>
  )
}

function SummaryCard({ label, value }) {
  return (
    <div className="rounded-lg px-4 py-2" style={{ background: 'var(--color-surface)' }}>
      <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>{label}</p>
      <p className="text-lg font-semibold">{value}</p>
    </div>
  )
}

// ── Siege summary computation ─────────────────────────────────────────────────

function useSiegeSummary(sieges, attackers, defenders) {
  return useMemo(() => {
    if (!sieges.length) return null

    const atkIds = new Set(attackers.map(p => p.country_id).filter(Boolean))
    const defIds = new Set(defenders.map(p => p.country_id).filter(Boolean))

    const atkLaid = sieges.filter(s => (s.attacker_country_ids || []).some(id => atkIds.has(id)))
    const defLaid = sieges.filter(s => (s.attacker_country_ids || []).some(id => defIds.has(id)))

    const avgDays = (list) => {
      const valid = list.filter(s => s.last_duration != null && s.last_duration > 0)
      if (!valid.length) return null
      return Math.round(valid.reduce((s, x) => s + x.last_duration, 0) / valid.length)
    }

    return {
      atkCount: atkLaid.length,
      atkAvgDays: avgDays(atkLaid),
      defCount: defLaid.length,
      defAvgDays: avgDays(defLaid),
      allSieges: sieges,
    }
  }, [sieges, attackers, defenders])
}

// ── Siege summary panel ───────────────────────────────────────────────────────

function SiegePanel({ summary }) {
  const [open, setOpen] = useState(false)
  if (!summary) return null

  return (
    <div className="rounded-lg overflow-hidden" style={{ background: 'var(--color-surface)' }}>
      <div
        className="flex items-center justify-between px-4 py-2 cursor-pointer select-none"
        style={{ borderBottom: open ? '1px solid var(--color-border)' : 'none' }}
        onClick={() => setOpen(v => !v)}
      >
        <span className="text-xs font-medium">Sieges</span>
        <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          {open ? '▲' : '▼'}
        </span>
      </div>

      {/* Summary row: always visible */}
      <div className="grid grid-cols-2 divide-x text-xs" style={{ borderColor: 'var(--color-border)' }}>
        <div className="px-4 py-2" style={{ borderRight: '1px solid var(--color-border)' }}>
          <span style={{ color: '#f97316' }}>⚔ Attacker sieges: </span>
          <strong>{summary.atkCount}</strong>
          {summary.atkAvgDays != null && (
            <span style={{ color: 'var(--color-text-muted)' }}> · avg {summary.atkAvgDays}d</span>
          )}
        </div>
        <div className="px-4 py-2">
          <span style={{ color: '#60a5fa' }}>🛡 Defender sieges: </span>
          <strong>{summary.defCount}</strong>
          {summary.defAvgDays != null && (
            <span style={{ color: 'var(--color-text-muted)' }}> · avg {summary.defAvgDays}d</span>
          )}
        </div>
      </div>

      {/* Collapsible list */}
      {open && summary.allSieges.length > 0 && (
        <div className="max-h-56 overflow-y-auto" style={{ borderTop: '1px solid var(--color-border)' }}>
          <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--color-surface-alt)' }}>
                {['Location', 'First seen', 'Last seen', 'Duration', 'Status'].map(h => (
                  <th key={h} className="px-3 py-1.5 text-left font-medium"
                    style={{ color: 'var(--color-text-muted)', borderBottom: '1px solid var(--color-border)' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {summary.allSieges.map((s, i) => (
                <tr key={s.id} style={{
                  background: i % 2 === 0 ? 'transparent' : 'var(--color-surface-alt)',
                  borderBottom: '1px solid var(--color-border)',
                }}>
                  <td className="px-3 py-1">{s.location_id ?? '—'}</td>
                  <td className="px-3 py-1">{s.first_seen_date ?? '—'}</td>
                  <td className="px-3 py-1">{s.last_seen_date ?? '—'}</td>
                  <td className="px-3 py-1">{s.last_duration != null ? `${s.last_duration}d` : '—'}</td>
                  <td className="px-3 py-1">
                    <span style={{ color: s.is_active ? '#4ade80' : 'var(--color-text-muted)' }}>
                      {s.last_siege_status ?? (s.is_active ? 'Active' : 'Ended')}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function WarsTab({ status }) {
  const api = useApi()
  const { track, fmt } = usePerfTracker('wars')
  const nameMap = useCountryNames()

  // ── Top-level state ────────────────────────────────────────────────────
  const [wars, setWars]               = useState([])
  const [selectedWarId, setSelectedWarId] = useState(null)
  const [showEnded, setShowEnded]     = useState(false)
  const [activeTab, setActiveTab]     = useState('summary')

  // ── Per-war data ───────────────────────────────────────────────────────
  const [warSnapshots, setWarSnapshots] = useState([])
  const [participants, setParticipants] = useState([])
  const [battles, setBattles]           = useState([])
  const [sieges, setSieges]             = useState([])
  const [warLoading, setWarLoading]     = useState(false)

  const ptId = status?.playthrough_id

  // Load wars list
  useEffect(() => {
    if (!ptId) return
    let cancelled = false
    track('wars', api.getWars(ptId)).then(w => {
      if (cancelled) return
      setWars(w || [])
      const first = (w || []).find(x => !x.end_date) || (w || [])[0]
      if (first) setSelectedWarId(first.id)
    }).catch(() => {})
    return () => { cancelled = true }
  }, [ptId])

  // Load per-war data whenever selection changes
  useEffect(() => {
    if (!ptId || !selectedWarId) return
    let cancelled = false
    setWarLoading(true)
    setWarSnapshots([]); setParticipants([]); setBattles([]); setSieges([])

    Promise.all([
      api.getWarSnapshots(ptId, { war_id: selectedWarId }).catch(() => []),
      api.getWarParticipants(ptId, { war_id: selectedWarId }).catch(() => []),
      api.getBattles(ptId, { war_id: selectedWarId }).catch(() => []),
      api.getSieges(ptId, { war_id: selectedWarId }).catch(() => []),
    ]).then(([snaps, parts, bats, sieList]) => {
      if (cancelled) return
      setWarSnapshots(snaps || [])
      setParticipants(parts || [])
      setBattles(bats || [])
      setSieges(sieList || [])
    }).finally(() => { if (!cancelled) setWarLoading(false) })

    return () => { cancelled = true }
  }, [ptId, selectedWarId])

  // ── Derived values ─────────────────────────────────────────────────────
  const filteredWars = useMemo(
    () => showEnded ? wars : wars.filter(w => !w.end_date),
    [wars, showEnded],
  )

  const selectedWar = wars.find(w => w.id === selectedWarId) ?? null
  const attackers   = participants.filter(p => p.side === 'Attacker')
  const defenders   = participants.filter(p => p.side === 'Defender')

  const siegeSummary = useSiegeSummary(sieges, attackers, defenders)

  // War score chart data
  const scoreData = useMemo(() => fmt('score', () =>
    warSnapshots.map(s => ({
      date: s.game_date,
      dateNum: euDateToNum(s.game_date),
      Attacker: s.attacker_score ?? 0,
      Defender: s.defender_score ?? 0,
      Net: s.net_war_score ?? 0,
    }))
  ), [warSnapshots])

  // ── Empty state ────────────────────────────────────────────────────────
  if (!ptId) {
    return (
      <div className="p-6 text-sm" style={{ color: 'var(--color-text-muted)' }}>
        No playthrough loaded. Start the pipeline or load a saved playthrough.
      </div>
    )
  }

  return (
    <div className="p-6 space-y-4">
      {/* Summary cards */}
      <div className="flex flex-wrap gap-3">
        <SummaryCard label="Total wars"    value={wars.length} />
        <SummaryCard label="Active"        value={wars.filter(w => !w.end_date).length} />
        <SummaryCard label="Ended"         value={wars.filter(w =>  w.end_date).length} />
      </div>

      <div className="flex gap-4">
        {/* ── War list sidebar ──────────────────────────────────────────── */}
        <div className="w-72 shrink-0 rounded-lg overflow-hidden" style={{ background: 'var(--color-surface)' }}>
          <div className="flex items-center justify-between px-3 py-2"
            style={{ background: 'var(--color-surface-alt)', borderBottom: '1px solid var(--color-border)' }}>
            <span className="text-xs font-medium">Wars</span>
            <button
              onClick={() => setShowEnded(v => !v)}
              className="text-xs px-2 py-0.5 rounded"
              style={{
                background: showEnded ? 'var(--color-accent)' : 'transparent',
                color: showEnded ? '#fff' : 'var(--color-text-muted)',
              }}
            >
              {showEnded ? 'All' : 'Active only'}
            </button>
          </div>

          <div className="overflow-y-auto" style={{ maxHeight: 'calc(100vh - 260px)' }}>
            {filteredWars.map(w => (
              <button
                key={w.id}
                onClick={() => { setSelectedWarId(w.id); setActiveTab('summary') }}
                className="w-full text-left px-3 py-2 text-xs transition-colors"
                style={{
                  background: selectedWarId === w.id ? 'var(--color-surface-alt)' : 'transparent',
                  borderBottom: '1px solid var(--color-border)',
                  borderLeft: selectedWarId === w.id ? '2px solid var(--color-accent)' : '2px solid transparent',
                }}
              >
                <p className="font-medium truncate" style={{ color: 'var(--color-text)' }}>
                  {w.name_display || w.name_key || `War #${w.id}`}
                </p>
                <p style={{ color: 'var(--color-text-muted)' }}>
                  {w.start_date}{w.end_date ? ` — ${w.end_date}` : ' (active)'}
                </p>
                {w.casus_belli && (
                  <p className="truncate capitalize" style={{ color: 'var(--color-text-muted)' }}>
                    {w.casus_belli.replace(/^cb_/, '').replace(/_/g, ' ')}
                  </p>
                )}
              </button>
            ))}
            {filteredWars.length === 0 && (
              <p className="text-xs px-3 py-4 text-center" style={{ color: 'var(--color-text-muted)' }}>
                {wars.length === 0 ? 'Loading…' : 'No wars found'}
              </p>
            )}
          </div>
        </div>

        {/* ── War detail (main area) ────────────────────────────────────── */}
        <div className="flex-1 min-w-0 space-y-3">
          {!selectedWar ? (
            <div className="rounded-lg p-8 text-center text-sm"
              style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}>
              Select a war from the list to view details.
            </div>
          ) : (
            <>
              {/* War info header */}
              <div className="rounded-lg p-4" style={{ background: 'var(--color-surface)' }}>
                <div className="flex items-start justify-between gap-2">
                  <h3 className="text-sm font-semibold">
                    {selectedWar.name_display || selectedWar.name_key || `War #${selectedWar.id}`}
                  </h3>
                  {!selectedWar.end_date && (
                    <span className="text-xs px-2 py-0.5 rounded-full shrink-0"
                      style={{ background: '#16a34a22', color: '#4ade80' }}>Active</span>
                  )}
                </div>
                <div className="flex flex-wrap gap-4 mt-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  <span>Started: {selectedWar.start_date}</span>
                  {selectedWar.end_date && <span>Ended: {selectedWar.end_date}</span>}
                  {selectedWar.casus_belli && (
                    <span className="capitalize">
                      CB: {selectedWar.casus_belli.replace(/^cb_/, '').replace(/_/g, ' ')}
                    </span>
                  )}
                  {selectedWar.goal_type && (
                    <span className="capitalize">
                      Goal: {selectedWar.goal_type.replace(/_/g, ' ')}
                    </span>
                  )}
                </div>
              </div>

              {/* Tab bar */}
              <div className="flex border-b" style={{ borderColor: 'var(--color-border)' }}>
                <TabButton id="summary"  label="Summary"  active={activeTab === 'summary'}  onClick={setActiveTab} />
                <TabButton id="forces"   label="Forces"   active={activeTab === 'forces'}   onClick={setActiveTab} />
                <TabButton id="battles"  label="Battles"  active={activeTab === 'battles'}  badge={battles.length} onClick={setActiveTab} />
                <TabButton id="scores"   label="Scores"   active={activeTab === 'scores'}   onClick={setActiveTab} />
              </div>

              {/* ── Summary tab ─────────────────────────────────────────── */}
              {activeTab === 'summary' && (
                <div className="space-y-3">
                  {/* Participant panels */}
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { side: 'Attackers', list: attackers, bg: '#ef444420', color: '#ef4444' },
                      { side: 'Defenders', list: defenders, bg: '#3b82f620', color: '#3b82f6' },
                    ].map(({ side, list, bg, color }) => (
                      <div key={side} className="rounded-lg overflow-hidden" style={{ background: 'var(--color-surface)' }}>
                        <div className="px-3 py-2 text-xs font-medium" style={{ background: bg, color }}>
                          {side} ({list.length})
                        </div>
                        <div className="max-h-40 overflow-y-auto">
                          {list.map(p => (
                            <div key={p.id} className="px-3 py-1.5 text-xs flex justify-between"
                              style={{ borderBottom: '1px solid var(--color-border)' }}>
                              <span>{p.country_tag ? fmtCountry(p.country_tag, nameMap, { showPrev: false }) : `#${p.country_id}`}</span>
                              <span style={{ color: 'var(--color-text-muted)' }}>
                                {p.join_reason}{p.status !== 'Active' ? ` (${p.status})` : ''}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Siege summary */}
                  <SiegePanel summary={siegeSummary} />

                  {/* War score chart */}
                  {scoreData.length > 0 ? (
                    <div className="rounded-lg p-4" style={{ background: 'var(--color-surface)' }}>
                      <h4 className="text-xs font-medium mb-3" style={{ color: 'var(--color-text-muted)' }}>
                        War Score
                      </h4>
                      <ResponsiveContainer width="100%" height={240}>
                        <LineChart data={scoreData} margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                          <XAxis
                            dataKey="dateNum" type="number" scale="linear"
                            domain={['dataMin', 'dataMax']} tickFormatter={fmtYearTick}
                            tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }}
                            stroke="var(--color-border)"
                          />
                          <YAxis tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} stroke="var(--color-border)" width={36} />
                          <Tooltip
                            contentStyle={{ background: 'var(--color-surface-alt)', border: '1px solid var(--color-border)', borderRadius: '6px', color: 'var(--color-text)', fontSize: '12px' }}
                            labelFormatter={(_v, p) => p?.[0]?.payload?.date ?? ''}
                          />
                          <Legend wrapperStyle={{ fontSize: '12px', color: 'var(--color-text-muted)' }} />
                          <Line type="monotone" dataKey="Attacker" stroke="#ef4444" strokeWidth={2} dot={false} />
                          <Line type="monotone" dataKey="Defender" stroke="#3b82f6" strokeWidth={2} dot={false} />
                          <Line type="monotone" dataKey="Net" stroke="#f59e0b" strokeWidth={2} dot={false} strokeDasharray="5 5" />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <div className="rounded-lg p-6 text-center text-xs"
                      style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}>
                      No score snapshots recorded yet.
                    </div>
                  )}
                </div>
              )}

              {/* ── Forces tab ──────────────────────────────────────────── */}
              {activeTab === 'forces' && (
                <WarForcesChart
                  ptId={ptId}
                  war={selectedWar}
                  participants={participants}
                />
              )}

              {/* ── Battles tab ─────────────────────────────────────────── */}
              {activeTab === 'battles' && (
                <BattleTable
                  battles={battles}
                  participants={participants}
                  nameMap={nameMap}
                />
              )}

              {/* ── Scores tab ───────────────────────────────────────────── */}
              {activeTab === 'scores' && (
                <ParticipantScoresChart
                  ptId={ptId}
                  warId={selectedWarId}
                  participants={participants}
                  nameMap={nameMap}
                />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
