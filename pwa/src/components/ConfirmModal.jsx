import { createContext, useContext, useState, useCallback } from 'react'

const ConfirmContext = createContext(null)

export function ConfirmProvider({ children }) {
  const [state, setState] = useState(null)

  const confirm = useCallback(({ title, message, confirmLabel = 'Confirmar', cancelLabel = 'Cancelar', danger = false }) => {
    return new Promise(resolve => {
      setState({ title, message, confirmLabel, cancelLabel, danger, resolve })
    })
  }, [])

  function handleConfirm() {
    state?.resolve(true)
    setState(null)
  }

  function handleCancel() {
    state?.resolve(false)
    setState(null)
  }

  return (
    <ConfirmContext.Provider value={{ confirm }}>
      {children}
      {state && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center p-6 animate-fade-in"
          onClick={handleCancel}
        >
          <div className="absolute inset-0 bg-ink-900/40 backdrop-blur-sm" />
          <div
            className="relative bg-surface-0 rounded-3xl p-6 w-full max-w-sm shadow-float animate-pop"
            onClick={e => e.stopPropagation()}
          >
            {state.title && (
              <h3 className="text-lg font-bold text-ink-900 mb-2">{state.title}</h3>
            )}
            {state.message && (
              <p className="text-sm text-ink-500 mb-6 leading-relaxed">{state.message}</p>
            )}
            <div className="flex gap-3">
              <button
                onClick={handleCancel}
                className="btn-secondary flex-1 py-3 text-sm"
              >
                {state.cancelLabel}
              </button>
              <button
                onClick={handleConfirm}
                className={`flex-1 py-3 rounded-2xl font-semibold text-sm transition-all active:scale-[0.98]
                  ${state.danger
                    ? 'bg-danger-500 text-white active:bg-danger-600'
                    : 'btn-primary'
                  }`}
              >
                {state.confirmLabel}
              </button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  )
}

export function useConfirm() {
  return useContext(ConfirmContext)
}
