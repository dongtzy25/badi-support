import { Link, Navigate, Route, Routes } from 'react-router-dom'
import { IdentitySwitcher } from './components'
import NewTicketPage from './pages/NewTicketPage'
import TicketDetailPage from './pages/TicketDetailPage'
import TicketListPage from './pages/TicketListPage'

export default function App() {
  return (
    <>
      <header className="topbar">
        <Link to="/tickets" className="brand">
          <span className="brand-mark" aria-hidden="true">B</span> Badi Support
        </Link>
        <IdentitySwitcher />
      </header>
      <main className="container">
        <Routes>
          <Route path="/" element={<Navigate to="/tickets" replace />} />
          <Route path="/tickets" element={<TicketListPage />} />
          <Route path="/tickets/new" element={<NewTicketPage />} />
          <Route path="/tickets/:id" element={<TicketDetailPage />} />
          <Route path="*" element={<p className="state">Page not found. <Link to="/tickets">Go to tickets</Link></p>} />
        </Routes>
      </main>
    </>
  )
}
