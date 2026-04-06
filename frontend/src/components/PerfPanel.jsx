/**
 * PerfPanel — right-side performance monitoring panel.
 *
 * Shows one block per tab session (most recent first), each listing the
 * individual API requests with stage, row count, and timings.
 *
 * Stages:
 *   fetching  → query in flight
 *   received  → response arrived, raw data in memory
 *   ready     → formatted / rendered (or: data used directly without a format step)
 *   error     → fetch or format threw
 */

import { usePerfContext } from '../contexts/PerfContext'

// ─── Stage display config ─────────────────────────────────────────────────────

const STAGE_META = {
  fetching:  { label: 'querying',   color: 'var(--color-accent)',       dot: true  },
  received:  { label: 'formatting', color: '#f59e0b',                   dot: true  },
  ready:     { label: 'ready',      color: 'var(--color-success)',       dot: false },
  error:     { label: 'error',      color: 'var(--color-danger)',        dot: false },
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function ms(n) {
  if (n == null) return null
  if (n >= 1000) return `${(n / 1000).toFixed(1)}s`
  return `${n}ms`
}

function fmtRows(n) {
  if (n == null) return null
  return n.toLocaleString()
}

// Total elapsed for a session (sum of slowest parallel request)
function sessionTotal(session) {
  let max = 0
  for (const r of session.requests) {
    const t = (r.fetchMs ?? 0) + (r.formatMs ?? 0)
    if (t > max) max = t
  }
  return max || null
}

function allReady(session) {
  return (
    session.requests.length > 0 &&
    session.requests.every((r) => r.stage === 'ready' || r.stage === 'error')
  )
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function Spinner() {
  return (
    <span
      style={{
        display: 'inline-block',
        width: 8,
        height: 8,
        borderRadius: '50%',
        border: '1.5px solid currentColor',
        borderTopColor: 'transparent',
        animation: 'perf-spin 0.7s linear infinite',
        flexShrink: 0,
      }}
    />
  )
}

function StageDot({ stage }) {
  const meta = STAGE_META[stage] ?? STAGE_META.ready
  return (
    <span style={{ color: meta.color, display: 'flex', alignItems: 'center', width: 10, flexShrink: 0 }}>
      {meta.dot ? <Spinner /> : (stage === 'error' ? '✕' : '✓')}
    </span>
  )
}

function RequestRow({ req }) {
  const meta = STAGE_META[req.stage] ?? STAGE_META.ready
  const fetchTime = ms(req.fetchMs)
  const fmtTime = req.formatMs != null && req.formatMs > 0 ? ms(req.formatMs) : null
  const rows = fmtRows(req.rowCount)

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '3px 0',
        fontSize: 11,
        lineHeight: 1.4,
      }}
    >
      <StageDot stage={req.stage} />

      {/* Label */}
      <span
        style={{
          flex: 1,
          color: req.stage === 'error' ? meta.color : 'var(--color-text)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          fontFamily: 'var(--font-mono, monospace)',
          fontSize: 10.5,
        }}
      >
        {req.label}
        {req.stage === 'error' && req.error && (
          <span style={{ color: meta.color, marginLeft: 4 }}>— {req.error}</span>
        )}
      </span>

      {/* Row count */}
      {rows != null && (
        <span style={{ color: 'var(--color-text-muted)', fontSize: 10, flexShrink: 0 }}>
          {rows}
        </span>
      )}

      {/* Timings */}
      <div style={{ textAlign: 'right', flexShrink: 0, minWidth: 48 }}>
        {fetchTime && (
          <span
            style={{
              color: req.fetchMs > 2000
                ? 'var(--color-danger)'
                : req.fetchMs > 500
                ? '#f59e0b'
                : 'var(--color-text-muted)',
              fontSize: 10,
            }}
          >
            {fetchTime}
          </span>
        )}
        {fmtTime && (
          <span style={{ color: 'var(--color-text-muted)', fontSize: 10, marginLeft: 2 }}>
            +{fmtTime}
          </span>
        )}
        {req.stage === 'fetching' && (
          <span style={{ color: 'var(--color-accent)', fontSize: 10 }}>…</span>
        )}
      </div>
    </div>
  )
}

