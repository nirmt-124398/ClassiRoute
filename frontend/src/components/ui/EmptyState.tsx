import { type LucideIcon } from "lucide-react"
import { Card, CardContent } from "./Card"
import { Button } from "./Button"

export interface EmptyStateAction {
  label: string
  onClick: () => void
}

export interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description: string
  action?: EmptyStateAction
}

function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center justify-center py-12 text-center">
        <Icon className="mb-4 size-12 text-brand-muted" />
        <h3 className="font-heading text-base font-semibold">{title}</h3>
        <p className="mt-1 text-sm text-brand-muted font-body">{description}</p>
        {action && (
          <Button variant="default" className="mt-4" onClick={action.onClick}>
            {action.label}
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

export { EmptyState }
