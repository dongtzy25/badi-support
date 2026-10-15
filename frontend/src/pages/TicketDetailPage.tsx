import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, apiFor, listAgents } from '../api'
import { ErrorBox, Loading, PriorityBadge, StatusBadge, formatTime } from '../components'
import { identityKey, useIdentity, type Identity } from '../identity'
import {
  PRIORITIES,
  STATUSES,
  label,
  type MessageType,
  type TicketDetail,
  type TicketEvent,
  type TicketPatch,
} from '../types'
import { useTicketLive, type LiveStatus } from '../useTicketLive'

export default function TicketDetailPage() {
  const ticketId = Number(useParams().id)
  const { identity } = useIdentity()
  const ticket = useQuery({
    queryKey: ['ticket', identityKey(identity), ticketId],
    queryFn: () => apiFor(identity).getTicket(ticketId),
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
  })
  const live = useTicketLive(ticketId, identity, ticket.isSuccess)

  if (ticket.isPending) return <Loading text="Loading ticket…" />
  if (ticket.isError) {
    return (
      <section>
        <Link to="/tickets" className="back">← Back to tickets</Link>
        <ErrorBox error={ticket.error} onRetry={() => ticket.refetch()} />
      </section>
    )
  }

  const t = ticket.data
  const isAgent = identity.role === 'agent'

  return (
    <section>
      <Link to="/tickets" className="back">← Back to tickets</Link>
      <header className="ticket-header">
        <div>
          <p className="mono muted">{t.number} · {label(t.category)} · opened {formatTime(t.created_at)}</p>
          <h1>{t.subject}</h1>
          <div className="badges">
            <StatusBadge status={t.status} />
            <PriorityBadge priority={t.priority} />
            <LiveIndicator status={live} />
          </div>
        </div>
      </header>

      <div className="detail-layout">
        <div className="main-col">
          <CustomerHint ticket={t} isAgent={isAgent} />
          <Thread ticket={t} identity={identity} />
          <Composer ticket={t} identity={identity} />
        </div>

        <aside className="side-col">
          {isAgent && <TicketControls ticket={t} identity={identity} />}
          <div className="card">
            <h2>Details</h2>
            <dl className="facts">
              <dt>Customer</dt><dd>{t.customer_email}</dd>
              <dt>Assignee</dt><dd>{t.assignee?.name ?? 'Unassigned'}</dd>
              <dt>Last update</dt><dd>{formatTime(t.updated_at)}</dd>
            </dl>
          </div>
          {t.order_id && <OrderCard orderId={t.order_id} identity={identity} />}
          {isAgent && <History events={t.events} />}
        </aside>
      </div>
    </section>
  )
}

function LiveIndicator({ status }: { status: LiveStatus }) {
  const text = { live: 'Live', connecting: 'Connecting…', offline: 'Offline, reconnecting…' }[status]
  return (
    <span className={`live live-${status}`} title="New replies appear automatically">
      <span className="dot" aria-hidden="true" /> {text}
    </span>
  )
}

/** Tells the customer what is expected of them right now. */
function CustomerHint({ ticket, isAgent }: { ticket: TicketDetail; isAgent: boolean }) {
  if (isAgent) return null
  const hints: Partial<Record<TicketDetail['status'], string>> = {
    WAITING_FOR_CUSTOMER: 'Our support team is waiting for your reply.',
    WAITING_FOR_PROVIDER: "We've contacted our network partner and will update you here.",
    RESOLVED: 'We marked this as resolved. If the problem continues, just reply and we will pick it up again.',
    CLOSED: 'This request is closed. Please open a new ticket if you need more help.',
  }
  const hint = hints[ticket.status]
  return hint ? <p className="hint">{hint}</p> : null
}

function Thread({ ticket, identity }: { ticket: TicketDetail; identity: Identity }) {
  const isAgent = identity.role === 'agent'
  const endRef = useRef<HTMLDivElement>(null)

  // Scroll to the newest message when one arrives.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [ticket.messages.length])

  const customerName = isAgent ? ticket.customer_email : 'You'

  return (
    <div className="card thread" aria-live="polite">
      <h2>Conversation</h2>
      {/* The description is the customer's opening message. */}
      <article className="msg msg-customer">
        <header><strong>{customerName}</strong> <time>{formatTime(ticket.created_at)}</time></header>
        <p>{ticket.description}</p>
      </article>

      {ticket.messages.map((m) => {
        const internal = m.type === 'INTERNAL'
        const fromAgent = m.sender_type === 'AGENT'
        const who = fromAgent
          ? isAgent ? (m.sender_agent?.name ?? 'Support') : `Badi Support${m.sender_agent ? ` (${m.sender_agent.name})` : ''}`
          : customerName
        return (
          <article key={m.id} className={`msg ${internal ? 'msg-internal' : fromAgent ? 'msg-agent' : 'msg-customer'}`}>
            <header>
              <strong>{who}</strong>
              {internal && <span className="tag">Internal note · not visible to customer</span>}
              <time>{formatTime(m.created_at)}</time>
            </header>
            <p>{m.body}</p>
          </article>
        )
      })}
      {ticket.messages.length === 0 && <p className="muted small">No replies yet.</p>}
      <div ref={endRef} />
    </div>
  )
}

