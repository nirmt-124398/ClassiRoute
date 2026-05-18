import { useState, useEffect, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { getSummary, getDailyStats, type Summary, type DailyStats } from "@/api/analytics"
import { ApiError } from "@/api/client"
import { useAuth } from "@/context/AuthContext"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card"
import { SkeletonStat } from "@/components/ui/Skeleton"
import { ErrorState } from "@/components/ui/ErrorState"
import { EmptyState } from "@/components/ui/EmptyState"
import {
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
} from "recharts"
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

const BRAND = {
  orange: "#d97757",
  blue: "#6a9bcc",
  green: "#788c5d",
}

// ─── Custom Recharts tooltips (brand-themed) ──────────────────────────────

function SparklineTooltip({
  active,
  payload,
  label,
  formatter,
}: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
  label?: string
  formatter?: (v: number) => string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-sm border border-brand-border bg-brand-surface px-3 py-2 text-xs shadow-md">
      <p className="text-brand-muted font-body">{label}</p>
      {payload.map((entry) => {
        const label =
          entry.dataKey === "requests"
            ? "Requests"
            : entry.dataKey === "cost_usd"
              ? "Cost"
              : entry.name ?? entry.dataKey ?? "Value"
        return (
          <div key={entry.dataKey ?? entry.name} className="flex items-center justify-between gap-4">
            <span className="text-brand-muted">{label}</span>
            <span
              className="font-heading font-semibold text-brand-text tabular-nums"
              style={{ color: entry.color }}
            >
              {formatter ? formatter(entry.value as number) : entry.value?.toLocaleString()}
            </span>
          </div>
        )
      })}
    </div>
  )
}

function DonutTooltip({
  active,
  payload,
}: {
  active?: boolean
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: any[]
}) {
  if (!active || !payload?.length) return null
  const d = payload[0]
  return (
    <div className="rounded-sm border border-brand-border bg-brand-surface px-3 py-2 text-xs shadow-md">
      <p className="font-heading font-semibold text-brand-text">{d.name}</p>
      <p className="text-brand-muted font-body">
        {d.value?.toLocaleString()} requests
      </p>
    </div>
  )
}

