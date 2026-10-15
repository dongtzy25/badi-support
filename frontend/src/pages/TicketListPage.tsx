import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { apiFor, listAgents } from '../api'
import { Empty, ErrorBox, Loading, PriorityBadge, StatusBadge, formatTime } from '../components'
import { identityKey, useIdentity } from '../identity'
import { CATEGORIES, PRIORITIES, STATUSES, label, type TicketFilters } from '../types'

const PAGE_SIZE = 20

export default function TicketListPage() {
  const { identity } = useIdentity()
  const isAgent = identity.role === 'agent'
  const navigate = useNavigate()

  // Filters live in the URL (?status=OPEN&q=...), so they survive a refresh and can be shared.
  const [params, setParams] = useSearchParams()
  const filters: TicketFilters = {
    status: (params.get('status') as TicketFilters['status']) || undefined,
    priority: (params.get('priority') as TicketFilters['priority']) || undefined,
    category: (params.get('category') as TicketFilters['category']) || undefined,
    assignee_id: params.get('assignee') && params.get('assignee') !== 'none' ? Number(params.get('assignee')) : undefined,
    unassigned: params.get('assignee') === 'none',
    q: params.get('q') || undefined,
    offset: Number(params.get('offset') || 0),
  }

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    next.delete('offset') // any filter change goes back to page 1
    setParams(next, { replace: true })
  }

  // Search box: wait until the user stops typing for 300ms before querying.
  const [search, setSearch] = useState(filters.q ?? '')
  useEffect(() => {
    const timer = setTimeout(() => {
      if (search !== (params.get('q') ?? '')) setFilter('q', search.trim())
    }, 300)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search])

  const tickets = useQuery({
    queryKey: ['tickets', identityKey(identity), filters],
    queryFn: () => apiFor(identity).listTickets(filters),
    placeholderData: keepPreviousData, // keep showing the old page while the next one loads
  })
  const agents = useQuery({ queryKey: ['agents'], queryFn: listAgents, enabled: isAgent })

  const hasFilters = ['status', 'priority', 'category', 'assignee', 'q'].some((k) => params.get(k))
  const data = tickets.data
  const offset = filters.offset ?? 0

  return (
    <section>
      <header className="page-header">
        <div>
          <h1>{isAgent ? 'Support tickets' : 'My support requests'}</h1>
          {data && <p className="muted">{data.total} ticket{data.total === 1 ? '' : 's'}</p>}
        </div>
        <Link to="/tickets/new" className="btn btn-primary">
          New ticket
        </Link>
      </header>

      <div className="filters">
        <input
          type="search"
          placeholder={isAgent ? 'Search number, subject, email, order…' : 'Search my tickets…'}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search tickets"
        />
        <select aria-label="Status" value={params.get('status') ?? ''} onChange={(e) => setFilter('status', e.target.value)}>
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>{label(s)}</option>
          ))}
        </select>
        <select aria-label="Priority" value={params.get('priority') ?? ''} onChange={(e) => setFilter('priority', e.target.value)}>
          <option value="">All priorities</option>
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>{label(p)}</option>
          ))}
        </select>
        <select aria-label="Category" value={params.get('category') ?? ''} onChange={(e) => setFilter('category', e.target.value)}>
          <option value="">All categories</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{label(c)}</option>
          ))}
        </select>
        {isAgent && (
          <select aria-label="Assignee" value={params.get('assignee') ?? ''} onChange={(e) => setFilter('assignee', e.target.value)}>
            <option value="">Any assignee</option>
            <option value={String(identity.agentId)}>Assigned to me</option>
            <option value="none">Unassigned</option>
            {agents.data?.filter((a) => a.id !== identity.agentId).map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        )}
      </div>

      {tickets.isPending ? (
        <Loading text="Loading tickets…" />
      ) : tickets.isError ? (
        <ErrorBox error={tickets.error} onRetry={() => tickets.refetch()} />
      ) : data!.items.length === 0 ? (
        hasFilters ? (
          <Empty title="No tickets match these filters.">
            <button type="button" className="btn" onClick={() => { setSearch(''); setParams({}) }}>
              Clear filters
            </button>
          </Empty>
        ) : (
          <Empty title={isAgent ? 'No tickets yet.' : "You haven't opened any support requests yet."}>
            <Link to="/tickets/new" className="btn btn-primary">Open a ticket</Link>
          </Empty>
        )
      ) : (
        <>
          <div className={`table-wrap ${tickets.isFetching ? 'is-refreshing' : ''}`}>
            <table className="tickets">
              <thead>
                <tr>
                  <th>Ticket</th>
                  <th>Subject</th>
                  {isAgent && <th>Customer</th>}
                  <th>Category</th>
                  <th>Priority</th>
                  <th>Status</th>
                  {isAgent && <th>Assignee</th>}
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {data!.items.map((t) => (
                  <tr key={t.id} onClick={() => navigate(`/tickets/${t.id}`)}>
                    <td className="mono nowrap">
                      <Link to={`/tickets/${t.id}`} onClick={(e) => e.stopPropagation()}>{t.number}</Link>
                    </td>
                    <td className="subject">{t.subject}</td>
                    {isAgent && <td className="muted">{t.customer_email}</td>}
                    <td>{label(t.category)}</td>
                    <td><PriorityBadge priority={t.priority} /></td>
                    <td><StatusBadge status={t.status} /></td>
                    {isAgent && <td>{t.assignee?.name ?? <span className="muted">Unassigned</span>}</td>}
                    <td className="muted nowrap">{formatTime(t.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data!.total > PAGE_SIZE && (
            <div className="pager">
              <span className="muted">
                {offset + 1}–{Math.min(offset + PAGE_SIZE, data!.total)} of {data!.total}
              </span>
              <button type="button" className="btn" disabled={offset === 0}
                onClick={() => setParams((p) => { p.set('offset', String(Math.max(0, offset - PAGE_SIZE))); return p })}>
                Previous
              </button>
              <button type="button" className="btn" disabled={offset + PAGE_SIZE >= data!.total}
                onClick={() => setParams((p) => { p.set('offset', String(offset + PAGE_SIZE)); return p })}>
                Next
              </button>
            </div>
          )}
        </>
      )}
    </section>
  )
}
