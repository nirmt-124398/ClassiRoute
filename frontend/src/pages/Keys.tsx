import { useState, useEffect, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import {
  listKeys,
  createKey,
  revokeKey,
  listNvidiaModels,
  listAnthropicModels,
  listGeminiModels,
  type VirtualKey,
  type CreateKeyPayload,
} from "@/api/keys"
import { ApiError } from "@/api/client"
import { useAuth } from "@/context/AuthContext"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Badge } from "@/components/ui/Badge"
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/Table"
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/Dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select"
import { Card, CardContent } from "@/components/ui/Card"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"
import { useToast } from "@/components/ui/Toast"
import { SkeletonTable } from "@/components/ui/Skeleton"
import { EmptyState } from "@/components/ui/EmptyState"
import { ErrorState } from "@/components/ui/ErrorState"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/Tabs"
import { Separator } from "@/components/ui/Separator"
import { Key, Plus, Copy, Check, Trash2, Loader2 } from "lucide-react"

const DEFAULT_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

const PROVIDER_OPTIONS = [
  { value: "openai", label: "OpenAI-compatible" },
  { value: "anthropic", label: "Anthropic" },
  { value: "gemini", label: "Gemini" },
] as const

const defaultForm: CreateKeyPayload = {
  name: "",
  weak_model: "",
  weak_api_key: "",
  weak_base_url: "",
  weak_provider_type: "openai",
  mid_model: "",
  mid_api_key: "",
  mid_base_url: "",
  mid_provider_type: "openai",
  strong_model: "",
  strong_api_key: "",
  strong_base_url: "",
  strong_provider_type: "openai",
}

