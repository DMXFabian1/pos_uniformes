/**
 * Pantalla de inicio operativo — escaner dual:
 * - QR de cliente  → vincula cliente al carrito, auto-navega a catalogo
 * - Codigo barras  → precio rapido + añadir al carrito directo
 * Resultado como bottom sheet (camara siempre visible)
 */
import { useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import Scanner from '../components/Scanner'
import { clientsApi } from '../api/clients'
import { catalogApi } from '../api/catalog'
import { useCart } from '../context/CartContext'

const MAX_HISTORY = 5

function fmt(n) {
  return Number(n).toLocaleString('es-MX', { minimumFractionDigits: 2 })
}


export default function ScannerScreen() {
  const [mode, setMode]           = useState('idle')
  const [result, setResult]       = useState(null)
  const [scanActive, setScan]     = useState(true)
  const [manualInput, setManual]  = useState('')
  const [showManual, setShowManual] = useState(false)
  const [qty, setQty]             = useState(1)
  const [history, setHistory]     = useState([])
  const [showHistory, setShowHistory] = useState(false)
  const { setClient, addLine }    = useCart()
  const navigate   = useNavigate()
  const processing = useRef(false)
  const autoTimer  = useRef(null)

  function pushHistory(entry) {
    setHistory(prev => [entry, ...prev].slice(0, MAX_HISTORY))
  }

  const processCode = useCallback(async (raw) => {
    if (processing.current) return
    processing.current = true
    setShowHistory(false)
    setScan(false)
    setMode('loading')

    try {
      const cliente = await clientsApi.byQr(raw).catch(() => null)
      if (cliente) {
        setResult({ type: 'client', data: cliente })
        setMode('client')
        pushHistory({ type: 'client', label: cliente.nombre, subLabel: cliente.tipo_cliente, raw })
        autoTimer.current = setTimeout(() => {
          setClient({ id: cliente.id, nombre: cliente.nombre, codigo_cliente: cliente.codigo_cliente })
          navigate('/catalog')
        }, 2000)
        return
      }

      const variante = await catalogApi.bySku(raw).catch(() => null)
      if (variante) {
        setResult({ type: 'product', data: variante })
        setQty(1)
        setMode('product')
        pushHistory({
          type: 'product',
          label: variante.nombre,
          subLabel: `${variante.talla} · ${variante.color}`,
          price: variante.precio_venta,
          raw,
        })
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
        { nombre: v.nombre ?? v.sku }
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
    <div className="relative h-full bg-black">
      {/* Camara — siempre ocupa toda la pantalla */}
      <div className="absolute inset-0">
        <Scanner onScan={handleScan} active={scanActive} />

        {/* Boton historial — solo cuando hay items y no hay sheet */}
        {!hasSheet && history.length > 0 && (
          <div className="absolute top-3 right-3">
            <button
              onClick={() => setShowHistory(h => !h)}
              className="flex items-center gap-1.5 bg-black/60 backdrop-blur-sm
                text-white/80 text-xs font-medium px-3 py-2 rounded-full border border-white/10"
            >
              🕐 Recientes
              <span className="bg-white/20 text-white text-xs rounded-full w-4 h-4
                flex items-center justify-center font-bold">
                {history.length}
              </span>
            </button>

            {/* Panel desplegable */}
            {showHistory && (
              <div className="absolute top-10 right-0 w-64 bg-black/80 backdrop-blur-sm
                rounded-2xl overflow-hidden shadow-2xl border border-white/10 mt-1">
                {history.map((h, i) => (
                  <button
                    key={i}
                    onClick={() => { setShowHistory(false); processCode(h.raw) }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 active:bg-white/10
                      border-b border-white/5 last:border-0 text-left"
                  >
                    <span className="text-base shrink-0">{h.type === 'client' ? '👤' : '📦'}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-white text-xs font-medium truncate">{h.label}</p>
                      <p className="text-white/40 text-xs truncate">{h.subLabel}</p>
                    </div>
                    {h.price && (
                      <p className="text-white/70 text-xs font-semibold shrink-0">${fmt(h.price)}</p>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Hint cuando no hay historial */}
        {!hasSheet && history.length === 0 && (
          <div className="absolute bottom-4 left-0 right-0 flex flex-col items-center pointer-events-none">
            <p className="text-white/50 text-xs tracking-wide">
              Apunta al QR del cliente o código del producto
            </p>
          </div>
        )}

        {/* Indicador de procesando — barra superior sin tapar la camara */}
        {mode === 'loading' && (
          <div className="absolute top-0 left-0 right-0">
            {/* Barra de progreso indeterminada */}
            <div className="h-1 bg-white/10 overflow-hidden">
              <div className="h-full bg-green-400 animate-[loading_1s_ease-in-out_infinite]
                w-1/3 rounded-full" style={{ animation: 'loading 1s ease-in-out infinite' }} />
            </div>
            <div className="flex items-center justify-center mt-2">
              <span className="bg-black/60 backdrop-blur-sm text-white/80 text-xs
                px-3 py-1.5 rounded-full font-medium">
                Identificando…
              </span>
            </div>
          </div>
        )}
      </div>

      {/* ── Bottom sheets — absolute sobre la camara ── */}
      {mode === 'client' && result && (
        <div className="absolute inset-x-0 bottom-0 z-20 animate-slide-up bg-white rounded-t-3xl shadow-2xl flex flex-col max-h-[60vh]">
          <div className="flex-1 overflow-y-auto overscroll-contain px-5 pt-5 pb-2">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center shrink-0 text-2xl">👤</div>
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
            <p className="text-center text-xs text-gray-400">Navegando al catálogo en 2 s…</p>
          </div>
          <div className="px-5 py-4 border-t border-gray-100 flex gap-2">
            <button onClick={reset} className="flex-1 py-3 rounded-xl border border-gray-200 text-gray-600 text-sm font-medium active:bg-gray-50">
              Cancelar
            </button>
            <button onClick={confirmClient} className="flex-[2] py-3 rounded-xl bg-brand-700 text-white font-semibold active:bg-brand-800">
              Ver catálogo →
            </button>
          </div>
        </div>
      )}

      {mode === 'product' && result && (
        <div className="absolute inset-x-0 bottom-0 z-20 animate-slide-up bg-white rounded-t-3xl shadow-2xl flex flex-col max-h-[65vh]">
          {/* Contenido scrollable */}
          <div className="flex-1 overflow-y-auto overscroll-contain px-5 pt-5 pb-2">
            {/* Nombre y precio */}
            <div className="flex items-start justify-between mb-3">
              <div className="flex-1 min-w-0 pr-3">
                <p className="font-bold text-gray-900 leading-tight">
                  {result.data.nombre ?? result.data.sku}
                </p>
                {result.data.categoria && (
                  <p className="text-xs text-gray-400 mt-0.5">
                    {result.data.categoria}{result.data.marca ? ` · ${result.data.marca}` : ''}
                  </p>
                )}
              </div>
              <p className="text-3xl font-extrabold text-brand-700 shrink-0">
                ${fmt(result.data.precio_venta)}
              </p>
            </div>

            {/* Chips */}
            <div className="flex gap-2 flex-wrap mb-4">
              <span className="bg-gray-100 text-gray-600 text-xs font-medium px-3 py-1 rounded-full">SKU: {result.data.sku}</span>
              <span className="bg-gray-100 text-gray-600 text-xs font-medium px-3 py-1 rounded-full">Talla {result.data.talla}</span>
              <span className="bg-gray-100 text-gray-600 text-xs font-medium px-3 py-1 rounded-full">{result.data.color}</span>
            </div>

            {result.data.descripcion && (
              <p className="text-xs text-gray-400 mb-4 leading-relaxed">{result.data.descripcion}</p>
            )}

            {/* Selector de cantidad */}
            <div className="flex items-center justify-between bg-gray-50 rounded-2xl px-4 py-3">
              <span className="text-sm text-gray-500 font-medium">Cantidad</span>
              <div className="flex items-center gap-4">
                <button onClick={() => setQty(q => Math.max(1, q - 1))}
                  className="w-9 h-9 rounded-full bg-white border border-gray-200 text-gray-700 text-lg font-bold flex items-center justify-center active:bg-gray-100 shadow-sm">−</button>
                <span className="text-xl font-bold text-gray-900 w-6 text-center">{qty}</span>
                <button onClick={() => setQty(q => q + 1)}
                  className="w-9 h-9 rounded-full bg-brand-700 text-white text-lg font-bold flex items-center justify-center active:bg-brand-800 shadow-sm">+</button>
              </div>
            </div>

            {qty > 1 && (
              <p className="text-right text-xs text-gray-400 mt-2">
                Subtotal: <span className="font-semibold text-gray-700">${fmt(result.data.precio_venta * qty)}</span>
              </p>
            )}
          </div>

          {/* Botones siempre visibles */}
          <div className="px-5 py-4 border-t border-gray-100 flex gap-2">
            <button onClick={reset} className="flex-1 py-3 rounded-xl border border-gray-200 text-gray-600 text-sm font-medium active:bg-gray-50">
              Escanear otro
            </button>
            <button onClick={addToCartAndReset} className="flex-[2] py-3 rounded-xl bg-brand-700 text-white font-semibold active:bg-brand-800">
              + Añadir {qty > 1 ? `(${qty})` : ''} al presupuesto
            </button>
          </div>
        </div>
      )}

      {mode === 'error' && result && (
        <div className="absolute inset-x-0 bottom-0 z-20 animate-slide-up bg-white rounded-t-3xl shadow-2xl flex flex-col max-h-[40vh]">
          <div className="flex-1 overflow-y-auto overscroll-contain px-5 pt-5 pb-2">
            <div className="flex items-center gap-3">
              <span className="text-3xl">🤷</span>
              <div>
                <p className="font-semibold text-gray-800">Código no reconocido</p>
                <p className="text-xs text-gray-400 break-all mt-0.5">{result.raw}</p>
              </div>
            </div>
          </div>
          <div className="px-5 py-4 border-t border-gray-100">
            <button onClick={reset} className="w-full py-3 rounded-xl bg-gray-800 text-white font-semibold active:bg-gray-900">
              Intentar de nuevo
            </button>
          </div>
        </div>
      )}

      {/* Barra inferior idle — absolute sobre la camara */}
      {mode === 'idle' && (
        <div className="absolute inset-x-0 bottom-0 z-20 bg-gray-950 px-5 py-3 pb-5">
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
              <button type="submit" className="bg-brand-700 text-white px-4 py-2.5 rounded-xl text-sm font-semibold active:bg-brand-800">
                Buscar
              </button>
              <button type="button" onClick={() => setShowManual(false)} className="text-white/40 px-2 text-sm">✕</button>
            </form>
          ) : (
            <div className="flex gap-2">
              <button onClick={() => setShowManual(true)} className="flex-1 bg-white/10 text-white/70 py-2.5 rounded-xl text-sm active:bg-white/20">
                ✏️ Ingresar código
              </button>
              <button onClick={() => { setClient(null); navigate('/catalog') }} className="flex-1 bg-white/10 text-white/70 py-2.5 rounded-xl text-sm active:bg-white/20">
                📦 Ir al catálogo
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
