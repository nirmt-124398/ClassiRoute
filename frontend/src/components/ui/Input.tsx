import { forwardRef, type InputHTMLAttributes } from "react"
import { cn } from "@/lib/utils"

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, id, type, ...props }, ref) => {
    return (
      <div className="space-y-1.5">
        {label && (
          <label
            htmlFor={id}
            className="text-sm font-heading font-medium text-brand-text"
          >
            {label}
          </label>
        )}
        <input
          id={id}
          type={type}
          className={cn(
            "flex h-10 w-full rounded-sm border bg-brand-surface px-3 py-2 text-sm font-body text-brand-text placeholder:text-brand-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-orange/50 disabled:cursor-not-allowed disabled:opacity-50",
            error ? "border-red-500" : "border-brand-border",
            className,
          )}
          ref={ref}
          {...props}
        />
        {error && (
          <p className="text-xs text-red-500 font-body">{error}</p>
        )}
      </div>
    )
  },
)
Input.displayName = "Input"

export { Input }
