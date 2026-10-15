/* Real-time updates for one ticket.
 *
 * Opens a WebSocket to /ws/tickets/{id}. The server only sends a small signal
 * like {"type": "message.created"}; we then tell React Query that the ticket
 * data is stale, and it re-fetches it over REST. That way the REST endpoint
 * stays the single place that decides what this user is allowed to see.
 * If the connection drops, we reconnect with a growing delay (1s, 2s, 4s... max 10s).
 */

import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import type { Identity } from './identity'

export type LiveStatus = 'connecting' | 'live' | 'offline'

export function useTicketLive(ticketId: number, identity: Identity, enabled = true): LiveStatus {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<LiveStatus>('connecting')

  const who =
    identity.role === 'agent'
      ? `role=agent&agent_id=${identity.agentId}`
      : `role=customer&email=${encodeURIComponent(identity.email)}`

  useEffect(() => {
    if (!enabled) return // e.g. the ticket doesn't exist or isn't ours: don't connect
    let socket: WebSocket | null = null
    let retryTimer: ReturnType<typeof setTimeout> | undefined
    let attempt = 0
    let stopped = false

    const connect = () => {
      setStatus('connecting')
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      socket = new WebSocket(`${protocol}://${window.location.host}/ws/tickets/${ticketId}?${who}`)

      socket.onopen = () => {
        attempt = 0
        setStatus('live')
        // Catch up on anything that happened while we were disconnected.
        queryClient.invalidateQueries({ queryKey: ['ticket'] })
      }
      socket.onmessage = () => {
        queryClient.invalidateQueries({ queryKey: ['ticket'] })
        queryClient.invalidateQueries({ queryKey: ['tickets'] })
      }
      socket.onclose = () => {
        if (stopped) return
        setStatus('offline')
        const delay = Math.min(1000 * 2 ** attempt, 10_000)
        attempt += 1
        retryTimer = setTimeout(connect, delay)
      }
    }

    connect()
    return () => {
      // Page closed or ticket/identity changed: stop for good.
      stopped = true
      clearTimeout(retryTimer)
      socket?.close()
    }
  }, [ticketId, who, queryClient, enabled])

  return status
}
