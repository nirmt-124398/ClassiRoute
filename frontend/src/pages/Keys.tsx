import { useState, useEffect, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { listKeys, createKey, revokeKey, listNvidiaModels, type VirtualKey, type CreateKeyPayload } from "@/api/keys"
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
import { Key, Plus, Copy, Check, Trash2, Loader2 } from "lucide-react"

const DEFAULT_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

const defaultForm: CreateKeyPayload = {
  name: "",
  weak_model: "",
  weak_api_key: "",
  weak_base_url: "",
  mid_model: "",
  mid_api_key: "",
  mid_base_url: "",
  strong_model: "",
  strong_api_key: "",
  strong_base_url: "",
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
        mid_api_key: nvidiaApiKey,
        mid_base_url: nvidiaBaseUrl,
        strong_api_key: nvidiaApiKey,
        strong_base_url: nvidiaBaseUrl,
      }))
    } catch (err: unknown) {
      setModelsError(err instanceof Error ? err.message : "Failed to load models")
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
      setFormError(err instanceof Error ? err.message : "Failed to create key")
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
    setModelsError("")
  }

  function updateField(field: keyof CreateKeyPayload, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }))
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
                  <div className="rounded-sm border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600 font-body">
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

                <div className="rounded-sm border border-brand-border p-3 space-y-3">
                  <p className="text-xs font-heading font-medium uppercase tracking-wider text-brand-muted">
                    NVIDIA NIM Credentials
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

                {nvidiaModels.length > 0 && (
                  <>
                    <div className="space-y-1">
                      <p className="text-xs font-heading font-medium uppercase tracking-wider text-brand-muted">
                        Weak Tier
                      </p>
                      <div className="grid grid-cols-1 gap-2">
                        <Select
                          value={form.weak_model}
                          onValueChange={(val) => updateField("weak_model", val)}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Select a model" />
                          </SelectTrigger>
                          <SelectContent>
                            {nvidiaModels.map((m) => (
                              <SelectItem key={m} value={m}>
                                {m}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    <div className="space-y-1">
                      <p className="text-xs font-heading font-medium uppercase tracking-wider text-brand-muted">
                        Mid Tier
                      </p>
                      <div className="grid grid-cols-1 gap-2">
                        <Select
                          value={form.mid_model}
                          onValueChange={(val) => updateField("mid_model", val)}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Select a model" />
                          </SelectTrigger>
                          <SelectContent>
                            {nvidiaModels.map((m) => (
                              <SelectItem key={m} value={m}>
                                {m}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    <div className="space-y-1">
                      <p className="text-xs font-heading font-medium uppercase tracking-wider text-brand-muted">
                        Strong Tier
                      </p>
                      <div className="grid grid-cols-1 gap-2">
                        <Select
                          value={form.strong_model}
                          onValueChange={(val) => updateField("strong_model", val)}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Select a model" />
                          </SelectTrigger>
                          <SelectContent>
                            {nvidiaModels.map((m) => (
                              <SelectItem key={m} value={m}>
                                {m}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  </>
                )}

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
                    disabled={submitting || nvidiaModels.length === 0}
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
