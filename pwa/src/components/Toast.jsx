import { createContext, useContext, useState, useCallback, useRef } from 'react'

const ToastContext = createContext(null)

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const idRef = useRef(0)

  const show = useCallback((message, { type = 'success', duration = 2500 } = {}) => {
    const id = ++idRef.current
    setToasts(prev => [...prev, { id, message, type, leaving: false }])
    setTimeout(() => {
      setToasts(prev => prev.map(t => t.id === id ? { ...t, leaving: true } : t))
      setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 300)
    }, duration)
  }, [])

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <div className="fixed bottom-24 left-4 right-4 z-[100] flex flex-col items-center gap-2 pointer-events-none">
        {toasts.map(t => (
          <div
            key={t.id}
            className={`px-5 py-3 rounded-2xl shadow-toast text-sm font-medium
              max-w-[320px] text-center pointer-events-auto
              ${t.leaving ? 'animate-toast-out' : 'animate-toast-in'}
              ${t.type === 'success' ? 'bg-success-600 text-white' : ''}
              ${t.type === 'error' ? 'bg-danger-500 text-white' : ''}
              ${t.type === 'info' ? 'bg-ink-900 text-white' : ''}
              ${t.type === 'warning' ? 'bg-warning-500 text-white' : ''}
            `}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  return useContext(ToastContext)
}
