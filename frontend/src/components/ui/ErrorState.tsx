import { AlertCircle } from "lucide-react"
import { Card, CardContent } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"

interface ErrorStateProps {
  title?: string
  message: string
  onRetry?: () => void
}

export function ErrorState({ title = "Something went wrong", message, onRetry }: ErrorStateProps) {
  return (
    <Card className="animate-fade-in">
      <CardContent className="flex flex-col items-center justify-center py-16 text-center">
        <div className="mb-4 rounded-full bg-brand-orange/10 p-3">
          <AlertCircle className="h-6 w-6 text-brand-orange" />
        </div>
        <h3 className="font-heading text-base font-semibold text-brand-text">{title}</h3>
        <p className="mt-1 max-w-sm text-sm text-brand-muted font-body">{message}</p>
        {onRetry && (
          <Button variant="outline" onClick={onRetry} className="mt-4">
            Try again
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
