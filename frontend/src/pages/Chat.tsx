import { useState, useEffect, useRef } from "react"
import { useNavigate } from "react-router-dom"
import { listKeys, type VirtualKey } from "@/api/keys"
import { streamChatMessage, type ChatMessage, type ChatChunk, type FallbackNotice } from "@/api/chat"

interface ChatMessageDisplay extends ChatMessage {
  tierLabel?: string
  modelName?: string
  fallbackReason?: string
}
import { ApiError } from "@/api/client"
import { useAuth } from "@/context/AuthContext"
import "highlight.js/styles/github-dark.css"
import ReactMarkdown from "react-markdown"
import rehypeHighlight from "rehype-highlight"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Card, CardContent } from "@/components/ui/Card"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/Select"
import { Send, Loader2, Bot, User, Sparkles, Zap, Cpu, KeyRound, Trash2, Copy, Check } from "lucide-react"

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
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (authLoading) return
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

    const userMsg: ChatMessage = { role: "user", content: text }
    setMessages((prev) => [...prev, userMsg])
    setInput("")
    setSending(true)
    setError("")
    setLastRouting(undefined)

    const allMessages = [...messages, userMsg]

    try {
      let content = ""
      let firstChunk = true
      let currentTierLabel = ""
      let currentModelName = ""
      let currentFallbackReason: string | undefined
      for await (const chunk of streamChatMessage(rawKey, allMessages)) {
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
              updated[updated.length - 1] = { role: "assistant", content, tierLabel: currentTierLabel, modelName: currentModelName, fallbackReason: currentFallbackReason }
            } else {
              updated.push({ role: "assistant", content, tierLabel: currentTierLabel, modelName: currentModelName, fallbackReason: currentFallbackReason })
            }
            return updated
          })
        }
      }
    } catch (err) {
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

  if (authLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-brand-orange" />
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

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-2xl font-bold text-brand-text">Playground</h1>
          <p className="text-sm text-brand-muted font-body">
            Send prompts to test the intelligent routing engine
          </p>
        </div>
        {messages.length > 0 && (
          <button
            onClick={() => {
              setMessages([])
              localStorage.removeItem(CHAT_STORAGE_KEY)
            }}
            className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm text-brand-muted hover:text-red-400 hover:bg-red-950/40 transition-colors font-body"
            title="Clear chat"
          >
            <Trash2 className="h-4 w-4" />
            Clear Chat
          </button>
        )}
      </div>

      {fallbackNotice && (
        <div className="flex items-center justify-between rounded-lg border border-yellow-300 bg-yellow-50 px-4 py-2.5">
          <span className="text-sm font-medium text-yellow-800">
            ⚡ Routed to {fallbackNotice.to_model} ({fallbackNotice.reason})
          </span>
          <button
            type="button"
            onClick={() => setFallbackNotice(null)}
            className="text-yellow-600 hover:text-yellow-800 transition-colors"
            title="Dismiss"
          >
            ✕
          </button>
        </div>
      )}

      <Card className="flex-1 overflow-hidden">
        <CardContent className="flex h-full flex-col p-0">
          <div className="flex-1 overflow-y-auto space-y-4 p-4">
            {messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <Bot className="mb-4 h-16 w-16 text-brand-muted" />
                <h3 className="font-heading text-lg font-semibold text-brand-text">
                  Test Your Router
                </h3>
                <p className="mt-2 max-w-md text-sm text-brand-muted font-body">
                  Select a key below (or paste one) and send a prompt to see which tier
                  the router selects based on complexity analysis.
                </p>
              </div>
            ) : (
              messages.map((msg, i) => (
                <div key={i} className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
                  <div
                    className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                      msg.role === "user" ? "bg-brand-orange" : "bg-brand-border"
                    }`}
                  >
                    {msg.role === "user"
                      ? <User className="h-4 w-4 text-white" />
                      : <Bot className="h-4 w-4 text-white" />
                    }
                  </div>
                  <div
                    className={`group flex max-w-[70%] flex-col gap-1 ${
                      msg.role === "user"
                        ? "items-end"
                        : "items-start"
                    }`}
                  >
                    <div
                      className={`w-full rounded-lg px-4 py-2 ${
                        msg.role === "user"
                          ? "bg-brand-orange text-white"
                          : "bg-brand-bg text-brand-text"
                      }`}
                    >
                      {msg.role === "assistant" && msg.tierLabel && (
                        <div className="mb-1.5 flex flex-col gap-1">
                          <div className="flex items-center gap-1.5">
                            <span
                              className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider font-heading ${
                                msg.tierLabel === "weak"
                                  ? "bg-green-100 text-green-700"
                                  : msg.tierLabel === "mid"
                                    ? "bg-yellow-100 text-yellow-700"
                                    : "bg-red-100 text-red-700"
                              }`}
                            >
                              {msg.tierLabel}
                            </span>
                            {msg.modelName && (
                              <span className="text-[11px] text-brand-muted font-mono truncate max-w-[200px]">
                                {msg.modelName}
                              </span>
                            )}
                          </div>
                          {msg.fallbackReason && (
                            <span className="text-[10px] text-amber-600 italic">
                              Fallback: {msg.fallbackReason}
                            </span>
                          )}
                        </div>
                      )}
                      <div
                        className={
                          msg.role === "user"
                            ? "font-body text-sm space-y-2 [&_p]:leading-relaxed [&_code]:rounded [&_code]:bg-white/10 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-sm [&_code]:text-white [&_pre]:mb-3 [&_pre]:mt-2 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-gray-900 [&_pre]:p-4 [&_pre]:text-sm [&_pre]:leading-relaxed [&_pre]:text-gray-100 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:mb-1 [&_h1]:mb-2 [&_h1]:text-xl [&_h1]:font-bold [&_h2]:mb-2 [&_h2]:text-lg [&_h2]:font-semibold [&_h3]:mb-1 [&_h3]:text-base [&_h3]:font-semibold [&_a]:text-blue-200 [&_a]:underline [&_a:hover]:text-blue-100 [&_blockquote]:border-l-4 [&_blockquote]:border-white/40 [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:text-white/80 [&_table]:w-full [&_table]:border-collapse [&_th]:border [&_th]:border-white/30 [&_th]:px-3 [&_th]:py-1.5 [&_th]:bg-white/10 [&_th]:text-left [&_td]:border [&_td]:border-white/30 [&_td]:px-3 [&_td]:py-1.5 [&_hr]:my-3 [&_hr]:border-white/30 [&_img]:max-w-full [&_img]:rounded"
                            : "font-body text-sm space-y-2 [&_p]:leading-relaxed [&_code]:rounded [&_code]:bg-white/10 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-sm [&_code]:text-brand-text [&_pre]:mb-3 [&_pre]:mt-2 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-brand-surface [&_pre]:p-4 [&_pre]:text-sm [&_pre]:leading-relaxed [&_pre]:text-brand-text [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:mb-1 [&_h1]:mb-2 [&_h1]:text-xl [&_h1]:font-bold [&_h2]:mb-2 [&_h2]:text-lg [&_h2]:font-semibold [&_h3]:mb-1 [&_h3]:text-base [&_h3]:font-semibold [&_a]:text-brand-blue [&_a]:underline [&_a:hover]:text-brand-orange [&_blockquote]:border-l-4 [&_blockquote]:border-brand-border [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:text-brand-muted [&_table]:w-full [&_table]:border-collapse [&_th]:border [&_th]:border-brand-border [&_th]:px-3 [&_th]:py-1.5 [&_th]:bg-brand-surface [&_th]:text-left [&_td]:border [&_td]:border-brand-border [&_td]:px-3 [&_td]:py-1.5 [&_hr]:my-3 [&_hr]:border-brand-border [&_img]:max-w-full [&_img]:rounded"
                        }
                      >
                        <ReactMarkdown rehypePlugins={[rehypeHighlight]}>
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                    </div>
                    {msg.role === "assistant" && (
                      <button
                        onClick={() => copyMessage(msg.content, i)}
                        className="ml-1 flex items-center gap-1 text-xs text-brand-muted hover:text-brand-text transition-colors"
                        title="Copy message"
                      >
                        {copiedIndex === i ? (
                          <>
                            <Check className="h-3.5 w-3.5 text-green-500" />
                            <span className="text-green-500">Copied</span>
                          </>
                        ) : (
                          <>
                            <Copy className="h-3.5 w-3.5" />
                            <span>Copy</span>
                          </>
                        )}
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
            {sending && (
              <div className="flex gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-border">
                  <Bot className="h-4 w-4 text-white" />
                </div>
                <div className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin text-brand-muted" />
                  <span className="text-sm text-brand-muted font-body">Thinking...</span>
                </div>
              </div>
            )}
            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {error}
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="border-t border-brand-border space-y-3 p-5">
            <div className="flex items-center gap-3">
              <Select value={selectedKey} onValueChange={setSelectedKey}>
                <SelectTrigger className="w-64 sm:w-72">
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
                <span className="text-xs text-brand-muted font-body">
                  (key not available — paste below)
                </span>
              )}
            </div>

            {!hasKey() && (
              <div className="flex items-center gap-2">
                <KeyRound className="h-4 w-4 shrink-0 text-brand-muted" />
                <Input
                  placeholder="Paste virtual key (lmr-...)"
                  value={manualKey}
                  onChange={(e) => setManualKey(e.target.value)}
                  className="font-mono text-sm flex-1"
                />
              </div>
            )}

            <div className="flex items-center gap-2">
              <Input
                placeholder="Enter a prompt..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault()
                    handleSend()
                  }
                }}
                disabled={sending}
                className="flex-1 text-base py-3 h-auto min-h-[56px]"
              />
              <Button onClick={handleSend} disabled={sending || !input.trim() || !hasKey()}>
                {sending
                  ? <Loader2 className="h-4 w-4 animate-spin" />
                  : <Send className="h-4 w-4" />
                }
              </Button>
            </div>

            {lastRouting && (
              <div className="flex items-center gap-2 text-xs">
                <span className="text-brand-muted font-body">Routed to:</span>
                <span
                  className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-white capitalize ${
                    lastRouting.tier === 0 ? "bg-yellow-500"
                    : lastRouting.tier === 1 ? "bg-blue-500"
                    : "bg-purple-500"
                  }`}
                >
                  {lastRouting.tier === 0 ? <Zap className="h-3 w-3" />
                    : lastRouting.tier === 1 ? <Cpu className="h-3 w-3" />
                    : <Sparkles className="h-3 w-3" />
                  }
                  {lastRouting.tier_name}
                </span>
                <span className="text-brand-muted font-body">
                  ({(lastRouting.confidence * 100).toFixed(0)}% confidence)
                </span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}