function Composer({ ticket, identity }: { ticket: TicketDetail; identity: Identity }) {
  const isAgent = identity.role === 'agent'
  const queryClient = useQueryClient()
  const [body, setBody] = useState('')
  const [type, setType] = useState<MessageType>('PUBLIC')

  const send = useMutation({
    mutationFn: () => apiFor(identity).addMessage(ticket.id, body.trim(), type),
    onSuccess: () => {
      setBody('')
      queryClient.invalidateQueries({ queryKey: ['ticket'] })
      queryClient.invalidateQueries({ queryKey: ['tickets'] })
    },
  })

  if (ticket.status === 'CLOSED') {
    return <p className="muted small composer-closed">This ticket is closed.{isAgent && ' Change the status to reopen it before replying.'}</p>
  }

  const onSubmit = (e?: FormEvent) => {
    e?.preventDefault()
    if (body.trim() && !send.isPending) send.mutate()
  }

  const internal = type === 'INTERNAL'
  return (
    <form className={`card composer ${internal ? 'composer-internal' : ''}`} onSubmit={onSubmit}>
      {isAgent && (
        <div className="segmented" role="radiogroup" aria-label="Message type">
          <button type="button" role="radio" aria-checked={!internal} className={!internal ? 'on' : ''} onClick={() => setType('PUBLIC')}>
            Reply to customer
          </button>
          <button type="button" role="radio" aria-checked={internal} className={internal ? 'on' : ''} onClick={() => setType('INTERNAL')}>
            Internal note
          </button>
        </div>
      )}
      <textarea
        rows={3}
        maxLength={5000}
        aria-label={internal ? 'Internal note' : 'Reply'}
        placeholder={internal ? 'Only agents will see this note…' : isAgent ? 'Write a reply to the customer…' : 'Write a reply…'}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) onSubmit()
        }}
      />
      {send.isError && <p className="form-error" role="alert">{send.error.message}</p>}
      <div className="actions">
        <span className="muted small">Ctrl+Enter to send</span>
        <button type="submit" className="btn btn-primary" disabled={!body.trim() || send.isPending}>
          {send.isPending ? 'Sending…' : internal ? 'Add note' : 'Send reply'}
        </button>
      </div>
    </form>
  )
}

function TicketControls({ ticket, identity }: { ticket: TicketDetail; identity: Identity }) {
  const queryClient = useQueryClient()
  const agents = useQuery({ queryKey: ['agents'], queryFn: listAgents })

  const update = useMutation({
    mutationFn: (patch: TicketPatch) => apiFor(identity).updateTicket(ticket.id, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ticket'] })
      queryClient.invalidateQueries({ queryKey: ['tickets'] })
    },
  })

  return (
    <div className="card controls">
      <h2>Manage</h2>
      <label>
        Status
        <select value={ticket.status} disabled={update.isPending}
          onChange={(e) => update.mutate({ status: e.target.value as TicketPatch['status'] })}>
          {STATUSES.map((s) => <option key={s} value={s}>{label(s)}</option>)}
        </select>
      </label>
      <label>
        Priority
        <select value={ticket.priority} disabled={update.isPending}
          onChange={(e) => update.mutate({ priority: e.target.value as TicketPatch['priority'] })}>
          {PRIORITIES.map((p) => <option key={p} value={p}>{label(p)}</option>)}
        </select>
      </label>
      <label>
        Assignee
        <select value={ticket.assignee?.id ?? ''} disabled={update.isPending || agents.isPending}
          onChange={(e) => update.mutate({ assignee_id: e.target.value ? Number(e.target.value) : null })}>
          <option value="">Unassigned</option>
          {agents.data?.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
      </label>
      {identity.role === 'agent' && ticket.assignee?.id !== identity.agentId && (
        <button type="button" className="btn" disabled={update.isPending}
          onClick={() => update.mutate({ assignee_id: identity.agentId })}>
          Assign to me
        </button>
      )}
      {update.isPending && <p className="muted small">Saving…</p>}
      {update.isError && <p className="form-error" role="alert">{update.error.message}</p>}
    </div>
  )
}

function OrderCard({ orderId, identity }: { orderId: string; identity: Identity }) {
  const order = useQuery({
    queryKey: ['order', orderId],
    queryFn: () => apiFor(identity).getOrder(orderId),
    retry: false,
  })
  return (
    <div className="card">
      <h2>Order {orderId}</h2>
      {order.isPending ? (
        <p className="muted small">Loading order…</p>
      ) : order.isError ? (
        <p className="muted small">{order.error.message}</p>
      ) : (
        <dl className="facts">
          <dt>Destination</dt><dd>{order.data.destination}</dd>
          <dt>Package</dt><dd>{order.data.package}</dd>
          <dt>Order status</dt><dd>{label(order.data.status)}</dd>
          <dt>eSIM</dt><dd>{label(order.data.esim_status)}</dd>
        </dl>
      )}
    </div>
  )
}

function describeEvent(e: TicketEvent): string {
  const v = (x: string | null) => (x ? label(x) : '—')
  switch (e.type) {
    case 'CREATED':
      return 'Ticket created'
    case 'STATUS_CHANGED':
      return `Status changed: ${v(e.old_value)} → ${v(e.new_value)}`
    case 'PRIORITY_CHANGED':
      return `Priority changed: ${v(e.old_value)} → ${v(e.new_value)}`
    case 'ASSIGNEE_CHANGED':
      return e.new_value ? `Assigned to ${e.new_value}` : `Unassigned (was ${e.old_value})`
  }
}

function History({ events }: { events: TicketEvent[] }) {
  return (
    <div className="card">
      <h2>History</h2>
      <ol className="history">
        {[...events].reverse().map((e) => (
          <li key={e.id}>
            <span>{describeEvent(e)}</span>
            <span className="muted small">
              {formatTime(e.created_at)} · {e.actor_agent?.name ?? (e.type === 'CREATED' ? 'Customer' : 'System')}
            </span>
          </li>
        ))}
      </ol>
    </div>
  )
}
