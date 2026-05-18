import {
  forwardRef,
  useCallback,
  useRef,
  type TextareaHTMLAttributes,
} from "react"
import { Send } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "./Button"

export interface ChatInputProps
  extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  onSend?: () => void
}

const ChatInput = forwardRef<HTMLTextAreaElement, ChatInputProps>(
  ({ className, onSend, value, onChange, onKeyDown, ...props }, forwardedRef) => {
    const internalRef = useRef<HTMLTextAreaElement>(null)

    const ref = useCallback(
      (node: HTMLTextAreaElement | null) => {
        internalRef.current = node
        if (typeof forwardedRef === "function") forwardedRef(node)
        else if (forwardedRef) forwardedRef.current = node
      },
      [forwardedRef],
    )

    const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const textarea = e.currentTarget
      textarea.style.height = "auto"
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`
      onChange?.(e)
    }

    const handleKeyDown = (
      e: React.KeyboardEvent<HTMLTextAreaElement>,
    ) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault()
        onSend?.()
      }
      onKeyDown?.(e)
    }

    const strValue = value?.toString() ?? ""
    const canSend = !props.disabled && strValue.trim().length > 0

    return (
      <div className="flex flex-col">
        <div className="relative">
          <textarea
            ref={ref}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            rows={1}
            className={cn(
              "w-full resize-none rounded-sm border bg-brand-surface pr-12 text-sm font-body text-brand-text placeholder:text-brand-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-orange/50 disabled:cursor-not-allowed disabled:opacity-50",
              "min-h-[40px]",
              "border-brand-border",
              className,
            )}
            {...props}
          />
          <Button
            type="button"
            size="icon"
            variant="default"
            disabled={!canSend}
            onClick={onSend}
            className="absolute bottom-1.5 right-1.5 h-7 w-7"
          >
            <Send className="h-3.5 w-3.5" />
          </Button>
        </div>
        <span className="mt-1 text-xs text-brand-muted font-body">
          Enter to send · Shift+Enter for new line
        </span>
      </div>
    )
  },
)
ChatInput.displayName = "ChatInput"

export { ChatInput }
