/**
 * Pantalla de inicio operativo — escaner dual:
 * - QR de cliente → vincula cliente al carrito y va a catalogo
 * - Codigo de barras de producto → consulta precio rapido
 */
import { useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import Scanner from '../components/Scanner'
import Spinner from '../components/Spinner'
import { clientsApi } from '../api/clients'
import { catalogApi } from '../api/catalog'
import { useCart } from '../context/CartContext'

export default function ScannerScreen() {
  const [mode, setMode]       = useState('waiting') // waiting | loading | client | product | error
  const [result, setResult]   = useState(null)
  const [scanActive, setScan] = useState(true)
  const { setClient }         = useCart()
  const navigate              = useNavigate()
  const processing            = useRef(false)

  const handleScan = useCallback(async (raw) => {
    if (processing.current) return
    processing.current = true
    setScan(false)
    setMode('loading')

    try {
      // Intentar como QR de cliente primero
      const cliente = await clientsApi.byQr(raw).catch(() => null)
      if (cliente) {
        setResult({ type: 'client', data: cliente })
        setMode('client')
        return
      }

      // Intentar como SKU de producto
      const variante = await catalogApi.bySku(raw).catch(() => null)
      if (variante) {
        setResult({ type: 'product', data: variante })
        setMode('product')
        return
      }

      setResult({ type: 'error', raw })
      setMode('error')
    } finally {
      processing.current = false
    }
  }, [])

  function reset() {
    setMode('waiting')
    setResult(null)
    setScan(true)
    processing.current = false
  }

  function goWithClient() {
    setClient({ id: result.data.id, nombre: result.data.nombre, codigo_cliente: result.data.codigo_cliente })
    navigate('/catalog')
  }

  function goWithoutClient() {
    setClient(null)
    navigate('/catalog')
  }

  return (
    <div className="flex flex-col h-full bg-gray-900">
      {/* Scanner */}
      <div className="flex-1 relative">
        <Scanner onScan={handleScan} active={scanActive} />

        {/* Overlay de estado */}
        {mode !== 'waiting' && (
          <div className="absolute inset-0 bg-black/70 flex items-center justify-center p-6">
            {mode === 'loading' && (
              <div className="bg-white rounded-2xl p-8 flex flex-col items-center gap-3">
                <Spinner />
                <p className="text-gray-600 text-sm">Identificando…</p>
              </div>
            )}

            {mode === 'client' && (
              <div className="bg-white rounded-2xl p-6 w-full max-w-xs">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center">
                    <span className="text-2xl">👤</span>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide">Cliente identificado</p>
                    <p className="font-bold text-gray-900">{result.data.nombre}</p>
                    <p className="text-xs text-gray-500">{result.data.tipo_cliente} · {result.data.nivel_lealtad}</p>
                  </div>
                </div>
                {result.data.descuento_preferente > 0 && (
                  <div className="bg-green-50 rounded-xl px-3 py-2 mb-4 text-center">
                    <p className="text-green-700 text-sm font-medium">
                      Descuento preferente: {result.data.descuento_preferente}%
                    </p>
                  </div>
                )}
                <button
                  onClick={goWithClient}
                  className="w-full bg-brand-700 text-white font-semibold py-3 rounded-xl mb-2 active:bg-brand-800"
                >
                  Ver catálogo con este cliente
                </button>
                <button
                  onClick={reset}
                  className="w-full text-gray-500 py-2 text-sm"
                >
                  Escanear otro código
                </button>
              </div>
            )}

            {mode === 'product' && (
              <div className="bg-white rounded-2xl p-6 w-full max-w-xs">
                <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Precio rápido</p>
                <p className="text-sm text-gray-600 mb-1">{result.data.sku}</p>
                <p className="text-sm text-gray-500 mb-3">{result.data.talla} · {result.data.color}</p>
                <p className="text-4xl font-bold text-brand-700 mb-6">
                  ${Number(result.data.precio_venta).toLocaleString('es-MX', { minimumFractionDigits: 2 })}
                </p>
                <button
                  onClick={reset}
                  className="w-full bg-brand-700 text-white font-semibold py-3 rounded-xl active:bg-brand-800"
                >
                  Escanear otro
                </button>
              </div>
            )}

            {mode === 'error' && (
              <div className="bg-white rounded-2xl p-6 w-full max-w-xs text-center">
                <p className="text-4xl mb-3">🤷</p>
                <p className="font-semibold text-gray-800 mb-1">Código no reconocido</p>
                <p className="text-sm text-gray-500 mb-4 break-all">{result.raw}</p>
                <button
                  onClick={reset}
                  className="w-full bg-gray-800 text-white font-semibold py-3 rounded-xl"
                >
                  Intentar de nuevo
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Barra inferior de acciones rapidas */}
      <div className="bg-gray-900 px-6 py-4 pb-6">
        <p className="text-white/40 text-xs text-center mb-3">
          Apunta la cámara al QR del cliente o al código del producto
        </p>
        <button
          onClick={goWithoutClient}
          className="w-full bg-white/10 text-white/80 py-3 rounded-xl text-sm font-medium active:bg-white/20"
        >
          Ir al catálogo sin escanear
        </button>
      </div>
    </div>
  )
}
