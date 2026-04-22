import { Routes, Route, Navigate } from 'react-router-dom'
import { useSession } from './context/SessionContext'
import BottomNav from './components/BottomNav'
import Banner from './components/Banner'
import LoginScreen      from './screens/LoginScreen'
import ScannerScreen    from './screens/ScannerScreen'
import CatalogScreen    from './screens/CatalogScreen'
import QuotesScreen     from './screens/QuotesScreen'
import QuoteCurrentScreen from './screens/QuoteCurrentScreen'
import SalesScreen      from './screens/SalesScreen'
import TicketsScreen    from './screens/TicketsScreen'

function EmployeeBar({ session, onLogout }) {
  return (
    <div className="bg-brand-800 text-white flex items-center justify-between px-4 py-2 text-sm">
      <span className="font-medium">{session.employee_name}</span>
      <button onClick={onLogout} className="text-white/60 text-xs active:text-white">
        Cambiar empleada
      </button>
    </div>
  )
}

export default function App() {
  const { session, logout } = useSession()

  if (!session) return <LoginScreen />

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <Banner />
      <EmployeeBar session={session} onLogout={logout} />

      {/* Contenido con scroll — deja espacio para la nav inferior */}
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

      <BottomNav />
    </div>
  )
}
