import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { getSummary, type Summary } from "@/api/analytics"
import { ApiError } from "@/api/client"
import { useAuth } from "@/context/AuthContext"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card"
import { Badge } from "@/components/ui/Badge"
import {
  Activity,
  DollarSign,
  Gauge,
  CheckCircle,
  Zap,
  ArrowUpRight,
} from "lucide-react"

function statColor(value: number): string {
  if (value >= 99) return "text-brand-green"
  if (value >= 95) return "text-brand-blue"
  return "text-brand-orange"
}

export default function Dashboard() {
  const { loading: authLoading } = useAuth()
  const navigate = useNavigate()
  const [summary, setSummary] = useState<Summary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    if (authLoading) return
    getSummary()
      .then(setSummary)
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) {
          navigate("/login", { replace: true })
          return
        }
        setError(err instanceof Error ? err.message : "Failed to load")
      })
      .finally(() => setLoading(false))
  }, [authLoading, navigate])

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <div className="h-4 w-20 rounded bg-brand-border" />
                <div className="mt-3 h-8 w-24 rounded bg-brand-border" />
              </CardContent>
            </Card>
          ))}
        </div>
        <Card>
          <CardContent className="p-6">
                <div className="h-4 w-32 rounded bg-brand-border" />
            <div className="mt-4 flex gap-8">
              <div className="h-6 w-16 rounded bg-brand-border" />
              <div className="h-6 w-16 rounded bg-brand-border" />
              <div className="h-6 w-16 rounded bg-brand-border" />
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="mb-4 rounded-full bg-red-950/30 p-3">
          <Activity className="h-6 w-6 text-red-400" />
        </div>
        <h3 className="font-heading text-base font-semibold text-brand-text">
          Failed to load
        </h3>
        <p className="mt-1 text-sm text-brand-muted font-body">{error}</p>
      </div>
    )
  }

  if (!summary) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="mb-4 rounded-full bg-brand-border p-3">
          <Activity className="h-6 w-6 text-brand-muted" />
        </div>
        <h3 className="font-heading text-base font-semibold text-brand-text">
          No data yet
        </h3>
        <p className="mt-1 text-sm text-brand-muted font-body">
          Start routing requests through your keys to see analytics.
        </p>
      </div>
    )
  }

  const stats = [
    {
      label: "Total Requests",
      value: summary.total_requests.toLocaleString(),
      icon: Activity,
      color: "text-brand-blue",
    },
    {
      label: "Cost Saved",
      value: `$${summary.cost_saved_vs_always_strong.toFixed(4)}`,
      icon: DollarSign,
      color: "text-brand-green",
    },
    {
      label: "Avg Latency",
      value: `${summary.avg_latency_ms.toFixed(0)}ms`,
      icon: Gauge,
      color: "text-brand-orange",
    },
    {
      label: "Success Rate",
      value: `${(summary.success_rate * 100).toFixed(1)}%`,
      icon: CheckCircle,
      color: statColor(summary.success_rate * 100),
    },
  ]

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => {
          const Icon = stat.icon
          return (
            <Card key={stat.label}>
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-heading font-medium uppercase tracking-wider text-brand-muted">
                    {stat.label}
                  </p>
                  <Icon className={`h-4 w-4 ${stat.color}`} />
                </div>
                <p className={`mt-2 font-heading text-2xl font-bold ${stat.color}`}>
                  {stat.value}
                </p>
              </CardContent>
            </Card>
          )
        })}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Zap className="h-4 w-4 text-brand-orange" />
            Requests by Tier
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {(
              [
                { tier: "Weak", count: summary.by_tier.weak },
                { tier: "Mid", count: summary.by_tier.mid },
                { tier: "Strong", count: summary.by_tier.strong },
              ] as const
            ).map(({ tier, count }) => {
              const total = summary.by_tier.weak + summary.by_tier.mid + summary.by_tier.strong
              const pct = total > 0 ? ((count / total) * 100).toFixed(1) : "0.0"
              return (
                <div key={tier} className="flex items-center gap-4">
                  <Badge variant="secondary" className="w-16 justify-center">
                    {tier}
                  </Badge>
                  <div className="flex-1">
                    <div className="h-2 rounded-full bg-brand-border">
                      <div
                        className="h-2 rounded-full bg-brand-orange/70 transition-all"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                  <span className="text-sm font-body text-brand-muted tabular-nums">
                    {count.toLocaleString()} ({pct}%)
                  </span>
                </div>
              )
            })}
          </div>

          <div className="mt-6 grid grid-cols-2 gap-4 border-t border-brand-border pt-4 text-sm">
            <div>
              <span className="font-heading text-brand-muted">Total Cost</span>
              <p className="font-heading font-semibold text-brand-text">
                ${summary.total_cost_usd.toFixed(6)}
              </p>
            </div>
            <div>
              <span className="font-heading text-brand-muted">Cost vs Strong</span>
              <p className="flex items-center gap-1 font-heading font-semibold text-brand-green">
                <ArrowUpRight className="h-3 w-3" />
                ${summary.cost_saved_vs_always_strong.toFixed(4)} saved
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
