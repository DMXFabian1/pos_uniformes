import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCart } from '../context/CartContext'
import { quotesApi } from '../api/quotes'
import { useConfirm } from '../components/ConfirmModal'
import { useToast } from '../components/Toast'
import SwipeToDelete from '../components/SwipeToDelete'

export default function QuoteCurrentScreen() {
  const { lines, client, total, updateQty, removeLine, clear } = useCart()
  const [saving, setSaving] = useState(false)
  const [error, setError]   = useState('')
  const navigate            = useNavigate()
  const { confirm }         = useConfirm()
  const { show: toast }     = useToast()

  if (lines.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center px-6">
        <div className="w-20 h-20 rounded-3xl bg-surface-100 border border-surface-200 flex items-center justify-center mb-5">
          <svg className="w-10 h-10 text-ink-300" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 3h1.386c.51 0 .955.343 1.087.835l.383 1.437M7.5 14.25a3 3 0 00-3 3h15.75m-12.75-3h11.218c1.121-2.3 2.1-4.684 2.924-7.138a60.114 60.114 0 00-16.536-1.84M7.5 14.25L5.106 5.272M6 20.25a.75.75 0 11-1.5 0 .75.75 0 011.5 0zm12.75 0a.75.75 0 11-1.5 0 .75.75 0 011.5 0z" />
          </svg>
        </div>
        <p className="font-bold text-ink-700 mb-2 text-lg">Presupuesto vacio</p>
        <p className="text-sm text-ink-400 mb-6">Agrega productos desde el catalogo</p>
        <button onClick={() => navigate('/catalog')} className="btn-primary px-8 py-3.5">
          Ir al catalogo
        </button>
      </div>
    )
  }

  async function saveAndSend() {
    setSaving(true)
    setError('')
    try {
      await quotesApi.create({
        cliente_id: client?.id ?? null,
        cliente_nombre: client?.nombre ?? null,
        lineas: lines.map(l => ({
          sku: l.sku,
          cantidad: l.cantidad,
          precio_unitario: l.precio,
        })),
      })
      clear()
      toast('Presupuesto guardado')
      navigate('/quotes', { replace: true })
    } catch (e) {
      setError(e.message ?? 'No se pudo guardar el presupuesto.')
    } finally {
      setSaving(false)
    }
  }

  async function handleClear() {
    const ok = await confirm({
      title: 'Limpiar presupuesto',
      message: `Se eliminaran los ${lines.length} productos del presupuesto actual.`,
      confirmLabel: 'Limpiar todo',
      cancelLabel: 'Conservar',
      danger: true,
    })
    if (ok) clear()
  }

  return (
    <div className="flex flex-col h-full bg-surface-50">
      <div className="bg-surface-0 px-5 pt-5 pb-4 border-b border-surface-200">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-bold text-ink-900 text-lg">Presupuesto</h2>
            {client && <p className="text-sm text-ink-500 mt-0.5">Cliente: {client.nombre}</p>}
          </div>
          <button
            onClick={handleClear}
            className="text-danger-500 text-sm font-medium px-3 py-2 rounded-xl active:bg-danger-50 transition-colors"
          >
            Limpiar
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto overscroll-contain px-4 py-4 space-y-2.5">
        {lines.map(l => (
          <SwipeToDelete key={l.sku} onDelete={() => removeLine(l.sku)}>
            <div className="card p-4 border-0 rounded-none shadow-none">
              <div className="flex-1 min-w-0 mb-3">
                <p className="font-semibold text-ink-900 text-sm leading-snug">{l.descripcion}</p>
                <p className="text-xs text-ink-400 mt-0.5">{l.sku}</p>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-0 bg-surface-100 rounded-xl border border-surface-200">
                  <button onClick={() => updateQty(l.sku, l.cantidad - 1)}
                    className="w-10 h-10 flex items-center justify-center text-ink-700 text-lg font-bold active:bg-surface-200 rounded-l-xl touch-target">-</button>
                  <span className="font-bold text-ink-900 w-8 text-center text-sm">{l.cantidad}</span>
                  <button onClick={() => updateQty(l.sku, l.cantidad + 1)}
                    className="w-10 h-10 flex items-center justify-center text-ink-700 text-lg font-bold active:bg-surface-200 rounded-r-xl touch-target">+</button>
                </div>
                <div className="text-right">
                  <p className="text-[11px] text-ink-400">${Number(l.precio).toFixed(2)} c/u</p>
                  <p className="font-bold text-brand-600">
                    ${Number(l.subtotal).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                  </p>
                </div>
              </div>
            </div>
          </SwipeToDelete>
        ))}
      </div>

      <div className="bg-surface-0 border-t border-surface-200 px-5 py-5 space-y-4 shadow-[0_-2px_16px_rgba(74,48,32,0.04)]">
        {error && (
          <div className="bg-danger-50 border border-danger-100 text-danger-500 rounded-xl px-4 py-2.5 text-sm text-center font-medium">
            {error}
          </div>
        )}

        <div className="flex justify-between items-center">
          <span className="text-ink-500 font-medium">Total</span>
          <span className="text-2xl font-bold text-brand-600">
            ${total.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
          </span>
        </div>

        <button
          onClick={saveAndSend}
          disabled={saving}
          className="w-full btn-primary py-4 text-base"
        >
          {saving ? 'Guardando...' : 'Guardar presupuesto'}
        </button>

        <button
          onClick={() => navigate('/catalog')}
          className="w-full btn-ghost py-2.5 text-sm"
        >
          + Agregar mas productos
        </button>
      </div>
    </div>
  )
}
