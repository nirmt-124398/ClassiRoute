import { forwardRef, useId, type HTMLAttributes } from "react"
import { cn } from "@/lib/utils"

const Skeleton = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("animate-pulse rounded-sm bg-brand-border", className)}
      {...props}
    />
  ),
)
Skeleton.displayName = "Skeleton"

const SkeletonCard = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("rounded-sm border border-brand-border bg-brand-surface p-6", className)}
      {...props}
    >
      <Skeleton className="h-4 w-3/4" />
      <div className="mt-4 space-y-2">
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-5/6" />
      </div>
    </div>
  ),
)
SkeletonCard.displayName = "SkeletonCard"

const SkeletonText = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <Skeleton ref={ref} className={cn("h-4", className)} {...props} />
  ),
)
SkeletonText.displayName = "SkeletonText"

interface SkeletonTableProps extends HTMLAttributes<HTMLDivElement> {
  rows?: number
}

const SkeletonTable = forwardRef<HTMLDivElement, SkeletonTableProps>(
  ({ rows = 5, className, ...props }, ref) => {
    const id = useId()
    const items = Array.from({ length: rows }, (_, i) => `${id}-row-${i}`)
    return (
      <div ref={ref} className={cn("space-y-3", className)} {...props}>
        {items.map((key) => (
          <div key={key} className="flex gap-4">
            <Skeleton className="h-4 w-1/4" />
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-4 w-1/5" />
            <Skeleton className="h-4 w-1/6" />
          </div>
        ))}
      </div>
    )
  },
)
SkeletonTable.displayName = "SkeletonTable"

const SkeletonStat = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("rounded-sm border border-brand-border bg-brand-surface p-6", className)}
      {...props}
    >
      <div className="flex items-center gap-4">
        <Skeleton className="size-10 rounded-full" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-6 w-16" />
        </div>
      </div>
    </div>
  ),
)
SkeletonStat.displayName = "SkeletonStat"

export { Skeleton, SkeletonCard, SkeletonText, SkeletonTable, SkeletonStat }
