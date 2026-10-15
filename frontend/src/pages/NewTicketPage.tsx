import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError, apiFor } from '../api'
import { useIdentity } from '../identity'
import { CATEGORIES, PRIORITIES, label, type NewTicket } from '../types'

export default function NewTicketPage() {
  const { identity } = useIdentity()
  const isCustomer = identity.role === 'customer'
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [form, setForm] = useState<NewTicket>({
    customer_email: isCustomer ? identity.email : '',
    order_id: '',
    category: 'CONNECTIVITY',
    subject: '',
    description: '',
    priority: 'MEDIUM',
  })
  const set = (key: keyof NewTicket, value: string) => setForm((f) => ({ ...f, [key]: value }))

  const create = useMutation({
    mutationFn: (data: NewTicket) => apiFor(identity).createTicket(data),
    onSuccess: (ticket) => {
      queryClient.invalidateQueries({ queryKey: ['tickets'] })
      navigate(`/tickets/${ticket.id}`)
    },
  })

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    // The backend does the real validation; we only drop the empty optional field.
    create.mutate({ ...form, order_id: form.order_id?.trim() || undefined })
  }

  // Field-level messages from the API's 422 response, e.g. { subject: "..." }
  const fieldErrors = create.error instanceof ApiError ? create.error.fieldErrors : {}
  const formError = create.error && Object.keys(fieldErrors).length === 0 ? create.error.message : null
  const err = (field: string) =>
    fieldErrors[field] ? <span className="field-error">{fieldErrors[field]}</span> : null

  return (
    <section className="narrow">
      <Link to="/tickets" className="back">← Back to tickets</Link>
      <h1>{isCustomer ? 'Contact support' : 'New ticket'}</h1>
      <p className="muted">
        {isCustomer ? "Tell us what's wrong and we'll get back to you here." : 'Open a ticket on behalf of a customer.'}
      </p>

      <form className="card form" onSubmit={onSubmit} noValidate>
        <label>
          Customer email
          <input type="email" required value={form.customer_email} readOnly={isCustomer}
            onChange={(e) => set('customer_email', e.target.value)} />
          {err('customer_email')}
        </label>

        <div className="row">
          <label>
            Category
            <select value={form.category} onChange={(e) => set('category', e.target.value)}>
              {CATEGORIES.map((c) => <option key={c} value={c}>{label(c)}</option>)}
            </select>
            {err('category')}
          </label>
          <label>
            Priority
            <select value={form.priority} onChange={(e) => set('priority', e.target.value)}>
              {PRIORITIES.map((p) => <option key={p} value={p}>{label(p)}</option>)}
            </select>
            {err('priority')}
          </label>
          <label>
            Order ID <span className="muted">(optional)</span>
            <input placeholder="ORD-10293" value={form.order_id} onChange={(e) => set('order_id', e.target.value)} />
            {err('order_id')}
          </label>
        </div>

        <label>
          Subject
          <input required maxLength={200} placeholder="eSIM installed but no internet" value={form.subject}
            onChange={(e) => set('subject', e.target.value)} />
          {err('subject')}
        </label>

        <label>
          Description
          <textarea required rows={6} maxLength={5000}
            placeholder="What happened? Which device and country are you in?"
            value={form.description} onChange={(e) => set('description', e.target.value)} />
          {err('description')}
        </label>

        {formError && <p className="form-error" role="alert">{formError}</p>}

        <div className="actions">
          <button type="submit" className="btn btn-primary" disabled={create.isPending}>
            {create.isPending ? 'Creating…' : 'Create ticket'}
          </button>
        </div>
      </form>
    </section>
  )
}