function SessionBlock({ session, isFirst }) {
  const total = sessionTotal(session)
  const done = allReady(session)
  const pending = session.requests.some((r) => r.stage === 'fetching' || r.stage === 'received')

  return (
    <div
      style={{
        padding: '10px 14px',
        borderBottom: '1px solid var(--color-border)',
        opacity: !isFirst && done ? 0.65 : 1,
        transition: 'opacity 0.3s',
      }}
    >
      {/* Session header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: session.requests.length ? 6 : 0,
        }}
      >
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: 'var(--color-text)',
            textTransform: 'capitalize',
            letterSpacing: '0.02em',
          }}
        >
          {session.tab}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {pending && (
            <span style={{ color: 'var(--color-accent)', fontSize: 10 }}>
              <Spinner />
            </span>
          )}
          {total != null && (
            <span
              style={{
                fontSize: 10,
                color: done ? 'var(--color-text-muted)' : 'var(--color-accent)',
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {ms(total)}
            </span>
          )}
        </div>
      </div>

      {/* Request rows */}
      {session.requests.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {session.requests.map((r) => (
            <RequestRow key={r.label} req={r} />
          ))}
        </div>
      )}

      {session.requests.length === 0 && (
        <div style={{ fontSize: 10, color: 'var(--color-text-muted)', fontStyle: 'italic' }}>
          no tracked requests
        </div>
      )}
    </div>
  )
}

// ─── Main panel ───────────────────────────────────────────────────────────────

export default function PerfPanel({ onClose }) {
  const ctx = usePerfContext()
  const { sessions, clear } = ctx ?? {}

  return (
    <>
      {/* Keyframe for spinner — injected once */}
      <style>{`
        @keyframes perf-spin {
          to { transform: rotate(360deg); }
        }
      `}</style>

      <div
        style={{
          width: 260,
          minWidth: 260,
          display: 'flex',
          flexDirection: 'column',
          borderLeft: '1px solid var(--color-border)',
          background: 'var(--color-surface)',
          overflow: 'hidden',
          height: '100%',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '8px 14px',
            borderBottom: '1px solid var(--color-border)',
            flexShrink: 0,
          }}
        >
          <span
            style={{
              fontSize: 10,
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              color: 'var(--color-text-muted)',
            }}
          >
            Performance
          </span>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {sessions?.length > 0 && (
              <button
                onClick={clear}
                title="Clear history"
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--color-text-muted)',
                  fontSize: 10,
                  padding: '1px 4px',
                  borderRadius: 3,
                }}
              >
                clear
              </button>
            )}
            <button
              onClick={onClose}
              title="Close panel"
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: 'var(--color-text-muted)',
                fontSize: 16,
                lineHeight: 1,
                padding: '0 2px',
              }}
            >
              ×
            </button>
          </div>
        </div>

        {/* Legend */}
        <div
          style={{
            display: 'flex',
            gap: 10,
            padding: '5px 14px',
            borderBottom: '1px solid var(--color-border)',
            flexShrink: 0,
          }}
        >
          {Object.entries(STAGE_META).map(([stage, meta]) => (
            <span
              key={stage}
              style={{ fontSize: 9.5, color: meta.color, display: 'flex', alignItems: 'center', gap: 3 }}
            >
              <span style={{ fontSize: 8 }}>●</span> {meta.label}
            </span>
          ))}
        </div>

        {/* Column headers */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            padding: '4px 14px',
            borderBottom: '1px solid var(--color-border)',
            flexShrink: 0,
          }}
        >
          <span style={{ fontSize: 9, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            request
          </span>
          <span style={{ fontSize: 9, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            rows · fetch · fmt
          </span>
        </div>

        {/* Session list */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {(!sessions || sessions.length === 0) && (
            <div
              style={{
                padding: '20px 14px',
                fontSize: 11,
                color: 'var(--color-text-muted)',
                fontStyle: 'italic',
                textAlign: 'center',
              }}
            >
              Navigate to a tab to see load timings.
            </div>
          )}
          {sessions?.map((session, i) => (
            <SessionBlock key={session.sessionId} session={session} isFirst={i === 0} />
          ))}
        </div>
      </div>
    </>
  )
}
