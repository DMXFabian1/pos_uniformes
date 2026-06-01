import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { quotesApi } from '../api/quotes'
import { useCart } from '../context/CartContext'
import { useConfirm } from '../components/ConfirmModal'
import { useToast } from '../components/Toast'
import { ListSkeleton } from '../components/Skeleton'
import PullToRefresh from '../components/PullToRefresh'

export default function QuotesScreen() {
  const [quotes, setQuotes] = useState([])
  const [loading, setLoading] = useState(true)
  const { lines }             = useCart()
  const navigate              = useNavigate()
  const { confirm }           = useConfirm()
  const { show: toast }       = useToast()

  const loadQuotes = useCallback(() => {
    return quotesApi.list()
      .then(setQuotes)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadQuotes() }, [loadQuotes])

  async function markReady(id, e) {
    e.stopPropagation()
    await quotesApi.markReady(id)
    setQuotes(q => q.filter(p => p.id !== id))
    toast('Presupuesto enviado a caja')
  }

  async function cancel(id, e) {
    e.stopPropagation()
    const ok = await confirm({
      title: 'Cancelar presupuesto',
      message: 'Se eliminara este presupuesto del servidor. Esta accion no se puede deshacer.',
      confirmLabel: 'Cancelar presupuesto',
      cancelLabel: 'Volver',
      danger: true,
    })
    if (!ok) return
    await quotesApi.cancel(id)
    setQuotes(q => q.filter(p => p.id !== id))
    toast('Presupuesto cancelado', { type: 'info' })
  }

  return (
    <div className="flex flex-col h-full bg-surface-50">
      <div className="bg-surface-0 px-5 pt-5 pb-4 border-b border-surface-200">
        <h2 className="font-bold text-ink-900 text-lg">Mis presupuestos</h2>
        <p className="text-xs text-ink-400 mt-0.5">Borradores activos en el servidor</p>
      </div>

      <PullToRefresh onRefresh={loadQuotes} className="flex-1 px-4 py-4 space-y-3">
        {lines.length > 0 && (
          <button
            onClick={() => navigate('/quotes/current')}
            className="w-full bg-brand-600 text-white rounded-2xl p-5 text-left shadow-card active:scale-[0.98] transition-all"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="font-bold">Presupuesto en curso</p>
                <p className="text-sm text-white/70 mt-0.5">{lines.length} producto{lines.length !== 1 ? 's' : ''}</p>
              </div>
              <svg className="w-5 h-5 text-white/60" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
              </svg>
            </div>
          </button>
        )}

        {loading && <ListSkeleton count={3} />}

        {!loading && quotes.length === 0 && lines.length === 0 && (
          <div className="text-center py-16">
            <div className="w-16 h-16 rounded-3xl bg-surface-100 border border-surface-200 flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-ink-300" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
              </svg>
            </div>
            <p className="text-ink-700 font-semibold">Sin borradores activos</p>
            <p className="text-sm text-ink-400 mt-1">Empieza uno desde el catalogo</p>
          </div>
        )}

        {!loading && quotes.map(q => (
          <div key={q.id} className="card p-5">
            <div className="flex items-start justify-between mb-3">
              <div>
                <p className="font-bold text-ink-900 text-sm">{q.folio}</p>
                {q.cliente_nombre && <p className="text-xs text-ink-500 mt-0.5">Cliente: {q.cliente_nombre}</p>}
                <p className="text-xs text-ink-400 mt-0.5">{q.total_lineas} linea{q.total_lineas !== 1 ? 's' : ''}</p>
              </div>
              <p className="font-bold text-brand-600 text-lg">
                ${Number(q.total).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
              </p>
            </div>
            <div className="flex gap-2.5 mt-4">
              <button
                onClick={(e) => markReady(q.id, e)}
                className="flex-1 bg-success-500 text-white text-sm font-semibold py-3 rounded-xl active:bg-success-600 active:scale-[0.98] transition-all touch-target"
              >
                Listo para caja
              </button>
              <button
                onClick={(e) => cancel(q.id, e)}
                className="btn-secondary px-4 py-3 text-sm"
              >
                Cancelar
              </button>
            </div>
          </div>
        ))}
      </PullToRefresh>
    </div>
  )
}
