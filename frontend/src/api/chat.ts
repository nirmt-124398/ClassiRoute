import { apiRequest, ApiError } from "./client"

export interface ChatMessage {
  role: "user" | "assistant" | "system"
  content: string
}

export interface ChatRequest {
  messages: ChatMessage[]
  stream?: boolean
}

export interface ChatResponse {
  id: string
  object: string
  created: number
  model: string
  choices: Array<{
    index: number
    message: ChatMessage
    finish_reason: string
  }>
  usage?: {
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
  }
  "x-llmrouter"?: {
    tier: number
    tier_name: string
    confidence: number
    difficulty_score: number
    upgraded: boolean
    rerouted: boolean
    fallback_reason?: string
    original_tier?: number
    original_tier_name?: string
  }
}

export interface ChatChunk {
  id: string
  object: string
  created: number
  model: string
  choices: Array<{
    index: number
    delta: Partial<ChatMessage>
    finish_reason: string | null
  }>
  "x-llmrouter"?: {
    tier: number
    tier_name: string
    confidence: number
    difficulty_score: number
    upgraded: boolean
    rerouted: boolean
    fallback_reason?: string
    original_tier?: number
    original_tier_name?: string
  }
}

export interface ChatError {
  error: string
}

export interface FallbackNotice {
  type: "fallback_notice"
  from_tier: string
  to_tier: string
  from_model: string
  to_model: string
  reason: string
  message: string
}

export interface StreamError {
  type: "error"
  message: string
}

export async function* streamChatMessage(
  virtualKey: string,
  messages: ChatMessage[]
): AsyncGenerator<ChatChunk | FallbackNotice | StreamError> {
  const response = await fetch("/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${virtualKey}`,
    },
    body: JSON.stringify({ messages, stream: true }),
  })

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: "Stream error" }))
    throw new ApiError(response.status, err.detail ?? "Stream error")
  }

  if (!response.body) {
    throw new ApiError(500, "No response body")
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const text = decoder.decode(value)
      const lines = text.split("\n")

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6)
          if (data === "[DONE]") return
          try {
            const parsed = JSON.parse(data)
            if (parsed.type === "fallback_notice" || parsed.type === "error") {
              yield parsed
            } else {
              yield parsed as ChatChunk
            }
          } catch {
            // malformed chunk — skip
          }
        }
      }
    }
  } catch (err) {
    if (err instanceof TypeError && err.message.includes("fetch")) {
      throw new ApiError(504, "Connection lost while streaming. Try again.")
    }
    throw err
  } finally {
    reader.releaseLock()
  }
}