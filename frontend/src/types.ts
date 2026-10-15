// Mirrors the backend schemas (app/schemas.py). Keep the two in sync.

export const STATUSES = [
  'OPEN',
  'IN_PROGRESS',
  'WAITING_FOR_CUSTOMER',
  'WAITING_FOR_PROVIDER',
  'RESOLVED',
  'CLOSED',
] as const
export const PRIORITIES = ['LOW', 'MEDIUM', 'HIGH', 'URGENT'] as const
export const CATEGORIES = [
  'INSTALLATION',
  'ACTIVATION',
  'CONNECTIVITY',
  'ORDER',
  'TOPUP',
  'REFUND',
  'OTHER',
] as const

export type TicketStatus = (typeof STATUSES)[number]
export type TicketPriority = (typeof PRIORITIES)[number]
export type TicketCategory = (typeof CATEGORIES)[number]
export type MessageType = 'PUBLIC' | 'INTERNAL'
export type EventType = 'CREATED' | 'STATUS_CHANGED' | 'PRIORITY_CHANGED' | 'ASSIGNEE_CHANGED'

export interface Agent {
  id: number
  name: string
  email: string
}

export interface Ticket {
  id: number
  number: string
  customer_email: string
  order_id: string | null
  category: TicketCategory
  subject: string
  description: string
  priority: TicketPriority
  status: TicketStatus
  assignee: Agent | null
  created_at: string
  updated_at: string
}

export interface TicketList {
  items: Ticket[]
  total: number
  limit: number
  offset: number
}

export interface Message {
  id: number
  ticket_id: number
  sender_type: 'CUSTOMER' | 'AGENT'
  sender_agent: Agent | null
  type: MessageType
  body: string
  created_at: string
}

export interface TicketEvent {
  id: number
  type: EventType
  old_value: string | null
  new_value: string | null
  actor_agent: Agent | null
  created_at: string
}

export interface TicketDetail extends Ticket {
  messages: Message[]
  events: TicketEvent[]
}

export interface OrderSummary {
  order_id: string
  destination: string
  package: string
  status: string
  esim_status: string
}

export interface TicketFilters {
  status?: TicketStatus
  priority?: TicketPriority
  category?: TicketCategory
  assignee_id?: number
  unassigned?: boolean
  q?: string
  offset?: number
}

export interface NewTicket {
  customer_email: string
  order_id?: string
  category: TicketCategory
  subject: string
  description: string
  priority: TicketPriority
}

export interface TicketPatch {
  status?: TicketStatus
  priority?: TicketPriority
  assignee_id?: number | null
}

/** "WAITING_FOR_CUSTOMER" -> "Waiting for customer" */
export function label(value: string): string {
  const text = value.replaceAll('_', ' ').toLowerCase()
  return text.charAt(0).toUpperCase() + text.slice(1)
}
