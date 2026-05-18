import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen, fireEvent, cleanup } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"
import { ChatInput, type ChatInputProps } from "./ChatInput"

afterEach(() => cleanup())

function renderChatInput(props: Partial<ChatInputProps> = {}) {
  const defaultProps: ChatInputProps = {
    value: "",
    onChange: vi.fn(),
    placeholder: "Type a message...",
    onSend: vi.fn(),
  }
  return render(<ChatInput {...defaultProps} {...props} />)
}

describe("ChatInput", () => {
  it("renders with placeholder text", () => {
    renderChatInput({ placeholder: "Ask anything..." })
    expect(screen.getByPlaceholderText("Ask anything...")).toBeInTheDocument()
  })

  it("typing updates value via onChange", () => {
    const onChange = vi.fn()
    renderChatInput({ onChange, value: "" })

    const textarea = screen.getByPlaceholderText("Type a message...")
    fireEvent.change(textarea, { target: { value: "Hello" } })

    expect(onChange).toHaveBeenCalledTimes(1)
  })

  it("Enter key triggers onSend callback", () => {
    const onSend = vi.fn()
    renderChatInput({ onSend, value: "Hello" })

    const textarea = screen.getByPlaceholderText("Type a message...")
    fireEvent.keyDown(textarea, { key: "Enter" })

    expect(onSend).toHaveBeenCalledTimes(1)
  })

  it("Shift+Enter does NOT trigger onSend", () => {
    const onSend = vi.fn()
    renderChatInput({ onSend, value: "Hello" })

    const textarea = screen.getByPlaceholderText("Type a message...")
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: true })

    expect(onSend).not.toHaveBeenCalled()
  })

  it("send button is disabled when value is empty", () => {
    renderChatInput({ value: "" })

    const sendBtn = screen.getByRole("button")
    expect(sendBtn).toBeDisabled()
  })

  it("send button is enabled when value is not empty", () => {
    renderChatInput({ value: "Hello" })

    const sendBtn = screen.getByRole("button")
    expect(sendBtn).not.toBeDisabled()
  })

  it("send button is disabled when value is only whitespace", () => {
    renderChatInput({ value: "   " })

    const sendBtn = screen.getByRole("button")
    expect(sendBtn).toBeDisabled()
  })
})
