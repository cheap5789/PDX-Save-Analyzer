import { useState, useEffect, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { useApi } from '../../hooks/useApi'

const SIDE_COLORS = { Attacker: '#ef4444', Defender: '#3b82f6' }

export default function WarsTab({ status }) {
  const api = useApi()
  const [wars, setWars] = useState([])
  const [selectedWarId, setSelectedWarId] = useState(null)
  const [warSnapshots, setWarSnapshots] = useState([])
  const [participants, setParticipants] = useState([])
  const [showEnded, setShowEnded] = useState(false)

  const ptId = status?.playthrough_id

  // Load war list
  useEffect(() => {
    if (!ptId) return
    let cancelled = false
    api.getWars(ptId).then((w) => {
      if (cancelled) return
      setWars(w)
      // Auto-select first active war
      const active = w.filter((war) => !war.end_date)
      if (active.length > 0) setSelectedWarId(active[0].id)
      else if (w.length > 0) setSelectedWarId(w[0].id)
    }).catch(() => {})
    return () => { cancelled = true }
  }, [ptId])

  // Load snapshots + participants when war is selected
  useEffect(() => {
    if (!ptId || !selectedWarId) return
    Promise.all([
      api.getWarSnapshots(ptId, { war_id: selectedWarId }).catch(() => []),
      api.getWarParticipants(ptId, { war_id: selectedWarId }).catch(() => []),
    ]).then(([snaps, parts]) => {
      setWarSnapshots(snaps)
      setParticipants(parts)
    })
  }, [ptId, selectedWarId])

  // Filter wars by active/ended
  const filteredWars = useMemo(() => {
    if (showEnded) return wars
    return wars.filter((w) => !w.end_date)
  }, [wars, showEnded])

  // War score chart data
  const chartData = useMemo(() => {
    return warSnapshots.map((s) => ({
      date: s.game_date,
      'Attacker Score': s.attacker_score || 0,
      'Defender Score': s.defender_score || 0,
      'Net Score': s.net_war_score || 0,
    }))
  }, [warSnapshots])

  // Current selected war
  const selectedWar = wars.find((w) => w.id === selectedWarId)

  // Split participants by side
  const attackers = participants.filter((p) => p.side === 'Attacker')
  const defenders = participants.filter((p) => p.side === 'Defender')

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
      <div className="flex flex-wrap gap-4 items-center">
        <div className="rounded-lg px-4 py-2" style={{ background: 'var(--color-surface)' }}>
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Total wars</span>
          <p className="text-lg font-semibold">{wars.length}</p>
        </div>
        <div className="rounded-lg px-4 py-2" style={{ background: 'var(--color-surface)' }}>
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Active</span>
          <p className="text-lg font-semibold">{wars.filter((w) => !w.end_date).length}</p>
        </div>
        <div className="rounded-lg px-4 py-2" style={{ background: 'var(--color-surface)' }}>
          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Ended</span>
          <p className="text-lg font-semibold">{wars.filter((w) => w.end_date).length}</p>
        </div>
      </div>

      <div className="flex gap-4">
        {/* War list (sidebar) */}
        <div className="w-72 shrink-0 rounded-lg overflow-hidden" style={{ background: 'var(--color-surface)' }}>
          <div className="flex items-center justify-between px-3 py-2" style={{ background: 'var(--color-surface-alt)' }}>
            <span className="text-xs font-medium">Wars</span>
            <button
              onClick={() => setShowEnded(!showEnded)}
              className="text-xs px-2 py-0.5 rounded"
              style={{
                background: showEnded ? 'var(--color-accent)' : 'transparent',
                color: showEnded ? '#fff' : 'var(--color-text-muted)',
              }}
            >
              {showEnded ? 'All' : 'Active only'}
            </button>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {filteredWars.map((w) => (
              <button
                key={w.id}
                onClick={() => setSelectedWarId(w.id)}
                className="w-full text-left px-3 py-2 text-xs transition-colors"
                style={{
                  background: selectedWarId === w.id ? 'var(--color-surface-alt)' : 'transparent',
                  borderBottom: '1px solid var(--color-border)',
                }}
              >
                <p className="font-medium truncate" style={{ color: 'var(--color-text)' }}>
                  {w.name_display || w.name_key || `War #${w.id}`}
                </p>
                <p style={{ color: 'var(--color-text-muted)' }}>
                  {w.start_date}{w.end_date ? ` — ${w.end_date}` : ' (active)'}
                </p>
                {w.casus_belli && (
                  <p className="capitalize" style={{ color: 'var(--color-text-muted)' }}>
                    {w.casus_belli.replace(/^cb_/, '').replace(/_/g, ' ')}
                  </p>
                )}
              </button>
            ))}
            {filteredWars.length === 0 && (
              <p className="text-xs px-3 py-4 text-center" style={{ color: 'var(--color-text-muted)' }}>
                {wars.length === 0 ? 'Loading...' : 'No wars found'}
              </p>
            )}
          </div>
        </div>

        {/* War detail (main area) */}
        <div className="flex-1 space-y-4">
          {selectedWar ? (
            <>
              {/* War info header */}
              <div className="rounded-lg p-4" style={{ background: 'var(--color-surface)' }}>
                <h3 className="text-sm font-semibold">
                  {selectedWar.name_display || selectedWar.name_key || `War #${selectedWar.id}`}
                </h3>
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

              {/* Participants */}
              <div className="grid grid-cols-2 gap-4">
                {/* Attackers */}
                <div className="rounded-lg overflow-hidden" style={{ background: 'var(--color-surface)' }}>
                  <div className="px-3 py-2 text-xs font-medium" style={{ background: '#ef444420', color: '#ef4444' }}>
                    Attackers ({attackers.length})
                  </div>
                  <div className="max-h-48 overflow-y-auto">
                    {attackers.map((p) => (
                      <div key={p.id} className="px-3 py-1.5 text-xs flex justify-between"
                        style={{ borderBottom: '1px solid var(--color-border)' }}>
                        <span>{p.country_tag || `#${p.country_id}`}</span>
                        <span style={{ color: 'var(--color-text-muted)' }}>
                          {p.join_reason}{p.status !== 'Active' ? ` (${p.status})` : ''}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Defenders */}
                <div className="rounded-lg overflow-hidden" style={{ background: 'var(--color-surface)' }}>
                  <div className="px-3 py-2 text-xs font-medium" style={{ background: '#3b82f620', color: '#3b82f6' }}>
                    Defenders ({defenders.length})
                  </div>
                  <div className="max-h-48 overflow-y-auto">
                    {defenders.map((p) => (
                      <div key={p.id} className="px-3 py-1.5 text-xs flex justify-between"
                        style={{ borderBottom: '1px solid var(--color-border)' }}>
                        <span>{p.country_tag || `#${p.country_id}`}</span>
                        <span style={{ color: 'var(--color-text-muted)' }}>
                          {p.join_reason}{p.status !== 'Active' ? ` (${p.status})` : ''}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Score chart */}
              {chartData.length > 0 ? (
                <div className="rounded-lg p-4" style={{ background: 'var(--color-surface)' }}>
                  <h3 className="text-sm font-medium mb-3">War Score Over Time</h3>
                  <ResponsiveContainer width="100%" height={300}>
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
                      <Line type="monotone" dataKey="Attacker Score" stroke="#ef4444" strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="Defender Score" stroke="#3b82f6" strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="Net Score" stroke="#f59e0b" strokeWidth={2} dot={false} strokeDasharray="5 5" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="rounded-lg p-6 text-center text-xs"
                  style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}>
                  No score snapshots available for this war yet.
                </div>
              )}
            </>
          ) : (
            <div className="rounded-lg p-8 text-center text-sm"
              style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}>
              Select a war from the list to view details.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
