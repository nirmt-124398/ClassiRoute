import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react"
import { ToastProvider, useToast, toast } from "./Toast"

afterEach(() => cleanup())

// ─── Helper component that uses the toast hook ────────────────────────────

function ToastTrigger({ variant }: { variant?: "success" | "error" | "info" | "warning" }) {
  const { addToast } = useToast()
  return (
    <button
      type="button"
      onClick={() =>
        addToast({
          title: "Test Title",
          description: "Test Description",
          variant,
        })
      }
    >
      Show Toast
    </button>
  )
}

// ─── Tests ────────────────────────────────────────────────────────────────

describe("Toast", () => {
  it("renders children within ToastProvider", () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>,
    )
    expect(screen.getByText("Show Toast")).toBeInTheDocument()
  })

  it("shows a toast when addToast is called", async () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>,
    )

    fireEvent.click(screen.getByText("Show Toast"))
    expect(await screen.findByText("Test Title")).toBeInTheDocument()
    expect(await screen.findByText("Test Description")).toBeInTheDocument()
  })

  it("renders with correct variant styling", async () => {
    const variants = [
      { variant: "success" as const, expectedClass: "border-brand-green" },
      { variant: "error" as const, expectedClass: "border-red-400" },
      { variant: "info" as const, expectedClass: "border-brand-blue" },
      { variant: "warning" as const, expectedClass: "border-brand-orange" },
    ]

    for (const { variant, expectedClass } of variants) {
      cleanup()
      const { container } = render(
        <ToastProvider>
          <ToastTrigger variant={variant} />
        </ToastProvider>,
      )

      fireEvent.click(screen.getByText("Show Toast"))

      // Wait for the toast to appear
      await screen.findByText("Test Title")

      // Check that the toast root has the variant accent class
      const toastEl = container.querySelector(`[class*="${expectedClass}"]`)
      expect(toastEl).toBeInTheDocument()
    }
  })

  it("stacks multiple toasts correctly", async () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>,
    )

    // Trigger multiple toasts
    fireEvent.click(screen.getByText("Show Toast"))
    fireEvent.click(screen.getByText("Show Toast"))
    fireEvent.click(screen.getByText("Show Toast"))

    // Wait for them to appear and check all are present
    await waitFor(() => {
      expect(screen.getAllByText("Test Title")).toHaveLength(3)
    })
    expect(screen.getAllByText("Test Description")).toHaveLength(3)
  })

  it("can be manually closed via close button", async () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>,
    )

    fireEvent.click(screen.getByText("Show Toast"))
    expect(await screen.findByText("Test Title")).toBeInTheDocument()

    // Find and click the close button
    const closeBtn = document.querySelector('[toast-close]')
    expect(closeBtn).toBeInTheDocument()
    if (closeBtn) fireEvent.click(closeBtn)

    // Wait for close animation and removal from DOM
    await waitFor(() => {
      expect(screen.queryByText("Test Title")).not.toBeInTheDocument()
    })
  })

  it("auto-dismisses after duration", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })

    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>,
    )

    fireEvent.click(screen.getByText("Show Toast"))
    expect(await screen.findByText("Test Title")).toBeInTheDocument()

    // The duration is 4000ms. Advance past it plus animation delay
    vi.advanceTimersByTime(5000)

    await waitFor(() => {
      expect(screen.queryByText("Test Title")).not.toBeInTheDocument()
    })

    vi.useRealTimers()
  })

  it("throws error when useToast is used outside ToastProvider", () => {
    const TestComponent = () => {
      useToast()
      return null
    }

    expect(() => render(<TestComponent />)).toThrow(
      "useToast must be used within a <ToastProvider>",
    )
  })

  it("global toast() function fires without provider context", () => {
    // Should not throw when no provider
    expect(() => toast({ title: "Global", description: "Test" })).not.toThrow()
  })

  it("global toast() shows toast via provider", async () => {
    render(
      <ToastProvider>
        <div data-testid="outside" />
      </ToastProvider>,
    )

    // This exercises the global handler registered by ToastProvider
    toast({ title: "Global Toast", description: "Fired from anywhere" })

    expect(await screen.findByText("Global Toast")).toBeInTheDocument()
  })
})
