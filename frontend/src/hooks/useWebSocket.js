import { useEffect, useRef, useCallback, useState } from 'react'

/**
 * useWebSocket — connects to /ws, auto-reconnects, parses JSON messages.
 *
 * Returns:
 *   connected  — boolean
 *   lastMessage — most recent parsed WsMessage
 *   snapshots  — array of all snapshot messages received this session
 *   events     — array of all event messages received this session
 *   status     — latest status object (sent on connect and on changes)
 */
export function useWebSocket(enabled = true) {
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)
  const [connected, setConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState(null)
  const [status, setStatus] = useState(null)
  const [snapshots, setSnapshots] = useState([])
  const [events, setEvents] = useState([])
  const [backfillProgress, setBackfillProgress] = useState(null)

  const connect = useCallback(() => {
    if (!enabled) return
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current)
        reconnectTimer.current = null
      }
    }

    ws.onclose = () => {
      setConnected(false)
      wsRef.current = null
      // auto-reconnect after 2s
      reconnectTimer.current = setTimeout(connect, 2000)
    }

    ws.onerror = () => {
      ws.close()
    }

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data)
        setLastMessage(msg)

        switch (msg.type) {
          case 'status':
            setStatus(msg.data)
            break
          case 'snapshot':
            setSnapshots((prev) => [...prev, msg.data])
            break
          case 'event':
            setEvents((prev) => [...prev, msg.data])
            break
          case 'events':
            // batch of events
            if (Array.isArray(msg.data)) {
              setEvents((prev) => [...prev, ...msg.data])
            }
            break
          case 'backfill_progress':
            setBackfillProgress(msg.data)
            break
        }
      } catch {
        // ignore malformed messages
      }
    }
  }, [enabled])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      if (wsRef.current) {
        wsRef.current.onclose = null  // prevent reconnect on intentional close
        wsRef.current.close()
      }
    }
  }, [connect])

  const clearHistory = useCallback(() => {
    setSnapshots([])
    setEvents([])
  }, [])

  return { connected, lastMessage, status, snapshots, events, backfillProgress, clearHistory }
}
