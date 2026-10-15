/* Small shared UI pieces: badges, the loading/empty/error states, and the demo identity switcher. */

import { useQuery } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { ApiError, listAgents } from './api'
import { useIdentity } from './identity'
import { label, type TicketPriority, type TicketStatus } from './types'

export function StatusBadge({ status }: { status: TicketStatus }) {
  return <span className={`badge status-${status.toLowerCase()}`}>{label(status)}</span>
}

export function PriorityBadge({ priority }: { priority: TicketPriority }) {
  return <span className={`badge priority-${priority.toLowerCase()}`}>{label(priority)}</span>
}

export function Loading({ text = 'Loading…' }: { text?: string }) {
  return (
    <div className="state" role="status">
      <span className="spinner" aria-hidden="true" /> {text}
    </div>
  )
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof ApiError || error instanceof Error ? error.message : 'Something went wrong.'
  return (
    <div className="state state-error" role="alert">
      <p>{message}</p>
      {onRetry && (
        <button type="button" className="btn" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  )
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state">
      <p className="state-title">{title}</p>
      {children}
    </div>
  )
}

const timeFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })
export const formatTime = (iso: string) => timeFormat.format(new Date(iso))

/** Demo-only "who am I" picker. A real app would have a login screen instead. */
export function IdentitySwitcher() {
  const { identity, setIdentity } = useIdentity()
  const agents = useQuery({ queryKey: ['agents'], queryFn: listAgents })
  const [email, setEmail] = useState(identity.role === 'customer' ? identity.email : 'customer@example.com')

  const value = identity.role === 'agent' ? `agent:${identity.agentId}` : 'customer'

  const onRoleChange = (next: string) => {
    if (next === 'customer') setIdentity({ role: 'customer', email: email.trim().toLowerCase() })
    else setIdentity({ role: 'agent', agentId: Number(next.split(':')[1]) })
  }

  const commitEmail = () => {
    const clean = email.trim().toLowerCase()
    if (clean && identity.role === 'customer' && clean !== identity.email) setIdentity({ role: 'customer', email: clean })
  }

  return (
    <div className="identity">
      <label htmlFor="identity-role">Viewing as</label>
      <select id="identity-role" value={value} onChange={(e) => onRoleChange(e.target.value)}>
        <optgroup label="Support agent">
          {(agents.data ?? [{ id: 1, name: 'Agent #1', email: '' }]).map((a) => (
            <option key={a.id} value={`agent:${a.id}`}>
              Agent: {a.name}
            </option>
          ))}
        </optgroup>
        <option value="customer">Customer</option>
      </select>
      {identity.role === 'customer' && (
        <input
          aria-label="Customer email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onBlur={commitEmail}
          onKeyDown={(e) => e.key === 'Enter' && commitEmail()}
        />
      )}
    </div>
  )
}
