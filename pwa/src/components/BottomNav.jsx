import { NavLink } from 'react-router-dom'
import { useCart } from '../context/CartContext'

const tabs = [
  { to: '/scanner', icon: ScanIcon,     label: 'Escaner'      },
  { to: '/catalog', icon: CatalogIcon,  label: 'Catalogo'     },
  { to: '/quotes',  icon: QuoteIcon,    label: 'Presupuestos' },
  { to: '/sales',   icon: SalesIcon,    label: 'Mis Ventas'   },
  { to: '/tickets', icon: TicketIcon,   label: 'Mis Tickets'  },
]

export default function BottomNav() {
  const { lines } = useCart()

  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 flex z-40 safe-area-bottom">
      {tabs.map(({ to, icon: Icon, label }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            `flex-1 flex flex-col items-center justify-center py-2 gap-0.5 text-xs font-medium transition-colors
             ${isActive ? 'text-brand-700' : 'text-gray-500 active:text-brand-600'}`
          }
        >
          {({ isActive }) => (
            <>
              <span className="relative">
                <Icon active={isActive} />
                {to === '/quotes' && lines.length > 0 && (
                  <span className="absolute -top-1 -right-2 bg-brand-600 text-white text-[10px] font-bold rounded-full min-w-[16px] h-4 flex items-center justify-center px-1">
                    {lines.length}
                  </span>
                )}
              </span>
              <span>{label}</span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}

function ScanIcon({ active }) {
  return (
    <svg className={`w-6 h-6 ${active ? 'text-brand-700' : 'text-gray-400'}`} fill="none" stroke="currentColor" strokeWidth={active ? 2.5 : 2} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 7V5a2 2 0 012-2h2M17 3h2a2 2 0 012 2v2M21 17v2a2 2 0 01-2 2h-2M7 21H5a2 2 0 01-2-2v-2" />
      <line x1="3" y1="12" x2="21" y2="12" strokeLinecap="round" />
    </svg>
  )
}

function CatalogIcon({ active }) {
  return (
    <svg className={`w-6 h-6 ${active ? 'text-brand-700' : 'text-gray-400'}`} fill="none" stroke="currentColor" strokeWidth={active ? 2.5 : 2} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
    </svg>
  )
}

function QuoteIcon({ active }) {
  return (
    <svg className={`w-6 h-6 ${active ? 'text-brand-700' : 'text-gray-400'}`} fill="none" stroke="currentColor" strokeWidth={active ? 2.5 : 2} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  )
}

function SalesIcon({ active }) {
  return (
    <svg className={`w-6 h-6 ${active ? 'text-brand-700' : 'text-gray-400'}`} fill="none" stroke="currentColor" strokeWidth={active ? 2.5 : 2} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
    </svg>
  )
}

function TicketIcon({ active }) {
  return (
    <svg className={`w-6 h-6 ${active ? 'text-brand-700' : 'text-gray-400'}`} fill="none" stroke="currentColor" strokeWidth={active ? 2.5 : 2} viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 5v2m0 4v2m0 4v2M5 5a2 2 0 00-2 2v3a2 2 0 110 4v3a2 2 0 002 2h14a2 2 0 002-2v-3a2 2 0 110-4V7a2 2 0 00-2-2H5z" />
    </svg>
  )
}
