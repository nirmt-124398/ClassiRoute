import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen, cleanup } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import "@testing-library/jest-dom/vitest"
import { Inbox } from "lucide-react"

import { EmptyState } from "./EmptyState"

afterEach(() => cleanup())

describe("EmptyState", () => {
  it("renders icon, title, and description", () => {
    render(
      <EmptyState
        icon={Inbox}
        title="No items"
        description="You have no items yet."
      />,
    )

    expect(screen.getByText("No items")).toBeInTheDocument()
    expect(screen.getByText("You have no items yet.")).toBeInTheDocument()
  })

  it("renders action button when provided", async () => {
    const onClick = vi.fn()
    render(
      <EmptyState
        icon={Inbox}
        title="No items"
        description="You have no items yet."
        action={{ label: "Create item", onClick }}
      />,
    )

    const button = screen.getByRole("button", { name: "Create item" })
    expect(button).toBeInTheDocument()

    await userEvent.click(button)
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it("does not render button when no action provided", () => {
    render(
      <EmptyState
        icon={Inbox}
        title="No items"
        description="You have no items yet."
      />,
    )

    expect(screen.queryByRole("button")).not.toBeInTheDocument()
  })
})