export default function Keys() {
  const { loading: authLoading } = useAuth()
  const navigate = useNavigate()
  const [keys, setKeys] = useState<VirtualKey[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [dialogOpen, setDialogOpen] = useState(false)
  const [form, setForm] = useState<CreateKeyPayload>(defaultForm)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState("")
  const [createdKey, setCreatedKey] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [revoking, setRevoking] = useState<string | null>(null)
  const { addToast } = useToast()
  const [revokeConfirmKey, setRevokeConfirmKey] = useState<VirtualKey | null>(null)

  const [nvidiaApiKey, setNvidiaApiKey] = useState("")
  const [nvidiaBaseUrl, setNvidiaBaseUrl] = useState(DEFAULT_NVIDIA_BASE_URL)
  const [nvidiaModels, setNvidiaModels] = useState<string[]>([])
  const [anthropicModels, setAnthropicModels] = useState<string[]>([])
  const [geminiModels, setGeminiModels] = useState<string[]>([])
  const [loadingModels, setLoadingModels] = useState(false)
  const [modelsError, setModelsError] = useState("")

  const fetchKeys = useCallback(() => {
    setLoading(true)
    setError("")
    listKeys()
      .then(setKeys)
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) {
          navigate("/login", { replace: true })
          return
        }
        setError(err instanceof Error ? err.message : "Failed to load keys")
      })
      .finally(() => setLoading(false))
  }, [navigate])

  useEffect(() => {
    if (authLoading) return
    fetchKeys()
  }, [authLoading, fetchKeys])

  async function handleLoadModels() {
    if (!nvidiaApiKey) {
      setModelsError("NVIDIA API Key is required.")
      return
    }
    if (!nvidiaBaseUrl) {
      setModelsError("Base URL is required.")
      return
    }
    setLoadingModels(true)
    setModelsError("")
    setNvidiaModels([])
    try {
      const result = await listNvidiaModels({
        api_key: nvidiaApiKey,
        base_url: nvidiaBaseUrl,
      })
      setNvidiaModels(result.models)
      setForm((prev) => ({
        ...prev,
        weak_api_key: nvidiaApiKey,
        weak_base_url: nvidiaBaseUrl,
        weak_provider_type: "openai",
        mid_api_key: nvidiaApiKey,
        mid_base_url: nvidiaBaseUrl,
        mid_provider_type: "openai",
        strong_api_key: nvidiaApiKey,
        strong_base_url: nvidiaBaseUrl,
        strong_provider_type: "openai",
      }))
    } catch (err: unknown) {
      setModelsError(err instanceof Error ? err.message : "Failed to load models")
    } finally {
      setLoadingModels(false)
    }
  }

  async function loadProviderModels(provider: "anthropic" | "gemini", apiKey: string) {
    if (!apiKey) return
    setLoadingModels(true)
    setModelsError("")
    try {
      if (provider === "anthropic") {
        const result = await listAnthropicModels({ api_key: apiKey })
        setAnthropicModels(result.models)
      } else {
        const result = await listGeminiModels({ api_key: apiKey })
        setGeminiModels(result.models)
      }
    } catch (err: unknown) {
      setModelsError(
        err instanceof Error
          ? err.message
          : `Failed to load ${provider === "anthropic" ? "Anthropic" : "Gemini"} models`,
      )
    } finally {
      setLoadingModels(false)
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setFormError("")
    if (!form.name) {
      setFormError("Key name is required.")
      return
    }
    if (!form.weak_model || !form.mid_model || !form.strong_model) {
      setFormError("Please select a model for each tier.")
      return
    }
    if (!form.weak_api_key || !form.mid_api_key || !form.strong_api_key) {
      setFormError("Please provide an API key for each tier.")
      return
    }
    setSubmitting(true)
    try {
      const result = await createKey(form)
      setCreatedKey(result.key)
      addToast({ title: "API key created", variant: "success" })

      // Store key locally for Chat playground usage
      try {
        const stored = JSON.parse(localStorage.getItem("created_keys") || "{}")
        stored[result.key_id] = { key: result.key, name: result.name }
        localStorage.setItem("created_keys", JSON.stringify(stored))
      } catch { /* ignore storage errors */ }

      setForm(defaultForm)
      fetchKeys()
    } catch (err: unknown) {
      if (err instanceof ApiError && typeof err.detail === "object" && err.detail !== null) {
        const d = err.detail as { message?: string; errors?: string[] }
        if (d.errors && d.errors.length > 0) {
          setFormError(d.errors.join("\n"))
        } else if (d.message) {
          setFormError(d.message)
        } else {
          setFormError("Failed to create key")
        }
      } else {
        setFormError(err instanceof Error ? err.message : "Failed to create key")
      }
    } finally {
      setSubmitting(false)
    }
  }

  function handleRevoke(key: VirtualKey) {
    setRevokeConfirmKey(key)
  }

  async function handleConfirmRevoke() {
    if (!revokeConfirmKey) return
    const keyId = revokeConfirmKey.key_id
    setRevoking(keyId)
    try {
      await revokeKey(keyId)
      fetchKeys()
      addToast({ title: "Key revoked", description: `"${revokeConfirmKey.name}" has been revoked.`, variant: "success" })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to revoke key"
      addToast({ title: "Error", description: msg, variant: "error" })
    } finally {
      setRevoking(null)
      setRevokeConfirmKey(null)
    }
  }

  function handleCopy(key: string) {
    navigator.clipboard.writeText(key)
    setCopied(true)
    addToast({ title: "API key copied to clipboard", variant: "info" })
    setTimeout(() => setCopied(false), 2000)
  }

  function handleCloseDialog() {
    setDialogOpen(false)
    setCreatedKey(null)
    setForm(defaultForm)
    setFormError("")
    setNvidiaApiKey("")
    setNvidiaBaseUrl(DEFAULT_NVIDIA_BASE_URL)
    setNvidiaModels([])
    setAnthropicModels([])
    setGeminiModels([])
    setModelsError("")
  }

  function updateField(field: keyof CreateKeyPayload, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  function renderTierSection(tierPrefix: "weak" | "mid" | "strong") {
    const providerType = form[`${tierPrefix}_provider_type`] ?? "openai"
    const knownModels =
      providerType === "anthropic"
        ? anthropicModels
        : providerType === "gemini"
          ? geminiModels
          : providerType === "openai"
            ? nvidiaModels
            : undefined
    const isOpenAI = providerType === "openai"

    const modelField = `${tierPrefix}_model` as keyof CreateKeyPayload
    const apiKeyField = `${tierPrefix}_api_key` as keyof CreateKeyPayload
    const baseUrlField = `${tierPrefix}_base_url` as keyof CreateKeyPayload
    const providerField = `${tierPrefix}_provider_type` as keyof CreateKeyPayload

    return (
      <div className="space-y-3">
        <Select
          value={providerType}
          onValueChange={(val) => updateField(providerField, val)}
        >
          <SelectTrigger>
            <SelectValue placeholder="Select provider" />
          </SelectTrigger>
          <SelectContent>
            {PROVIDER_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {knownModels && knownModels.length > 0 ? (
          <Select
            value={form[modelField]}
            onValueChange={(val) => updateField(modelField, val)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Select a model" />
            </SelectTrigger>
            <SelectContent>
              {knownModels.map((m) => (
                <SelectItem key={m} value={m}>
                  {m}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <Input
            id={`${tierPrefix}-model`}
            label="Model"
            placeholder="Type a model name or load models above"
            value={form[modelField]}
            onChange={(e) => updateField(modelField, e.target.value)}
          />
        )}

        <Input
          id={`${tierPrefix}-api-key`}
          label="API Key"
          type="password"
          placeholder={
            isOpenAI ? "sk-..." : providerType === "anthropic" ? "sk-ant-..." : "AIza..."
          }
          value={form[apiKeyField]}
          onChange={(e) => updateField(apiKeyField, e.target.value)}
        />
        {(providerType === "anthropic" || providerType === "gemini") && (
          <Button
            type="button"
            variant="outline"
            onClick={() => loadProviderModels(providerType, form[apiKeyField] ?? "")}
            disabled={!form[apiKeyField] || loadingModels}
          >
            {loadingModels ? (
              <span className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading models...
              </span>
            ) : (
              `Load ${providerType === "anthropic" ? "Anthropic" : "Gemini"} models`
            )}
          </Button>
        )}

        {isOpenAI && (
          <Input
            id={`${tierPrefix}-base-url`}
            label="Base URL"
            placeholder="https://api.openai.com/v1"
            value={form[baseUrlField]}
            onChange={(e) => updateField(baseUrlField, e.target.value)}
          />
        )}
      </div>
    )
  }

  if (loading) {
    return (
      <div className="animate-fade-in">
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="h-8 w-32 rounded bg-brand-surface" />
            <div className="h-10 w-28 rounded bg-brand-surface" />
          </div>
          <SkeletonTable rows={5} />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="animate-fade-in">
        <ErrorState
          title="Failed to load keys"
          message={error}
          onRetry={fetchKeys}
        />
      </div>
    )
  }

  return (
    <div className="animate-fade-in">
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-brand-muted font-body">
            Manage your virtual API keys
          </p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={(open) => {
          if (!open) handleCloseDialog()
          else setDialogOpen(true)
        }}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4" />
              Create Key
            </Button>
          </DialogTrigger>
          <DialogContent className="max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Create Virtual Key</DialogTitle>
              <DialogDescription>
                Configure routing tiers and provider credentials.
              </DialogDescription>
            </DialogHeader>

            {createdKey ? (
              <div className="space-y-4">
                <div className="rounded-sm border border-brand-green/30 bg-brand-green/5 p-4">
                  <p className="text-sm font-heading font-semibold text-brand-green">
                    Key Created Successfully
                  </p>
                  <p className="mt-1 text-xs text-brand-muted font-body">
                    Copy this key now. You will not be able to see it again.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <code className="flex-1 truncate rounded-sm border border-brand-border bg-brand-surface px-3 py-2 font-mono text-xs">
                    {createdKey}
                  </code>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => handleCopy(createdKey)}
                  >
                    {copied ? (
                      <Check className="h-4 w-4 text-brand-green" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                </div>
                <Button className="w-full" onClick={handleCloseDialog}>
                  Done
                </Button>
              </div>
            ) : (
              <form onSubmit={handleCreate} className="space-y-4">
                {formError && (
                  <div className="rounded-sm border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600 font-body whitespace-pre-wrap">
                    {formError}
                  </div>
                )}

                <Input
                  id="key-name"
                  label="Key Name"
                  placeholder="My API Key"
                  value={form.name}
                  onChange={(e) => updateField("name", e.target.value)}
                />

                <div className="rounded-sm border border-brand-border bg-brand-surface/30 p-3 space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-heading font-medium uppercase tracking-wider text-brand-muted">
                      NVIDIA NIM Credentials
                    </p>
                    <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                      Quick-fill
                    </Badge>
                  </div>
                  <p className="text-xs text-brand-muted font-body">
                    Fill in once to auto-populate all three tiers with OpenAI-compatible settings.
                  </p>

                  <Input
                    id="nvidia-api-key"
                    label="NVIDIA API Key"
                    placeholder="nvapi-..."
                    type="password"
                    value={nvidiaApiKey}
                    onChange={(e) => setNvidiaApiKey(e.target.value)}
                  />

                  <Input
                    id="nvidia-base-url"
                    label="Base URL"
                    placeholder="https://integrate.api.nvidia.com/v1"
                    value={nvidiaBaseUrl}
                    onChange={(e) => {
                      setNvidiaBaseUrl(e.target.value)
                      setNvidiaModels([])
                    }}
                  />

                  {modelsError && (
                    <p className="text-xs text-red-500 font-body">{modelsError}</p>
                  )}

                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleLoadModels}
                    disabled={loadingModels}
                    className="w-full"
                  >
                    {loadingModels ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Loading Models…
                      </>
                    ) : nvidiaModels.length > 0 ? (
                      "Reload Models"
                    ) : (
                      "Load Models"
                    )}
                  </Button>

                  {nvidiaModels.length > 0 && (
                    <p className="text-xs text-brand-muted font-body">
                      {nvidiaModels.length} models available
                    </p>
                  )}
                </div>

                <Separator />

                <Tabs defaultValue="weak" className="w-full">
                  <TabsList className="w-full grid grid-cols-3">
                    <TabsTrigger value="weak">
                      Weak
                      {form.weak_model && form.weak_api_key && (
                        <span className="ml-1.5 text-brand-green">✓</span>
                      )}
                    </TabsTrigger>
                    <TabsTrigger value="mid">
                      Mid
                      {form.mid_model && form.mid_api_key && (
                        <span className="ml-1.5 text-brand-green">✓</span>
                      )}
                    </TabsTrigger>
                    <TabsTrigger value="strong">
                      Strong
                      {form.strong_model && form.strong_api_key && (
                        <span className="ml-1.5 text-brand-green">✓</span>
                      )}
                    </TabsTrigger>
                  </TabsList>
                  <TabsContent value="weak" className="space-y-3">
                    {renderTierSection("weak")}
                  </TabsContent>
                  <TabsContent value="mid" className="space-y-3">
                    {renderTierSection("mid")}
                  </TabsContent>
                  <TabsContent value="strong" className="space-y-3">
                    {renderTierSection("strong")}
                  </TabsContent>
                </Tabs>

                <div className="flex justify-end gap-2 pt-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleCloseDialog}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    disabled={submitting}
                  >
                    {submitting ? "Creating…" : "Create Key"}
                  </Button>
                </div>
              </form>
            )}
          </DialogContent>
        </Dialog>
      </div>

      {keys.length === 0 ? (
        <EmptyState
          icon={Key}
          title="No API keys yet"
          description="Create your first API key to get started"
          action={{ label: "Create Key", onClick: () => setDialogOpen(true) }}
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Weak</TableHead>
                  <TableHead>Mid</TableHead>
                  <TableHead>Strong</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Last Used</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {keys.map((k) => (
                  <TableRow key={k.key_id}>
                    <TableCell className="font-heading font-medium">
                      {k.name}
                    </TableCell>
                    <TableCell className="text-brand-muted text-xs font-mono max-w-[120px] truncate">
                      {k.weak_model}
                    </TableCell>
                    <TableCell className="text-brand-muted text-xs font-mono max-w-[120px] truncate">
                      {k.mid_model}
                    </TableCell>
                    <TableCell className="text-brand-muted text-xs font-mono max-w-[120px] truncate">
                      {k.strong_model}
                    </TableCell>
                    <TableCell>
                      <Badge variant={k.is_active ? "success" : "destructive"}>
                        {k.is_active ? "Active" : "Revoked"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-brand-muted text-xs whitespace-nowrap">
                      {new Date(k.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-brand-muted text-xs whitespace-nowrap">
                      {k.last_used_at
                        ? new Date(k.last_used_at).toLocaleDateString()
                        : "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      {k.is_active && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRevoke(k)}
                          disabled={revoking === k.key_id}
                          className="text-red-500 hover:text-red-600 hover:bg-red-50"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <ConfirmationDialog
        open={revokeConfirmKey !== null}
        onOpenChange={(open) => { if (!open) setRevokeConfirmKey(null) }}
        title="Revoke API Key"
        description={`Are you sure you want to revoke "${revokeConfirmKey?.name ?? ""}"? This action cannot be undone.`}
        confirmLabel="Revoke"
        variant="danger"
        onConfirm={handleConfirmRevoke}
      />
    </div>
    </div>
  )
}
