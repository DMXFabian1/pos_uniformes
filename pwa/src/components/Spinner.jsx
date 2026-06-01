export default function Spinner({ className = '', size = 'md' }) {
  const sizes = { sm: 'w-5 h-5', md: 'w-8 h-8', lg: 'w-12 h-12' }

  return (
    <div className={`flex items-center justify-center ${className}`}>
      <div className={`${sizes[size]} relative`}>
        <div className={`${sizes[size]} rounded-full border-[2.5px] border-surface-200`} />
        <div className={`${sizes[size]} rounded-full border-[2.5px] border-transparent border-t-brand-500 animate-spin absolute inset-0`} />
      </div>
    </div>
  )
}
