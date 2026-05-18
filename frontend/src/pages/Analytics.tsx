import { useState, useEffect, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { getSummary, getRequests, getDailyStats, type Summary, type RequestLog, type DailyStats } from "@/api/analytics"
import { listKeys, type VirtualKey } from "@/api/keys"
import { ApiError } from "@/api/client"
import { useAuth } from "@/context/AuthContext"
import { Button } from "@/components/ui/Button"
import { Badge } from "@/components/ui/Badge"
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/Card"
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/Table"
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/Select"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/Tabs"
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, BarChart, Bar,
  type TooltipValueType,
} from "recharts"
import { SkeletonTable, SkeletonStat } from "@/components/ui/Skeleton"
import { EmptyState } from "@/components/ui/EmptyState"
import { ErrorState } from "@/components/ui/ErrorState"
import {
  Activity,
  DollarSign,
  Gauge,
  CheckCircle,
  Zap,
  AlertCircle,
  RefreshCw,
  ArrowUpRight,
  BarChart3,
  Database,
} from "lucide-react"

function statColor(value: number): string {
  if (value >= 99) return "text-brand-green"
  if (value >= 95) return "text-brand-blue"
  return "text-brand-orange"
}

function SummaryCards({ summary }: { summary: Summary }) {
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
                    <div className="h-2 rounded-full bg-brand-surface">
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
  )
}

function latencyBuckets(requests: RequestLog[]) {
  const thresholds = [0, 50, 100, 200, 500, 1000]
  const labels = ["<50ms", "50-100", "100-200", "200-500", "500-1s", ">1s"]
  const counts = new Array(thresholds.length).fill(0)
  for (const r of requests) {
    const ms = r.latency_ms
    let idx = thresholds.length - 1
    for (let i = 0; i < thresholds.length - 1; i++) {
      if (ms >= thresholds[i] && ms < thresholds[i + 1]) {
        idx = i
        break
      }
    }
    counts[idx]++
  }
  return labels.map((range, i) => ({ range, count: counts[i] }))
}

