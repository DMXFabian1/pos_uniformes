export function Skeleton({ className = '', variant = 'rect' }) {
  const base = 'relative overflow-hidden bg-surface-200/70 rounded-2xl'
  const shimmer = `after:absolute after:inset-0 after:bg-gradient-to-r
    after:from-transparent after:via-white/40 after:to-transparent
    after:animate-shimmer`

  if (variant === 'circle') {
    return <div className={`${base} ${shimmer} rounded-full ${className}`} />
  }

  return <div className={`${base} ${shimmer} ${className}`} />
}

export function CardSkeleton() {
  return (
    <div className="card p-4 space-y-3">
      <div className="flex items-start justify-between">
        <div className="space-y-2 flex-1">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-3 w-1/2" />
        </div>
        <Skeleton className="h-6 w-16" />
      </div>
      <div className="flex gap-2">
        <Skeleton className="h-10 w-14 rounded-xl" />
        <Skeleton className="h-10 w-14 rounded-xl" />
        <Skeleton className="h-10 w-14 rounded-xl" />
        <Skeleton className="h-10 w-14 rounded-xl" />
      </div>
    </div>
  )
}

export function ListSkeleton({ count = 3 }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }, (_, i) => <CardSkeleton key={i} />)}
    </div>
  )
}
