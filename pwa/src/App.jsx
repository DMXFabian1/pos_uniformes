import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { useSession } from './context/SessionContext'
import { useCart } from './context/CartContext'
import BottomNav from './components/BottomNav'
import Banner from './components/Banner'
import LoginScreen      from './screens/LoginScreen'
import ScannerScreen    from './screens/ScannerScreen'
import CatalogScreen    from './screens/CatalogScreen'
import QuotesScreen     from './screens/QuotesScreen'
import QuoteCurrentScreen from './screens/QuoteCurrentScreen'
import SalesScreen      from './screens/SalesScreen'
import TicketsScreen    from './screens/TicketsScreen'

function fmt(n) {
  return Number(n).toLocaleString('es-MX', { minimumFractionDigits: 2 })
}

function EmployeeBar({ session, onLogout }) {
  return (
    <div className="bg-brand-700 text-white flex items-center justify-between px-4 py-2.5 text-sm">
      <div className="flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-full bg-white/20 flex items-center justify-center text-xs font-bold">
          {session.employee_name?.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()}
        </div>
        <span className="font-medium">{session.employee_name}</span>
      </div>
      <button onClick={onLogout} className="text-white/60 text-xs font-medium active:text-white px-2 py-1 -mr-2 rounded-lg active:bg-white/10 transition-colors">
        Cambiar
      </button>
    </div>
  )
}

function FloatingCart() {
  const { lines, total } = useCart()
  const navigate = useNavigate()
  const location = useLocation()

  if (lines.length === 0 || location.pathname === '/quotes/current' || location.pathname === '/scanner') return null

  return (
    <div className="fixed bottom-16 left-0 right-0 z-30 px-4 pb-2 safe-area-bottom">
      <button
        onClick={() => navigate('/quotes/current')}
        className="w-full bg-brand-600 text-white rounded-2xl px-5 py-3.5
          flex items-center justify-between shadow-float active:bg-brand-700 active:scale-[0.98] transition-all"
      >
        <span className="font-semibold">Ver presupuesto ({lines.length})</span>
        <span className="font-bold text-lg">${fmt(total)}</span>
      </button>
    </div>
  )
}

export default function App() {
  const { session, logout } = useSession()

  if (!session) return <LoginScreen />

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-surface-50">
      <Banner />
      <EmployeeBar session={session} onLogout={logout} />

      <main className="flex-1 overflow-hidden relative">
        <div className="absolute inset-0 overflow-y-auto overscroll-contain pb-20">
          <Routes>
            <Route path="/"                 element={<Navigate to="/scanner" replace />} />
            <Route path="/scanner"          element={<ScannerScreen />} />
            <Route path="/catalog"          element={<CatalogScreen />} />
            <Route path="/quotes"           element={<QuotesScreen />} />
            <Route path="/quotes/current"   element={<QuoteCurrentScreen />} />
            <Route path="/sales"            element={<SalesScreen />} />
            <Route path="/tickets"          element={<TicketsScreen />} />
            <Route path="*"                 element={<Navigate to="/scanner" replace />} />
          </Routes>
        </div>
      </main>

      <FloatingCart />
      <BottomNav />
    </div>
  )
}
