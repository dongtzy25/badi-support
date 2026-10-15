/* The only place that talks to the backend. Every request carries the current
 * identity as headers, and every error becomes an ApiError with a readable
 * message (plus per-field messages for validation errors). */

import type { Identity } from './identity'
import type {
  Agent,
  Message,
  MessageType,
  NewTicket,
  OrderSummary,
  Ticket,
  TicketDetail,
  TicketFilters,
  TicketList,
  TicketPatch,
} from './types'

export class ApiError extends Error {
  status: number
  /** e.g. { subject: "String should have at least 3 characters" } */
  fieldErrors: Record<string, string>

  constructor(status: number, message: string, fieldErrors: Record<string, string> = {}) {
    super(message)
    this.status = status
    this.fieldErrors = fieldErrors
  }
}

function identityHeaders(identity: Identity): Record<string, string> {
  return identity.role === 'agent'
    ? { 'X-Role': 'agent', 'X-Agent-Id': String(identity.agentId) }
    : { 'X-Role': 'customer', 'X-Customer-Email': identity.email }
}

async function request<T>(identity: Identity | null, path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(identity ? identityHeaders(identity) : {}),
        ...init.headers,
      },
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Is the API running on port 8000?')
  }

  if (response.ok) return (await response.json()) as T

  // Backend errors look like {"detail": "..."} or
  // {"detail": "Validation failed", "errors": [{"field": "subject", "message": "..."}]}
  let message = `Request failed (${response.status})`
  const fieldErrors: Record<string, string> = {}
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') message = body.detail
    for (const err of body.errors ?? []) {
      if (err.field) fieldErrors[err.field] = err.message
      else message = err.message
    }
  } catch {
    /* response was not JSON; keep the generic message */
  }
  throw new ApiError(response.status, message, fieldErrors)
}

function toQuery(filters: TicketFilters): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== '' && value !== false) params.set(key, String(value))
  }
  const query = params.toString()
  return query ? `?${query}` : ''
}

/** API client bound to one identity. */
export function apiFor(identity: Identity) {
  return {
    listTickets: (filters: TicketFilters) => request<TicketList>(identity, `/tickets${toQuery(filters)}`),
    getTicket: (id: number) => request<TicketDetail>(identity, `/tickets/${id}`),
    createTicket: (data: NewTicket) =>
      request<Ticket>(identity, '/tickets', { method: 'POST', body: JSON.stringify(data) }),
    updateTicket: (id: number, patch: TicketPatch) =>
      request<Ticket>(identity, `/tickets/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
    addMessage: (id: number, body: string, type: MessageType) =>
      request<Message>(identity, `/tickets/${id}/messages`, {
        method: 'POST',
        body: JSON.stringify({ body, type }),
      }),
    getOrder: (orderId: string) => request<OrderSummary>(identity, `/mock/orders/${encodeURIComponent(orderId)}`),
  }
}

export const listAgents = () => request<Agent[]>(null, '/agents')
