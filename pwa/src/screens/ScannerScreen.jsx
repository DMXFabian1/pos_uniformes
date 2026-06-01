import { useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import Scanner from '../components/Scanner'
import BottomSheet from '../components/BottomSheet'
import { clientsApi } from '../api/clients'
import { catalogApi } from '../api/catalog'
import { useCart } from '../context/CartContext'
import { useToast } from '../components/Toast'

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
  const { show: toast }           = useToast()
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
    toast(`${v.nombre ?? v.sku} T${v.talla} agregado${qty > 1 ? ` (x${qty})` : ''}`)
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
    <div className="relative flex flex-col h-full bg-ink-900">
      <div className="flex-1 relative min-h-0">
        <Scanner onScan={handleScan} active={scanActive} />

        {!hasSheet && history.length > 0 && (
          <div className="absolute top-3 right-3">
            <button
              onClick={() => setShowHistory(h => !h)}
              className="flex items-center gap-1.5 bg-ink-900/70 backdrop-blur-md
                text-white/80 text-xs font-medium px-3.5 py-2.5 rounded-full border border-white/10 touch-target"
            >
              Recientes
              <span className="bg-white/20 text-white text-[10px] rounded-full w-5 h-5
                flex items-center justify-center font-bold">
                {history.length}
              </span>
            </button>

            {showHistory && (
              <div className="absolute top-12 right-0 w-72 bg-ink-900/90 backdrop-blur-lg
                rounded-2xl overflow-hidden shadow-float border border-white/10 mt-1 animate-fade-in">
                {history.map((h, i) => (
                  <button
                    key={i}
                    onClick={() => { setShowHistory(false); processCode(h.raw) }}
                    className="w-full flex items-center gap-3 px-4 py-3 active:bg-white/10
                      border-b border-white/5 last:border-0 text-left touch-target"
                  >
                    <span className="text-base shrink-0">{h.type === 'client' ? '👤' : '📦'}</span>
                    <div className="flex-1 min-w-0">
                      <p className="text-white text-xs font-medium truncate">{h.label}</p>
                      <p className="text-white/40 text-[11px] truncate">{h.subLabel}</p>
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

        {!hasSheet && history.length === 0 && (
          <div className="absolute bottom-4 left-0 right-0 flex flex-col items-center pointer-events-none">
            <p className="text-white/40 text-xs tracking-wide">
              Apunta al QR del cliente o codigo del producto
            </p>
          </div>
        )}

        {mode === 'loading' && (
          <div className="absolute top-0 left-0 right-0">
            <div className="h-1 bg-white/10 overflow-hidden">
              <div className="h-full bg-brand-400 w-1/3 rounded-full"
                style={{ animation: 'loading 1s ease-in-out infinite' }} />
            </div>
            <div className="flex items-center justify-center mt-3">
              <span className="bg-ink-900/70 backdrop-blur-md text-white/80 text-xs px-4 py-2 rounded-full font-medium">
                Identificando...
              </span>
            </div>
          </div>
        )}
      </div>

      {mode === 'idle' && (
        <div className="shrink-0 bg-ink-900 px-5 py-3 pb-5 border-t border-white/5">
          {showManual ? (
            <form onSubmit={submitManual} className="flex gap-2">
              <input
                autoFocus
                type="text"
                value={manualInput}
                onChange={e => setManual(e.target.value)}
                placeholder="Escribe SKU o codigo..."
                className="flex-1 bg-white/10 text-white placeholder-white/30 rounded-2xl px-4 py-3 text-sm outline-none border border-white/10 focus:border-brand-400"
              />
              <button type="submit" className="btn-primary px-5 py-3 text-sm">Buscar</button>
              <button type="button" onClick={() => setShowManual(false)} className="text-white/40 px-2 text-sm active:text-white">✕</button>
            </form>
          ) : (
            <div className="flex gap-2.5">
              <button onClick={() => setShowManual(true)} className="flex-1 bg-white/10 text-white/70 py-3 rounded-2xl text-sm font-medium active:bg-white/20 border border-white/5 touch-target">
                Ingresar codigo
              </button>
              <button onClick={() => { setClient(null); navigate('/catalog') }} className="flex-1 bg-white/10 text-white/70 py-3 rounded-2xl text-sm font-medium active:bg-white/20 border border-white/5 touch-target">
                Ir al catalogo
              </button>
            </div>
          )}
        </div>
      )}

      {mode === 'client' && result && (
        <BottomSheet onClose={reset} maxHeight="50vh">
          <div className="flex-1 overflow-y-auto overscroll-contain px-5 pt-2 pb-2">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-14 h-14 rounded-2xl bg-success-50 border border-success-100 flex items-center justify-center shrink-0 text-2xl">��</div>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-ink-400 uppercase tracking-wide font-semibold">Cliente identificado</p>
                <p className="font-bold text-ink-900 truncate text-lg mt-0.5">{result.data.nombre}</p>
                <p className="text-xs text-ink-500 mt-0.5">{result.data.tipo_cliente} · {result.data.nivel_lealtad}</p>
              </div>
              {result.data.descuento_preferente > 0 && (
                <span className="shrink-0 bg-success-50 text-success-500 border border-success-100 text-xs font-bold px-2.5 py-1.5 rounded-xl">
                  -{result.data.descuento_preferente}%
                </span>
              )}
            </div>
            <p className="text-center text-xs text-ink-400">Navegando al catalogo en 2 s...</p>
          </div>
          <div className="px-5 py-4 border-t border-surface-200 flex gap-3 shrink-0">
            <button onClick={reset} className="btn-secondary flex-1 py-3.5 text-sm">Cancelar</button>
            <button onClick={confirmClient} className="btn-primary flex-[2] py-3.5 text-sm">Ver catalogo</button>
          </div>
        </BottomSheet>
      )}

      {mode === 'product' && result && (
        <BottomSheet onClose={reset} maxHeight="60vh">
          <div className="flex-1 overflow-y-auto overscroll-contain px-5 pt-2 pb-2">
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1 min-w-0 pr-3">
                <p className="font-bold text-ink-900 text-lg leading-tight">{result.data.nombre ?? result.data.sku}</p>
                {result.data.categoria && (
                  <p className="text-xs text-ink-400 mt-1">{result.data.categoria}{result.data.marca ? ` · ${result.data.marca}` : ''}</p>
                )}
              </div>
              <p className="text-3xl font-extrabold text-brand-600 shrink-0">${fmt(result.data.precio_venta)}</p>
            </div>

            <div className="flex gap-2 flex-wrap mb-5">
              <span className="bg-surface-100 text-ink-500 text-xs font-medium px-3 py-1.5 rounded-xl border border-surface-200">SKU: {result.data.sku}</span>
              <span className="bg-surface-100 text-ink-500 text-xs font-medium px-3 py-1.5 rounded-xl border border-surface-200">Talla {result.data.talla}</span>
              <span className="bg-surface-100 text-ink-500 text-xs font-medium px-3 py-1.5 rounded-xl border border-surface-200">{result.data.color}</span>
            </div>

            <div className="flex items-center justify-between bg-surface-100 rounded-2xl px-5 py-4 border border-surface-200">
              <span className="text-sm text-ink-500 font-medium">Cantidad</span>
              <div className="flex items-center gap-5">
                <button onClick={() => setQty(q => Math.max(1, q - 1))}
                  className="w-10 h-10 rounded-full bg-surface-0 border border-surface-300 text-ink-700 text-lg font-bold flex items-center justify-center active:bg-surface-200 shadow-card touch-target">-</button>
                <span className="text-2xl font-bold text-ink-900 w-6 text-center">{qty}</span>
                <button onClick={() => setQty(q => q + 1)}
                  className="w-10 h-10 rounded-full bg-brand-600 text-white text-lg font-bold flex items-center justify-center active:bg-brand-700 shadow-card touch-target">+</button>
              </div>
            </div>
            {qty > 1 && (
              <p className="text-right text-xs text-ink-400 mt-2">
                Subtotal: <span className="font-semibold text-ink-700">${fmt(result.data.precio_venta * qty)}</span>
              </p>
            )}
          </div>
          <div className="px-5 py-4 border-t border-surface-200 flex gap-3 shrink-0">
            <button onClick={reset} className="btn-secondary flex-1 py-3.5 text-sm">Escanear otro</button>
            <button onClick={addToCartAndReset} className="btn-primary flex-[2] py-3.5 text-sm">
              Agregar {qty > 1 ? `(${qty})` : ''} al presupuesto
            </button>
          </div>
        </BottomSheet>
      )}

      {mode === 'error' && result && (
        <BottomSheet onClose={reset} maxHeight="40vh">
          <div className="flex-1 overflow-y-auto overscroll-contain px-5 pt-2 pb-2">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-2xl bg-warning-50 border border-warning-100 flex items-center justify-center text-2xl shrink-0">?</div>
              <div>
                <p className="font-semibold text-ink-900">Codigo no reconocido</p>
                <p className="text-xs text-ink-400 break-all mt-1">{result.raw}</p>
              </div>
            </div>
          </div>
          <div className="px-5 py-4 border-t border-surface-200 shrink-0">
            <button onClick={reset} className="w-full btn-primary py-3.5 text-sm">Intentar de nuevo</button>
          </div>
        </BottomSheet>
      )}
    </div>
  )
}