function DailyUsageChart({ data, metric }: { data: DailyStats[]; metric: "requests" | "cost" }) {
  const lineColor = metric === "requests" ? "#6a9bcc" : "#788c5d"
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2a28" />
        <XAxis
          dataKey="date"
          stroke="#9c9a92"
          fontSize={12}
          tickFormatter={(v: string) => v.slice(5)}
          tickLine={false}
        />
        <YAxis stroke="#9c9a92" fontSize={12} tickLine={false} axisLine={false} />
        <Tooltip
          contentStyle={{
            background: "#1c1c1a",
            border: "1px solid #2a2a28",
            borderRadius: "8px",
            color: "#ededed",
            fontSize: "13px",
          }}
          labelStyle={{ color: "#ededed", fontWeight: 600, marginBottom: 4 }}
          formatter={(value: TooltipValueType | undefined) => [
            metric === "requests" ? Number(value ?? 0).toLocaleString() : `$${Number(value ?? 0).toFixed(4)}`,
            metric === "requests" ? "Requests" : "Cost",
          ]}
        />
        <Line
          type="monotone"
          dataKey={metric}
          stroke={lineColor}
          strokeWidth={2}
          dot={{ r: 3, fill: lineColor, stroke: "none" }}
          activeDot={{ r: 5, fill: lineColor, stroke: "#1c1c1a", strokeWidth: 2 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

function LatencyHistogram({ requests }: { requests: RequestLog[] }) {
  const buckets = latencyBuckets(requests)
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <BarChart3 className="h-4 w-4 text-brand-orange" />
          Latency Distribution
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={buckets} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2a28" vertical={false} />
            <XAxis
              dataKey="range"
              stroke="#9c9a92"
              fontSize={11}
              tickLine={false}
            />
            <YAxis stroke="#9c9a92" fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
            <Tooltip
              contentStyle={{
                background: "#1c1c1a",
                border: "1px solid #2a2a28",
                borderRadius: "8px",
                color: "#ededed",
                fontSize: "13px",
              }}
              itemStyle={{ color: "#d97757" }}
              formatter={(value: TooltipValueType | undefined) => [Number(value ?? 0).toLocaleString(), "Requests"]}
            />
            <Bar dataKey="count" fill="#d97757" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

export default function Analytics() {
  const { loading: authLoading } = useAuth()
  const navigate = useNavigate()
  const [selectedKeyId, setSelectedKeyId] = useState("all")
  const [summary, setSummary] = useState<Summary | null>(null)
  const [requests, setRequests] = useState<RequestLog[]>([])
  const [keys, setKeys] = useState<VirtualKey[]>([])
  const [summaryLoading, setSummaryLoading] = useState(true)
  const [requestsLoading, setRequestsLoading] = useState(true)
  const [dailyStats, setDailyStats] = useState<DailyStats[]>([])
  const [dailyLoading, setDailyLoading] = useState(true)
  const [dailyError, setDailyError] = useState("")
  const [summaryError, setSummaryError] = useState("")
  const [requestsError, setRequestsError] = useState("")
  const [chartMetric, setChartMetric] = useState<"requests" | "cost">("requests")

  useEffect(() => {
    listKeys()
      .then(setKeys)
      .catch(() => {})
  }, [])

  const fetchSummary = useCallback(() => {
    setSummaryLoading(true)
    setSummaryError("")
    getSummary(selectedKeyId === "all" ? undefined : selectedKeyId)
      .then(setSummary)
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) {
          navigate("/login", { replace: true })
          return
        }
        setSummaryError(err instanceof Error ? err.message : "Failed to load")
      })
      .finally(() => setSummaryLoading(false))
  }, [selectedKeyId, navigate])

  const fetchRequests = useCallback(() => {
    setRequestsLoading(true)
    setRequestsError("")
    getRequests(selectedKeyId === "all" ? undefined : selectedKeyId)
      .then(setRequests)
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) {
          navigate("/login", { replace: true })
          return
        }
        setRequestsError(err instanceof Error ? err.message : "Failed to load")
      })
      .finally(() => setRequestsLoading(false))
  }, [selectedKeyId, navigate])

  const fetchDaily = useCallback(() => {
    setDailyLoading(true)
    setDailyError("")
    getDailyStats(selectedKeyId === "all" ? undefined : selectedKeyId)
      .then(setDailyStats)
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) {
          navigate("/login", { replace: true })
          return
        }
        setDailyError(err instanceof Error ? err.message : "Failed to load")
      })
      .finally(() => setDailyLoading(false))
  }, [selectedKeyId, navigate])

  useEffect(() => {
    if (authLoading) return
    listKeys()
      .then(setKeys)
      .catch(() => {})
  }, [authLoading])

  useEffect(() => {
    if (authLoading) return
    fetchSummary()
    fetchRequests()
    fetchDaily()
  }, [authLoading, fetchSummary, fetchRequests, fetchDaily])

  return (
    <div className="animate-fade-in">
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm text-brand-muted font-body">
            Usage statistics and request logs
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select
            value={selectedKeyId}
            onValueChange={setSelectedKeyId}
          >
            <SelectTrigger className="w-48">
              <SelectValue placeholder="All keys" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Keys</SelectItem>
              {keys.map((k) => (
                <SelectItem key={k.key_id} value={k.key_id}>
                  {k.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" size="icon" onClick={() => { fetchSummary(); fetchRequests(); fetchDaily() }}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <Tabs defaultValue="summary">
        <TabsList>
          <TabsTrigger value="summary">Summary</TabsTrigger>
          <TabsTrigger value="daily">Daily Usage</TabsTrigger>
          <TabsTrigger value="logs">Request Logs</TabsTrigger>
        </TabsList>

        <TabsContent value="summary">
          {summaryLoading ? (
            <div className="space-y-6 animate-pulse">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Card key={i}>
                    <CardContent className="p-6">
                      <div className="h-4 w-20 rounded bg-brand-surface" />
                      <div className="mt-3 h-8 w-24 rounded bg-brand-surface" />
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          ) : summaryError ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="mb-4 rounded-full bg-red-50 p-3">
                <AlertCircle className="h-6 w-6 text-red-500" />
              </div>
              <h3 className="font-heading text-base font-semibold text-brand-text">
                Failed to load
              </h3>
              <p className="mt-1 text-sm text-brand-muted font-body">{summaryError}</p>
            </div>
          ) : summary ? (
            <div className="space-y-6">
              <SummaryCards summary={summary} />
              {!requestsLoading && requests.length > 0 && (
                <LatencyHistogram requests={requests} />
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="mb-4 rounded-full bg-brand-surface p-3">
                <Activity className="h-6 w-6 text-brand-muted" />
              </div>
              <h3 className="font-heading text-base font-semibold text-brand-text">
                No data yet
              </h3>
              <p className="mt-1 text-sm text-brand-muted font-body">
                No analytics data available for the selected period.
              </p>
            </div>
          )}
        </TabsContent>

        <TabsContent value="daily">
          {dailyLoading ? (
            <Card>
              <CardContent className="p-6">
                <div className="space-y-6">
                  <SkeletonStat />
                  <SkeletonStat />
                </div>
              </CardContent>
            </Card>
          ) : dailyError ? (
            <ErrorState
              message={dailyError}
              onRetry={fetchDaily}
            />
          ) : dailyStats.length === 0 ? (
            <EmptyState
              icon={BarChart3}
              title="No daily data yet"
              description="Start routing requests to see daily usage trends."
            />
          ) : (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Activity className="h-4 w-4 text-brand-blue" />
                    Daily Usage
                  </CardTitle>
                  <div className="flex items-center gap-1 rounded-lg border border-brand-border bg-brand-surface p-0.5">
                    <button
                      type="button"
                      onClick={() => setChartMetric("requests")}
                      className={`rounded-md px-3 py-1.5 text-xs font-heading font-medium transition-colors ${
                        chartMetric === "requests"
                          ? "bg-brand-orange text-white"
                          : "text-brand-muted hover:text-brand-text"
                      }`}
                    >
                      Requests
                    </button>
                    <button
                      type="button"
                      onClick={() => setChartMetric("cost")}
                      className={`rounded-md px-3 py-1.5 text-xs font-heading font-medium transition-colors ${
                        chartMetric === "cost"
                          ? "bg-brand-orange text-white"
                          : "text-brand-muted hover:text-brand-text"
                      }`}
                    >
                      Cost
                    </button>
                  </div>
                </div>
                <CardDescription>
                  {chartMetric === "requests"
                    ? "Number of routing requests per day"
                    : "Total cost in USD per day"}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <DailyUsageChart data={dailyStats} metric={chartMetric} />
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="logs">
          {requestsLoading ? (
            <Card>
              <CardContent className="p-6">
                <SkeletonTable rows={5} />
              </CardContent>
            </Card>
          ) : requestsError ? (
            <ErrorState
              message={requestsError}
              onRetry={fetchRequests}
            />
          ) : requests.length === 0 ? (
            <EmptyState
              icon={Database}
              title="No request logs"
              description="No requests found for the selected filter."
            />
          ) : (
            <Card>
              <div className="max-h-[480px] overflow-auto">
                <CardContent className="p-0">
                  <Table>
                    <TableHeader className="sticky top-0 z-10 bg-brand-surface">
                      <TableRow>
                        <TableHead>Time</TableHead>
                        <TableHead>Model</TableHead>
                        <TableHead>Tier</TableHead>
                        <TableHead>Confidence</TableHead>
                        <TableHead>Latency</TableHead>
                        <TableHead>Tokens</TableHead>
                        <TableHead>Cost</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Prompt</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {requests.map((r) => (
                        <TableRow key={r.id} className="hover:bg-brand-surface/80">
                          <TableCell className="text-brand-muted text-xs whitespace-nowrap">
                            {new Date(r.created_at).toLocaleString()}
                          </TableCell>
                          <TableCell className="text-xs font-mono max-w-[120px] truncate">
                            {r.model_used}
                          </TableCell>
                          <TableCell>
                            <Badge variant="secondary" className="text-xs">
                              {["Weak", "Mid", "Strong"][r.tier_assigned] ?? r.tier_assigned}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-xs tabular-nums">
                            {(r.confidence * 100).toFixed(0)}%
                          </TableCell>
                          <TableCell className="text-xs tabular-nums">
                            {r.latency_ms}ms
                          </TableCell>
                          <TableCell className="text-xs tabular-nums">
                            {r.input_tokens != null ? `${r.input_tokens}→${r.output_tokens}` : "—"}
                          </TableCell>
                          <TableCell className="text-xs tabular-nums">
                            {r.cost_estimate_usd != null
                              ? `$${r.cost_estimate_usd.toFixed(6)}`
                              : "—"}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant={
                                r.status === "success" ? "success"
                                : r.status === "error" ? "destructive"
                                : "outline"
                              }
                              className="text-xs"
                            >
                              {r.status}
                            </Badge>
                          </TableCell>
                          <TableCell className="max-w-[200px] truncate text-brand-muted text-xs">
                            {r.prompt_preview ?? "—"}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </div>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
    </div>
  )
}
