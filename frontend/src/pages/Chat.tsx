import { useState, useEffect, useRef, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { listKeys, type VirtualKey } from "@/api/keys"
import { streamChatMessage, type ChatMessage, type ChatChunk, type FallbackNotice } from "@/api/chat"

interface ChatMessageDisplay extends ChatMessage {
  tierLabel?: string
  modelName?: string
  fallbackReason?: string
  rerouted?: boolean
  originalTier?: string
  timestamp?: number
}
import { ApiError } from "@/api/client"
import { useAuth } from "@/context/AuthContext"
import "highlight.js/styles/github-dark.css"
import ReactMarkdown from "react-markdown"
import rehypeHighlight from "rehype-highlight"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/Select"
import { ChatInput } from "@/components/ui/ChatInput"
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog"
import { EmptyState } from "@/components/ui/EmptyState"
import { SkeletonCard } from "@/components/ui/Skeleton"
import { Badge } from "@/components/ui/Badge"
import { useToast } from "@/components/ui/Toast"
import { cn } from "@/lib/utils"
import {
  Send,
  Loader2,
  Bot,
  User,
  Sparkles,
  Zap,
  Cpu,
  KeyRound,
  Trash2,
  Copy,
  Check,
  ChevronDown,
  MessageSquare,
} from "lucide-react"

const CHAT_STORAGE_KEY = "chat_messages"

function loadMessages(): ChatMessageDisplay[] {
  try {
    const raw = localStorage.getItem(CHAT_STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveMessages(messages: ChatMessageDisplay[]) {
  try {
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages))
  } catch {
    // quota exceeded — silently ignore
  }
}

function getStoredKey(keyId: string): string | null {
  try {
    const stored = JSON.parse(localStorage.getItem("created_keys") || "{}")
    return stored[keyId]?.key || null
  } catch {
    return null
  }
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

// ─── Prose classes kept identical to preserve markdown rendering ──────────

const assistantProse =
  "font-body text-sm space-y-2 [&_p]:leading-relaxed [&_code]:rounded [&_code]:bg-white/10 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-sm [&_code]:text-brand-text [&_pre]:mb-3 [&_pre]:mt-2 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-brand-surface [&_pre]:p-4 [&_pre]:text-sm [&_pre]:leading-relaxed [&_pre]:text-brand-text [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:mb-1 [&_h1]:mb-2 [&_h1]:text-xl [&_h1]:font-bold [&_h2]:mb-2 [&_h2]:text-lg [&_h2]:font-semibold [&_h3]:mb-1 [&_h3]:text-base [&_h3]:font-semibold [&_a]:text-brand-blue [&_a]:underline [&_a:hover]:text-brand-orange [&_blockquote]:border-l-4 [&_blockquote]:border-brand-border [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:text-brand-muted [&_table]:w-full [&_table]:border-collapse [&_th]:border [&_th]:border-brand-border [&_th]:px-3 [&_th]:py-1.5 [&_th]:bg-brand-surface [&_th]:text-left [&_td]:border [&_td]:border-brand-border [&_td]:px-3 [&_td]:py-1.5 [&_hr]:my-3 [&_hr]:border-brand-border [&_img]:max-w-full [&_img]:rounded"

const userProse =
  "font-body text-sm space-y-2 [&_p]:leading-relaxed [&_code]:rounded [&_code]:bg-white/10 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-sm [&_code]:text-white [&_pre]:mb-3 [&_pre]:mt-2 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-gray-900 [&_pre]:p-4 [&_pre]:text-sm [&_pre]:leading-relaxed [&_pre]:text-gray-100 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:mb-1 [&_h1]:mb-2 [&_h1]:text-xl [&_h1]:font-bold [&_h2]:mb-2 [&_h2]:text-lg [&_h2]:font-semibold [&_h3]:mb-1 [&_h3]:text-base [&_h3]:font-semibold [&_a]:text-blue-200 [&_a]:underline [&_a:hover]:text-blue-100 [&_blockquote]:border-l-4 [&_blockquote]:border-white/40 [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:text-white/80 [&_table]:w-full [&_table]:border-collapse [&_th]:border [&_th]:border-white/30 [&_th]:px-3 [&_th]:py-1.5 [&_th]:bg-white/10 [&_th]:text-left [&_td]:border [&_td]:border-white/30 [&_td]:px-3 [&_td]:py-1.5 [&_hr]:my-3 [&_hr]:border-white/30 [&_img]:max-w-full [&_img]:rounded"

export default function Chat() {
  const { loading: authLoading } = useAuth()
  const navigate = useNavigate()
  const [keys, setKeys] = useState<VirtualKey[]>([])
  const [selectedKey, setSelectedKey] = useState<string>("")
  const [manualKey, setManualKey] = useState("")
  const [messages, setMessages] = useState<ChatMessageDisplay[]>(loadMessages())
  const [input, setInput] = useState("")
  const [sending, setSending] = useState(false)
  const [error, setError] = useState("")
  const [lastRouting, setLastRouting] = useState<ChatChunk["x-llmrouter"]>(undefined)
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)
  const [fallbackNotice, setFallbackNotice] = useState<FallbackNotice | null>(null)
  const [clearDialogOpen, setClearDialogOpen] = useState(false)
  const [showScrollBtn, setShowScrollBtn] = useState(false)
  const [expandedRoutingIndex, setExpandedRoutingIndex] = useState<number | null>(null)
  const [lastRoutingExpanded, setLastRoutingExpanded] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const { addToast } = useToast()

  // ─── Effects ─────────────────────────────────────────────────────────────

  useEffect(() => {
    if (authLoading) return
    setInitialLoading(true)
    listKeys()
      .then((ks) => {
        const activeKeys = ks.filter(k => k.is_active)
        setKeys(activeKeys)
        if (activeKeys.length > 0) setSelectedKey(activeKeys[0].key_id)
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          navigate("/login", { replace: true })
        }
      })
      .finally(() => setInitialLoading(false))
  }, [authLoading, navigate])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  useEffect(() => {
    const handleBeforeUnload = () => saveMessages(messages)
    window.addEventListener("beforeunload", handleBeforeUnload)
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload)
      saveMessages(messages)
    }
  }, [messages])

  // ─── Helpers ─────────────────────────────────────────────────────────────

  // ─── Context window management ───────────────────────────────────────
  //
  //  Token budget instead of a hard message cap.  This lets short messages
  //  keep more history while long messages don't blow the model's context.
  //
  const CTX_BUDGET = 6000         // target tokens for conversation history
  const CHARS_PER_TOKEN = 4       // rough English estimate

  function estimateTokens(text: string): number {
    return Math.ceil(text.length / CHARS_PER_TOKEN)
  }

  function toApiMessages(msgs: ChatMessageDisplay[]): ChatMessage[] {
    // 1. Strip display-only fields, drop empty messages, dedupe consecutive
    //    same-role (can happen on retry / error).
    const cleaned: ChatMessage[] = []
    for (const m of msgs) {
      if (!m.role || !m.content) continue               // ← skip empty / corrupt
      const msg: ChatMessage = { role: m.role, content: m.content }
      if (cleaned.length > 0 && cleaned.at(-1)!.role === msg.role) continue
      cleaned.push(msg)
    }
    // Conversation must always start with a user turn
    if (cleaned.length > 0 && cleaned[0].role !== "user") cleaned.shift()
    if (cleaned.length === 0) return cleaned

    // 2. Under budget?  Send everything.
    const totalTokens = cleaned.reduce((s, m) => s + estimateTokens(m.content), 0)
    if (totalTokens <= CTX_BUDGET) return cleaned

    // 3. Over budget — keep the **newest** messages that fit.
    const result: ChatMessage[] = []
    let budget = CTX_BUDGET

    for (let i = cleaned.length - 1; i >= 0; i--) {
      const t = estimateTokens(cleaned[i].content)
      if (t <= budget) {
        result.unshift(cleaned[i])
        budget -= t
      } else {
        break          // message alone exceeds budget → stop here
      }
    }

    // 4. Safety net — even a single message can be too long.
    //    Send a truncated version so the AI at least sees the user's last turn.
    if (result.length === 0 && cleaned.length > 0) {
      const last = cleaned.at(-1)!
      const maxChars = CTX_BUDGET * CHARS_PER_TOKEN
      result.push({ role: last.role, content: last.content.slice(-maxChars) })
    }

    // After removal of oldest messages the window may start with assistant
    if (result.length > 0 && result[0].role !== "user") result.shift()

    return result
  }

  function resolveKey(): string | null {
    if (manualKey.trim()) return manualKey.trim()
    if (selectedKey) {
      const selected = keys.find(k => k.key_id === selectedKey)
      if (selected?.key_raw) return selected.key_raw
      const stored = getStoredKey(selectedKey)
      if (stored) return stored
    }
    return null
  }

  async function handleSend() {
    const text = input.trim()
    if (!text || sending) return

    const rawKey = resolveKey()
    if (!rawKey) {
      setError("No virtual key available. Select a key created in this session or paste one below.")
      return
    }

    const userMsg: ChatMessageDisplay = { role: "user", content: text, timestamp: Date.now() }
    setMessages((prev) => [...prev, userMsg])
    setInput("")
    setSending(true)
    setError("")
    setLastRouting(undefined)

    const allMessages = [...messages, userMsg]
    const apiMessages = toApiMessages(allMessages)

    try {
      let content = ""
      let firstChunk = true
      let currentTierLabel = ""
      let currentModelName = ""
      let currentFallbackReason: string | undefined
      let currentRerouted = false
      let currentOriginalTier = ""
      for await (const chunk of streamChatMessage(rawKey, apiMessages)) {
        if ("type" in chunk && chunk.type === "fallback_notice") {
          setFallbackNotice(chunk)
          continue
        }
        if ("type" in chunk && chunk.type === "error") {
          setError(`Backend error: ${chunk.message}`)
          break
        }
        if ("error" in chunk) {
          setError(`Backend error: ${chunk.error}`)
          break
        }
        if (firstChunk && chunk["x-llmrouter"]) {
          setLastRouting(chunk["x-llmrouter"])
          firstChunk = false
          const routing = chunk["x-llmrouter"]
          currentTierLabel = routing.tier_name ?? "unknown"
          currentFallbackReason = routing.fallback_reason
          currentRerouted = routing.rerouted ?? false
          currentOriginalTier = routing.original_tier_name ?? ""
          const tierNum = routing.tier
          const selected = keys.find(k => k.key_id === selectedKey)
          if (selected) {
            if (tierNum === 0) currentModelName = selected.weak_model
            else if (tierNum === 1) currentModelName = selected.mid_model
            else if (tierNum === 2) currentModelName = selected.strong_model
          }
        }
        if (chunk.choices?.[0]?.delta?.content) {
          content += chunk.choices[0].delta.content
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last && last.role === "assistant") {
              updated[updated.length - 1] = {
                ...last,
                role: "assistant",
                content,
                tierLabel: currentTierLabel,
                modelName: currentModelName,
                fallbackReason: currentFallbackReason,
                rerouted: currentRerouted,
                originalTier: currentOriginalTier,
              }
            } else {
              updated.push({
                role: "assistant",
                content,
                tierLabel: currentTierLabel,
                modelName: currentModelName,
                fallbackReason: currentFallbackReason,
                rerouted: currentRerouted,
                originalTier: currentOriginalTier,
                timestamp: Date.now(),
              })
            }
            return updated
          })
        }
      }
    } catch (err) {
      // Remove the partial assistant message (if any) — it's incomplete and
      // sending it would confuse the model on the next turn.
      setMessages(prev => {
        const updated = [...prev]
        const last = updated.at(-1)
        if (last && last.role === "assistant") updated.pop()
        return updated
      })
      if (err instanceof ApiError) {
        console.error("Chat API error:", err.status, err.detail)
        setError(`Error (${err.status}): ${err.detail}`)
      } else if (err instanceof Error) {
        console.error("Chat error:", err.message)
        setError(`Error: ${err.message}`)
      } else {
        setError("Request failed")
      }
    } finally {
      setSending(false)
      setMessages(prev => {
        saveMessages(prev)
        return prev
      })
    }
  }

  function hasKey(): boolean {
    if (manualKey.trim()) return true
    if (selectedKey) {
      const selected = keys.find(k => k.key_id === selectedKey)
      if (selected?.key_raw) return true
      if (getStoredKey(selectedKey)) return true
    }
    return false
  }

  async function copyMessage(content: string, index: number) {
    try {
      await navigator.clipboard.writeText(content)
      setCopiedIndex(index)
      setTimeout(() => setCopiedIndex(null), 2000)
    } catch {
      // Clipboard API not available or permission denied — silently ignore
    }
  }

  function handleClear() {
    setMessages([])
    localStorage.removeItem(CHAT_STORAGE_KEY)
    addToast({ title: "Conversation cleared", variant: "info" })
  }

  const handleScroll = useCallback(() => {
    const container = messagesContainerRef.current
    if (!container) return
    const threshold = 120
    const isNearBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight < threshold
    setShowScrollBtn(!isNearBottom)
  }, [])

  // ─── Loading / No-keys states ────────────────────────────────────────────

  if (authLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-brand-orange" />
      </div>
    )
  }

  if (initialLoading) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="w-full max-w-2xl space-y-4">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </div>
    )
  }

  if (keys.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <Bot className="mb-4 h-12 w-12 text-brand-muted" />
        <h3 className="font-heading text-lg font-semibold text-brand-text">No API Keys</h3>
        <p className="mt-2 text-sm text-brand-muted font-body">
          Create an API key first to test the chat routing feature.
        </p>
        <Button className="mt-4" onClick={() => navigate("/keys")}>
          Go to Keys
        </Button>
      </div>
    )
  }

  // ─── Main UI ─────────────────────────────────────────────────────────────

  return (
    <div className="flex h-full flex-col">
      <ConfirmationDialog
        open={clearDialogOpen}
        onOpenChange={setClearDialogOpen}
        title="Clear conversation"
        description="This will permanently delete all messages in this conversation. This action cannot be undone."
        confirmLabel="Clear"
        cancelLabel="Cancel"
        onConfirm={handleClear}
        variant="default"
      />

      {/* ZONE 1: Header — key picker + clear button */}
      <div className="shrink-0 border-b border-brand-border px-6 py-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <Select value={selectedKey} onValueChange={setSelectedKey}>
              <SelectTrigger className="w-56">
                <SelectValue placeholder="Select a key" />
              </SelectTrigger>
              <SelectContent>
                {keys.map((k) => (
                  <SelectItem key={k.key_id} value={k.key_id}>
                    {k.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {!manualKey.trim() && !getStoredKey(selectedKey) && (
              <span className="shrink-0 text-xs text-brand-muted font-body">
                (key not available — paste below)
              </span>
            )}
          </div>
          {messages.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setClearDialogOpen(true)}
              className="shrink-0 text-brand-muted hover:text-red-400"
            >
              <Trash2 className="mr-1.5 h-4 w-4" />
              Clear Chat
            </Button>
          )}
        </div>

        {!hasKey() && (
          <div className="mt-3 flex items-center gap-2">
            <KeyRound className="h-4 w-4 shrink-0 text-brand-muted" />
            <Input
              placeholder="Paste virtual key (clr-...)"
              value={manualKey}
              onChange={(e) => setManualKey(e.target.value)}
              className="font-mono text-sm flex-1"
            />
          </div>
        )}

        {fallbackNotice && (
          <div className="mt-3 flex items-center justify-between rounded-sm border border-brand-border bg-brand-surface px-4 py-2.5">
            <span className="text-sm font-body text-brand-muted">
              ⚡ Routed to {fallbackNotice.to_model} ({fallbackNotice.reason})
            </span>
            <button
              type="button"
              onClick={() => setFallbackNotice(null)}
              className="text-brand-muted hover:text-brand-text transition-colors"
              title="Dismiss"
            >
              ✕
            </button>
          </div>
        )}
      </div>

      {/* ZONE 2: Messages — scrollable */}
      <div
        ref={messagesContainerRef}
        onScroll={handleScroll}
        className="relative flex-1 overflow-y-auto"
      >
        <div className="px-6 py-4">
          {messages.length === 0 ? (
            <div className="flex h-full min-h-[400px] items-center justify-center">
              <EmptyState
                icon={MessageSquare}
                title="Start a conversation"
                description="Select a key above and send a prompt to test the intelligent routing engine."
              />
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((msg, i) => {
                const isAssistant = msg.role === "assistant"
                const isSameAsPrev = i > 0 && messages[i - 1].role === msg.role
                const isRoutingExpanded = expandedRoutingIndex === i

                return (
                  <div
                    key={`msg-${msg.role}-${i}`}
                    className={cn(
                      "flex w-full animate-fade-in-up",
                      isAssistant ? "justify-start" : "justify-end",
                      isSameAsPrev ? "-mt-3" : "",
                    )}
                  >
                    <div
                      className={cn(
                        "flex max-w-[80%] flex-col",
                        isAssistant ? "items-start" : "items-end",
                      )}
                    >
                      {/* Routing badge — compact, collapsible */}
                      {isAssistant && msg.tierLabel && (
                        <button
                          type="button"
                          onClick={() =>
                            setExpandedRoutingIndex(isRoutingExpanded ? null : i)
                          }
                          className="mb-1.5"
                        >
                          <Badge
                            variant="outline"
                            className={cn(
                              "cursor-pointer text-[10px] uppercase tracking-wider",
                              msg.rerouted
                                ? "border-yellow-500/40 text-yellow-600 hover:bg-yellow-500/10"
                                : "hover:bg-brand-border/50",
                            )}
                          >
                            {msg.tierLabel === "weak" ? (
                              <Zap className="mr-1 h-3 w-3" />
                            ) : msg.tierLabel === "mid" ? (
                              <Cpu className="mr-1 h-3 w-3" />
                            ) : (
                              <Sparkles className="mr-1 h-3 w-3" />
                            )}
                            {msg.rerouted && msg.originalTier ? (
                              <span>{msg.originalTier} → {msg.tierLabel}</span>
                            ) : (
                              <span>{msg.tierLabel}</span>
                            )}
                            {msg.modelName && (
                              <span className="ml-1 font-mono normal-case">
                                · {msg.modelName}
                              </span>
                            )}
                          </Badge>
                        </button>
                      )}

                      {/* Expanded routing details */}
                      {isRoutingExpanded && msg.fallbackReason && (
                        <div className="mb-2 rounded-sm border border-brand-border bg-brand-bg px-2.5 py-1.5 text-xs text-brand-muted">
                          Fallback: {msg.fallbackReason}
                        </div>
                      )}

                      {/* Message bubble */}
                      <div
                        className={cn(
                          "w-full rounded-sm px-4 py-3",
                          isAssistant
                            ? "border-l-2 border-brand-orange/40 bg-brand-surface"
                            : "border border-brand-border/80 bg-brand-surface",
                        )}
                      >
                        <div className={isAssistant ? assistantProse : userProse}>
                          <ReactMarkdown rehypePlugins={[rehypeHighlight]}>
                            {msg.content}
                          </ReactMarkdown>
                        </div>
                      </div>

                      {/* Timestamp + Copy */}
                      <div className="mt-1 flex items-center gap-3">
                        {msg.timestamp && (
                          <span className="text-[10px] text-brand-muted/50">
                            {formatTime(msg.timestamp)}
                          </span>
                        )}
                        {isAssistant && (
                          <button
                            type="button"
                            onClick={() => copyMessage(msg.content, i)}
                            className="flex items-center gap-1 text-[10px] text-brand-muted/50 hover:text-brand-text transition-colors"
                            title="Copy message"
                          >
                            {copiedIndex === i ? (
                              <>
                                <Check className="h-3 w-3 text-brand-green" />
                                <span className="text-brand-green">Copied</span>
                              </>
                            ) : (
                              <>
                                <Copy className="h-3 w-3" />
                                <span>Copy</span>
                              </>
                            )}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* Streaming indicator */}
          {sending && (
            <div className="mt-4 flex items-start gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-border">
                <Bot className="h-4 w-4 text-white" />
              </div>
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-2">
                  <div className="flex gap-1">
                    <span className="h-2 w-2 rounded-full bg-brand-orange/60 animate-typing-dot" />
                    <span
                      className="h-2 w-2 rounded-full bg-brand-orange/60 animate-typing-dot"
                      style={{ animationDelay: "0.2s" }}
                    />
                    <span
                      className="h-2 w-2 rounded-full bg-brand-orange/60 animate-typing-dot"
                      style={{ animationDelay: "0.4s" }}
                    />
                  </div>
                  {lastRouting?.tier_name && (
                    <span className="text-xs text-brand-muted font-mono">
                      {lastRouting.tier_name} model responding...
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="mt-4 rounded-sm border border-red-800 bg-red-950/20 px-4 py-3 text-sm text-red-400">
              {error}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Scroll-to-bottom button */}
        {showScrollBtn && (
          <button
            type="button"
            onClick={() => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })}
            className="absolute bottom-4 right-4 z-10 flex h-8 w-8 items-center justify-center rounded-full bg-brand-orange text-white shadow-lg hover:bg-brand-orange/90 transition-colors animate-fade-in-up"
            title="Scroll to bottom"
          >
            <ChevronDown className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* ZONE 3: Input — fixed bottom */}
      <div className="shrink-0 border-t border-brand-border px-6 py-4">
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <ChatInput
              placeholder="Enter a prompt..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onSend={handleSend}
              disabled={sending || !hasKey()}
            />
          </div>
          {lastRouting && (
            <button
              type="button"
              onClick={() => setLastRoutingExpanded(!lastRoutingExpanded)}
              className="mb-1"
              title="Routing details"
            >
              <Badge
                variant="outline"
                className="cursor-pointer text-[10px] uppercase tracking-wider hover:bg-brand-border/50"
              >
                {lastRouting.tier === 0 ? (
                  <Zap className="mr-1 h-3 w-3" />
                ) : lastRouting.tier === 1 ? (
                  <Cpu className="mr-1 h-3 w-3" />
                ) : (
                  <Sparkles className="mr-1 h-3 w-3" />
                )}
                {lastRouting.tier_name}
              </Badge>
            </button>
          )}
        </div>

        {lastRoutingExpanded && lastRouting && (
          <div className="mt-2 space-y-1 rounded-sm border border-brand-border bg-brand-surface p-2.5 text-xs text-brand-muted">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span>Tier: {lastRouting.tier_name}</span>
              <span>· Confidence: {(lastRouting.confidence * 100).toFixed(0)}%</span>
              <span>· Difficulty: {(lastRouting.difficulty_score * 100).toFixed(0)}%</span>
              {lastRouting.upgraded && (
                <Badge variant="success" className="text-[9px]">
                  Upgraded
                </Badge>
              )}
              {lastRouting.rerouted && (
                <Badge variant="destructive" className="text-[9px]">
                  Rerouted
                </Badge>
              )}
            </div>
            {lastRouting.fallback_reason && (
              <div className="pt-0.5">Fallback: {lastRouting.fallback_reason}</div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
