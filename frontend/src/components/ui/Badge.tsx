import { type HTMLAttributes } from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-sm px-2.5 py-0.5 text-xs font-heading font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "bg-brand-orange/10 text-brand-orange border border-brand-orange/20",
        secondary: "bg-brand-surface text-brand-muted",
        outline: "border border-brand-border text-brand-muted",
        success: "bg-brand-green/10 text-brand-green border border-brand-green/20",
        destructive: "bg-red-950/30 text-red-400 border border-red-800",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
)

export interface BadgeProps
  extends HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
