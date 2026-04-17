/**
 * Pantalla de inicio operativo — escaner dual:
 * - QR de cliente  → vincula cliente al carrito, auto-navega a catalogo
 * - Codigo barras  → precio rapido + añadir al carrito directo
 * Resultado como bottom sheet (camara siempre visible)
 */
import { useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import Scanner from '../components/Scanner'
import Spinner from '../components/Spinner'
import { clientsApi } from '../api/clients'
import { catalogApi } from '../api/catalog'
import { useCart } from '../context/CartContext'

function fmt(n) {
  return Number(n).toLocaleString('es-MX', { minimumFractionDigits: 2 })
}

export default function ScannerScreen() {
  const [mode, setMode]     = useState('idle')   // idle | loading | client | product | error
  const [result, setResult] = useState(null)
  const [scanActive, setScan] = useState(true)
  const [manualInput, setManual] = useState('')
  const [showManual, setShowManual] = useState(false)
  const [qty, setQty] = useState(1)
  const { setClient, addLine } = useCart()
  const navigate   = useNavigate()
  const processing = useRef(false)
  const autoTimer  = useRef(null)

  const processCode = useCallback(async (raw) => {
    if (processing.current) return
    processing.current = true
    setScan(false)
    setMode('loading')

    try {
      // 1. Intentar como QR de cliente
      const cliente = await clientsApi.byQr(raw).catch(() => null)
      if (cliente) {
        setResult({ type: 'client', data: cliente })
        setMode('client')
        // Auto-navegar tras 2 s si no toca nada
        autoTimer.current = setTimeout(() => {
          setClient({ id: cliente.id, nombre: cliente.nombre, codigo_cliente: cliente.codigo_cliente })
          navigate('/catalog')
        }, 2000)
        return
      }

      // 2. Intentar como SKU de producto
      const variante = await catalogApi.bySku(raw).catch(() => null)
      if (variante) {
        setResult({ type: 'product', data: variante })
        setQty(1)
        setMode('product')
        return
      }

      setResult({ type: 'error', raw })
      setMode('error')
    } finally {
      processing.current = false
    }
  }, [navigate, setClient])

  function handleScan(raw) { processCode(raw) }

  function reset() {
    clearTimeout(autoTimer.current)
    setMode('idle')
    setResult(null)
    setScan(true)
    setManual('')
    processing.current = false
  }

  function confirmClient() {
    clearTimeout(autoTimer.current)
    setClient({ id: result.data.id, nombre: result.data.nombre, codigo_cliente: result.data.codigo_cliente })
    navigate('/catalog')
  }

  function addToCartAndReset() {
    const v = result.data
    for (let i = 0; i < qty; i++) {
      addLine(
        { sku: v.sku, talla: v.talla, color: v.color, precio_venta: Number(v.precio_venta) },
        { nombre: v.descripcion_snapshot ?? v.sku }
      )
    }
    reset()
  }

  function submitManual(e) {
    e.preventDefault()
    const val = manualInput.trim()
    if (!val) return
    setShowManual(false)
    processCode(val)
  }

  const hasSheet = mode !== 'idle'

  return (
    <div className="flex flex-col h-full bg-black">
      {/* Camara — ocupa todo menos el sheet inferior */}
      <div className="flex-1 relative min-h-0">
        <Scanner onScan={handleScan} active={scanActive} />

        {/* Hint cuando idle */}
        {!hasSheet && (
          <div className="absolute bottom-4 left-0 right-0 flex flex-col items-center gap-2 pointer-events-none">
            <p className="text-white/50 text-xs tracking-wide">
              Apunta al QR del cliente o código del producto
            </p>
          </div>
        )}

        {/* Spinner de loading encima de la camara */}
        {mode === 'loading' && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/50">
            <div className="bg-white rounded-2xl px-8 py-6 flex flex-col items-center gap-3">
              <Spinner />
              <p className="text-gray-600 text-sm font-medium">Identificando…</p>
            </div>
          </div>
        )}
      </div>

      {/* ── Bottom sheet de resultados ── */}
      {mode === 'client' && result && (
        <div className="animate-slide-up bg-white rounded-t-3xl px-5 pt-5 pb-8 shadow-2xl">
          <div className="flex items-center gap-4 mb-4">
            <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center shrink-0 text-2xl">
              👤
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs text-gray-400 uppercase tracking-wide">Cliente identificado</p>
              <p className="font-bold text-gray-900 truncate">{result.data.nombre}</p>
              <p className="text-xs text-gray-500">{result.data.tipo_cliente} · {result.data.nivel_lealtad}</p>
            </div>
            {result.data.descuento_preferente > 0 && (
              <span className="shrink-0 bg-green-100 text-green-700 text-xs font-bold px-2 py-1 rounded-full">
                -{result.data.descuento_preferente}%
              </span>
            )}
          </div>
          <p className="text-center text-xs text-gray-400 mb-3">Navegando al catálogo en 2 s…</p>
          <div className="flex gap-2">
            <button
              onClick={reset}
              className="flex-1 py-3 rounded-xl border border-gray-200 text-gray-600 text-sm font-medium active:bg-gray-50"
            >
              Cancelar
            </button>
            <button
              onClick={confirmClient}
              className="flex-[2] py-3 rounded-xl bg-brand-700 text-white font-semibold active:bg-brand-800"
            >
              Ver catálogo →
            </button>
          </div>
        </div>
      )}

      {mode === 'product' && result && (
        <div className="animate-slide-up bg-white rounded-t-3xl px-5 pt-5 pb-8 shadow-2xl">
          {/* Info del producto */}
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1 min-w-0 pr-3">
              <p className="text-xs text-gray-400 uppercase tracking-wide">Precio rápido</p>
              <p className="text-sm font-medium text-gray-700 truncate mt-0.5">{result.data.sku}</p>
              <p className="text-xs text-gray-400">{result.data.talla} · {result.data.color}</p>
            </div>
            <p className="text-3xl font-extrabold text-brand-700 shrink-0">
              ${fmt(result.data.precio_venta)}
            </p>
          </div>

          {/* Selector de cantidad */}
          <div className="flex items-center justify-between bg-gray-50 rounded-2xl px-4 py-3 mb-4">
            <span className="text-sm text-gray-500 font-medium">Cantidad</span>
            <div className="flex items-center gap-4">
              <button
                onClick={() => setQty(q => Math.max(1, q - 1))}
                className="w-9 h-9 rounded-full bg-white border border-gray-200 text-gray-700
                  text-lg font-bold flex items-center justify-center active:bg-gray-100 shadow-sm"
              >
                −
              </button>
              <span className="text-xl font-bold text-gray-900 w-6 text-center">{qty}</span>
              <button
                onClick={() => setQty(q => q + 1)}
                className="w-9 h-9 rounded-full bg-brand-700 text-white
                  text-lg font-bold flex items-center justify-center active:bg-brand-800 shadow-sm"
              >
                +
              </button>
            </div>
          </div>

          {/* Subtotal */}
          {qty > 1 && (
            <p className="text-right text-xs text-gray-400 mb-3">
              Subtotal: <span className="font-semibold text-gray-700">${fmt(result.data.precio_venta * qty)}</span>
            </p>
          )}

          <div className="flex gap-2">
            <button
              onClick={reset}
              className="flex-1 py-3 rounded-xl border border-gray-200 text-gray-600 text-sm font-medium active:bg-gray-50"
            >
              Escanear otro
            </button>
            <button
              onClick={addToCartAndReset}
              className="flex-[2] py-3 rounded-xl bg-brand-700 text-white font-semibold active:bg-brand-800"
            >
              + Añadir {qty > 1 ? `(${qty})` : ''} al presupuesto
            </button>
          </div>
        </div>
      )}

      {mode === 'error' && result && (
        <div className="animate-slide-up bg-white rounded-t-3xl px-5 pt-5 pb-8 shadow-2xl">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-3xl">🤷</span>
            <div>
              <p className="font-semibold text-gray-800">Código no reconocido</p>
              <p className="text-xs text-gray-400 break-all mt-0.5">{result.raw}</p>
            </div>
          </div>
          <button
            onClick={reset}
            className="w-full py-3 rounded-xl bg-gray-800 text-white font-semibold active:bg-gray-900"
          >
            Intentar de nuevo
          </button>
        </div>
      )}

      {/* Barra inferior cuando idle */}
      {mode === 'idle' && (
        <div className="bg-gray-950 px-5 py-3 pb-5">
          {showManual ? (
            <form onSubmit={submitManual} className="flex gap-2">
              <input
                autoFocus
                type="text"
                value={manualInput}
                onChange={e => setManual(e.target.value)}
                placeholder="Escribe SKU o código…"
                className="flex-1 bg-white/10 text-white placeholder-white/30 rounded-xl px-4 py-2.5 text-sm outline-none"
              />
              <button
                type="submit"
                className="bg-brand-700 text-white px-4 py-2.5 rounded-xl text-sm font-semibold active:bg-brand-800"
              >
                Buscar
              </button>
              <button
                type="button"
                onClick={() => setShowManual(false)}
                className="text-white/40 px-2 text-sm"
              >
                ✕
              </button>
            </form>
          ) : (
            <div className="flex gap-2">
              <button
                onClick={() => setShowManual(true)}
                className="flex-1 bg-white/10 text-white/70 py-2.5 rounded-xl text-sm active:bg-white/20"
              >
                ✏️ Ingresar código
              </button>
              <button
                onClick={() => { setClient(null); navigate('/catalog') }}
                className="flex-1 bg-white/10 text-white/70 py-2.5 rounded-xl text-sm active:bg-white/20"
              >
                📦 Ir al catálogo
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
