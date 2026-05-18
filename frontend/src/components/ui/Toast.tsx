import {
  forwardRef,
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ComponentPropsWithoutRef,
  type ElementRef,
  type ReactNode,
} from "react"
import * as ToastPrimitives from "@radix-ui/react-toast"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

// ─── Types ────────────────────────────────────────────────────────────────

type ToastVariant = "success" | "error" | "info" | "warning"

interface ToastData {
  id: string
  title?: string
  description?: string
  variant?: ToastVariant
  open: boolean
}

interface ToastContextType {
  toasts: ToastData[]
  addToast: (toast: Omit<ToastData, "id" | "open">) => void
  dismissToast: (id: string) => void
}

// ─── Context ──────────────────────────────────────────────────────────────

const ToastContext = createContext<ToastContextType | null>(null)

// ─── Variant styles ───────────────────────────────────────────────────────

const variantAccent: Record<ToastVariant, string> = {
  success: "border-l-[3px] border-brand-green",
  error: "border-l-[3px] border-red-400",
  info: "border-l-[3px] border-brand-blue",
  warning: "border-l-[3px] border-brand-orange",
}

const variantTitleColor: Record<ToastVariant, string> = {
  success: "text-brand-green",
  error: "text-red-400",
  info: "text-brand-blue",
  warning: "text-brand-orange",
}

// ─── Primitive wrappers ───────────────────────────────────────────────────

const ToastViewport = forwardRef<
  ElementRef<typeof ToastPrimitives.Viewport>,
  ComponentPropsWithoutRef<typeof ToastPrimitives.Viewport>
>(({ className, ...props }, ref) => (
  <ToastPrimitives.Viewport
    ref={ref}
    className={cn(
      "fixed top-4 right-4 z-[100] flex max-h-screen w-full max-w-sm flex-col gap-2 outline-none",
      className,
    )}
    {...props}
  />
))
ToastViewport.displayName = ToastPrimitives.Viewport.displayName

const ToastRoot = forwardRef<
  ElementRef<typeof ToastPrimitives.Root>,
  ComponentPropsWithoutRef<typeof ToastPrimitives.Root>
>(({ className, ...props }, ref) => (
  <ToastPrimitives.Root
    ref={ref}
    className={cn(
      "group pointer-events-auto relative flex w-full items-start justify-between gap-3 overflow-hidden rounded-md border border-brand-border bg-brand-surface p-4 shadow-lg",
      "data-[state=open]:animate-in data-[state=closed]:animate-out",
      "data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      "data-[state=closed]:slide-out-to-right-full data-[state=open]:slide-in-from-right-full",
      "data-[swipe=end]:translate-x-[var(--radix-toast-swipe-end-x)]",
      "data-[swipe=move]:translate-x-[var(--radix-toast-swipe-move-x)]",
      "data-[swipe=cancel]:translate-x-0",
      "transition-[transform,opacity] duration-200 ease-in-out",
      className,
    )}
    {...props}
  />
))
ToastRoot.displayName = ToastPrimitives.Root.displayName

const ToastTitle = forwardRef<
  ElementRef<typeof ToastPrimitives.Title>,
  ComponentPropsWithoutRef<typeof ToastPrimitives.Title>
>(({ className, ...props }, ref) => (
  <ToastPrimitives.Title
    ref={ref}
    className={cn("text-sm font-medium leading-tight", className)}
    {...props}
  />
))
ToastTitle.displayName = ToastPrimitives.Title.displayName

const ToastDescription = forwardRef<
  ElementRef<typeof ToastPrimitives.Description>,
  ComponentPropsWithoutRef<typeof ToastPrimitives.Description>
>(({ className, ...props }, ref) => (
  <ToastPrimitives.Description
    ref={ref}
    className={cn("text-sm text-brand-muted", className)}
    {...props}
  />
))
ToastDescription.displayName = ToastPrimitives.Description.displayName

const ToastClose = forwardRef<
  ElementRef<typeof ToastPrimitives.Close>,
  ComponentPropsWithoutRef<typeof ToastPrimitives.Close>
>(({ className, ...props }, ref) => (
  <ToastPrimitives.Close
    ref={ref}
    className={cn(
      "absolute right-2 top-2 rounded-sm p-0.5 text-brand-muted opacity-0 transition-opacity hover:text-brand-text focus:opacity-100 focus:outline-none focus:ring-2 focus:ring-brand-orange/50 group-hover:opacity-100",
      className,
    )}
    toast-close=""
    {...props}
  >
    <X className="h-3.5 w-3.5" />
  </ToastPrimitives.Close>
))
ToastClose.displayName = ToastPrimitives.Close.displayName

// ─── ToastProvider ────────────────────────────────────────────────────────

const REMOVE_DELAY = 300 // ms to allow close animation before unmount

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastData[]>([])

  const addToast = useCallback((data: Omit<ToastData, "id" | "open">) => {
    const id = Math.random().toString(36).slice(2, 9)
    setToasts((prev) => [...prev, { ...data, id, open: true }])
  }, [])

  const dismissToast = useCallback((id: string) => {
    // First set open=false to trigger the close animation
    setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, open: false } : t)))
    // Then remove from state after the animation finishes
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, REMOVE_DELAY)
  }, [])

  // Register global toast() handler
  useEffect(() => {
    globalAddToast = addToast
    return () => {
      globalAddToast = null
    }
  }, [addToast])

  return (
    <ToastContext.Provider value={{ toasts, addToast, dismissToast }}>
      <ToastPrimitives.Provider swipeDirection="right">
        {children}
        <ToastViewport>
          {toasts.map((toast) => {
            const variant = toast.variant ?? "info"
            return (
              <ToastRoot
                key={toast.id}
                open={toast.open}
                duration={4000}
                onOpenChange={(open) => {
                  if (!open) dismissToast(toast.id)
                }}
                className={variantAccent[variant]}
              >
                <div className="flex flex-col gap-1 pr-4">
                  {toast.title && (
                    <ToastTitle className={variantTitleColor[variant]}>
                      {toast.title}
                    </ToastTitle>
                  )}
                  {toast.description && (
                    <ToastDescription>{toast.description}</ToastDescription>
                  )}
                </div>
                <ToastClose />
              </ToastRoot>
            )
          })}
        </ToastViewport>
      </ToastPrimitives.Provider>
    </ToastContext.Provider>
  )
}

// ─── Hook ─────────────────────────────────────────────────────────────────

export function useToast(): ToastContextType {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error("useToast must be used within a <ToastProvider>")
  }
  return context
}

// ─── Global imperative toast() ────────────────────────────────────────────

let globalAddToast: ((data: Omit<ToastData, "id" | "open">) => void) | null = null

export function toast(data: Omit<ToastData, "id" | "open">) {
  globalAddToast?.(data)
}
