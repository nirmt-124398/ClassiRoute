import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen, cleanup } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import "@testing-library/jest-dom/vitest"
import { ErrorState } from "./ErrorState"

afterEach(() => cleanup())

describe("ErrorState", () => {
  it("renders default title and message", () => {
    render(<ErrorState message="Test error description" />)
    expect(screen.getByText("Something went wrong")).toBeInTheDocument()
    expect(screen.getByText("Test error description")).toBeInTheDocument()
  })

  it("renders custom title", () => {
    render(<ErrorState title="Custom Error" message="Test" />)
    expect(screen.getByText("Custom Error")).toBeInTheDocument()
  })

  it("renders alert-circle icon", () => {
    const { container } = render(<ErrorState message="Test" />)
    expect(container.querySelector("svg")).toBeInTheDocument()
  })

  it("shows retry button when onRetry is provided", () => {
    render(<ErrorState message="Test" onRetry={() => {}} />)
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument()
  })

  it("does not render retry button when onRetry is omitted", () => {
    render(<ErrorState message="Test" />)
    expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument()
  })

  it("fires onRetry when retry button is clicked", async () => {
    const onRetry = vi.fn()
    render(<ErrorState message="Test" onRetry={onRetry} />)
    await userEvent.click(screen.getByRole("button", { name: /try again/i }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it("has fade-in animation class", () => {
    const { container } = render(<ErrorState message="Test" />)
    const card = container.firstChild as HTMLElement
    expect(card.className).toContain("animate-fade-in")
  })
})