// ─── Page ──────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const { loading: authLoading } = useAuth()
  const navigate = useNavigate()

  const [summary, setSummary] = useState<Summary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  const [dailyStats, setDailyStats] = useState<DailyStats[] | null>(null)

  const fetchSummary = useCallback(() => {
    setLoading(true)
    setError("")
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
  }, [navigate])

  const fetchDailyStats = useCallback(() => {
    getDailyStats()
      .then(setDailyStats)
      .catch(() => {
        // silently swallow — sparklines are supplementary
      })
  }, [])

  useEffect(() => {
    if (authLoading) return
    fetchSummary()
    fetchDailyStats()
  }, [authLoading, fetchSummary, fetchDailyStats])

  // ── Loading ─────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="animate-fade-in">
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <SkeletonStat key="sk-0" />
            <SkeletonStat key="sk-1" />
            <SkeletonStat key="sk-2" />
            <SkeletonStat key="sk-3" />
          </div>
          <Card>
            <CardContent className="p-6">
              <div className="h-4 w-32 rounded-sm bg-brand-border" />
              <div className="mt-4 flex gap-8">
                <div className="h-6 w-16 rounded-sm bg-brand-border" />
                <div className="h-6 w-16 rounded-sm bg-brand-border" />
                <div className="h-6 w-16 rounded-sm bg-brand-border" />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    )
  }

  // ── Error ───────────────────────────────────────────────────────────────

  if (error) {
    return (
      <div className="animate-fade-in">
        <ErrorState message={error} onRetry={fetchSummary} />
      </div>
    )
  }

  // ── Empty ───────────────────────────────────────────────────────────────

  if (!summary) {
    return (
      <div className="animate-fade-in">
        <EmptyState
          icon={Activity}
          title="No data yet"
          description="Start routing requests through your keys to see analytics."
        />
      </div>
    )
  }

  // ── Derived data ────────────────────────────────────────────────────────

  const successPct = summary.success_rate * 100
  const successCls = statColor(successPct)

  const accentForSuccess =
    successPct >= 99 ? BRAND.green : successPct >= 95 ? BRAND.blue : BRAND.orange

  const stats = [
    {
      label: "Total Requests",
      value: summary.total_requests.toLocaleString(),
      icon: Activity,
      accent: BRAND.blue,
      textColor: "text-brand-blue",
      dataKey: "requests",
      formatter: (v: number) => v.toLocaleString(),
    },
    {
      label: "Cost Saved",
      value: `$${summary.cost_saved_vs_always_strong.toFixed(4)}`,
      icon: DollarSign,
      accent: BRAND.green,
      textColor: "text-brand-green",
      dataKey: "cost_usd",
      formatter: (v: number) => `$${v.toFixed(4)}`,
    },
    {
      label: "Avg Latency",
      value: `${summary.avg_latency_ms.toFixed(0)}ms`,
      icon: Gauge,
      accent: BRAND.orange,
      textColor: "text-brand-orange",
      dataKey: "requests",
      formatter: (v: number) => v.toLocaleString(),
    },
    {
      label: "Success Rate",
      value: `${successPct.toFixed(1)}%`,
      icon: CheckCircle,
      accent: accentForSuccess,
      textColor: successCls,
      dataKey: "requests",
      formatter: (v: number) => v.toLocaleString(),
    },
  ]

  const total = summary.by_tier.weak + summary.by_tier.mid + summary.by_tier.strong

  const tierData = [
    { name: "Weak", value: summary.by_tier.weak, color: BRAND.orange },
    { name: "Mid", value: summary.by_tier.mid, color: BRAND.blue },
    { name: "Strong", value: summary.by_tier.strong, color: BRAND.green },
  ]

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="animate-fade-in">
    <div className="space-y-6">
      {/* ── Stat cards with sparkline trends ───────────────────────────── */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat, index) => {
          const Icon = stat.icon
          return (
            <Card key={stat.label} className="animate-fade-in-up" style={{ animationDelay: `${(index + 1) * 50}ms` }}>
              <CardContent className="p-6">
                {/* Header row */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div
                      className="flex size-8 items-center justify-center rounded-full"
                      style={{ backgroundColor: `${stat.accent}1A` }}
                    >
                      <Icon className="h-4 w-4" style={{ color: stat.accent }} />
                    </div>
                    <p className="text-xs font-heading font-medium uppercase tracking-wider text-brand-muted">
                      {stat.label}
                    </p>
                  </div>
                </div>

                {/* Value */}
                <p className={`mt-3 font-heading text-2xl font-bold ${stat.textColor}`}>
                  {stat.value}
                </p>

                {/* Sparkline */}
                {dailyStats && dailyStats.length > 0 && (
                  <div className="mt-2">
                    <ResponsiveContainer width="100%" height={40}>
                      <AreaChart
                        data={dailyStats}
                        margin={{ top: 0, right: 0, left: 0, bottom: 0 }}
                      >
                        <defs>
                          <linearGradient
                            id={`spark-${stat.label}`}
                            x1="0"
                            y1="0"
                            x2="0"
                            y2="1"
                          >
                            <stop
                              offset="0%"
                              stopColor={stat.accent}
                              stopOpacity={0.25}
                            />
                            <stop
                              offset="100%"
                              stopColor={stat.accent}
                              stopOpacity={0}
                            />
                          </linearGradient>
                        </defs>
                        <Tooltip
                          content={<SparklineTooltip formatter={stat.formatter} />}
                          cursor={false}
                        />
                        <Area
                          type="monotone"
                          dataKey={stat.dataKey}
                          stroke={stat.accent}
                          fill={`url(#spark-${stat.label})`}
                          strokeWidth={1.5}
                          dot={false}
                          activeDot={{ r: 3, fill: stat.accent, strokeWidth: 0 }}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* ── Tier distribution (donut + legend + cost summary) ──────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Zap className="h-4 w-4 text-brand-orange" />
            Requests by Tier
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-8">
            {/* Donut chart */}
            <div className="shrink-0">
              <ResponsiveContainer width={140} height={140}>
                <PieChart>
                  <Pie
                    data={tierData}
                    cx="50%"
                    cy="50%"
                    innerRadius={44}
                    outerRadius={64}
                    paddingAngle={2}
                    dataKey="value"
                  >
                    {tierData.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip content={<DonutTooltip />} />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Legend */}
            <div className="space-y-3">
              {tierData.map((tier) => {
                const pct = total > 0 ? ((tier.value / total) * 100).toFixed(1) : "0.0"
                return (
                  <div key={tier.name} className="flex items-center gap-3">
                    <div
                      className="size-3 shrink-0 rounded-full"
                      style={{ backgroundColor: tier.color }}
                    />
                    <div className="flex items-baseline gap-2">
                      <span className="text-sm font-heading font-medium text-brand-text">
                        {tier.name}
                      </span>
                      <span className="text-sm text-brand-muted tabular-nums">
                        {tier.value.toLocaleString()} ({pct}%)
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Cost summary (kept from previous implementation) */}
          <div className="mt-6 grid grid-cols-2 gap-4 border-t border-brand-border pt-4 text-sm">
            <div>
              <span className="font-body text-xs text-brand-muted">Total Cost</span>
              <p className="font-heading font-semibold text-brand-text">
                ${summary.total_cost_usd.toFixed(6)}
              </p>
            </div>
            <div>
              <span className="font-body text-xs text-brand-muted">Cost vs Strong</span>
              <p className="flex items-center gap-1 font-heading font-semibold text-brand-green">
                <ArrowUpRight className="h-3 w-3" />
                ${summary.cost_saved_vs_always_strong.toFixed(4)} saved
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
    </div>
  )
}
