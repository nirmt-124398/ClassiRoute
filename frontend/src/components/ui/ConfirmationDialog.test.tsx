import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen, cleanup } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import "@testing-library/jest-dom/vitest"
import { ConfirmationDialog } from "./ConfirmationDialog"

afterEach(() => cleanup())

describe("ConfirmationDialog", () => {
  it("renders title and description when open", () => {
    render(
      <ConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        title="Delete item"
        description="Are you sure you want to delete this item?"
        onConfirm={() => {}}
      />,
    )

    expect(screen.getByText("Delete item")).toBeInTheDocument()
    expect(
      screen.getByText("Are you sure you want to delete this item?"),
    ).toBeInTheDocument()
  })

  it("does not render when closed", () => {
    render(
      <ConfirmationDialog
        open={false}
        onOpenChange={() => {}}
        title="Delete item"
        description="Are you sure?"
        onConfirm={() => {}}
      />,
    )

    expect(screen.queryByText("Delete item")).not.toBeInTheDocument()
  })

  it("calls onConfirm when confirm button is clicked", async () => {
    const onConfirm = vi.fn()
    const user = userEvent.setup()

    render(
      <ConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        title="Are you sure?"
        description="This action cannot be undone."
        onConfirm={onConfirm}
        confirmLabel="Yes, delete"
      />,
    )

    await user.click(screen.getByRole("button", { name: "Yes, delete" }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it("calls onOpenChange with false when cancel is clicked", async () => {
    const onOpenChange = vi.fn()
    const user = userEvent.setup()

    render(
      <ConfirmationDialog
        open={true}
        onOpenChange={onOpenChange}
        title="Confirm"
        description="Test"
        onConfirm={() => {}}
      />,
    )

    await user.click(screen.getByRole("button", { name: "Cancel" }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it("danger variant shows destructive button styling", () => {
    render(
      <ConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        title="Destructive action"
        description="This cannot be undone."
        onConfirm={() => {}}
        variant="danger"
        confirmLabel="Delete"
      />,
    )

    const btn = screen.getByRole("button", { name: "Delete" })
    expect(btn).toBeInTheDocument()
    // Destructive variant has bg-red-600 class
    expect(btn.className).toContain("bg-red-600")
  })

  it("renders default variant with default button styling", () => {
    render(
      <ConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        title="Confirm action"
        description="Proceed?"
        onConfirm={() => {}}
        variant="default"
        confirmLabel="Save"
      />,
    )

    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument()
  })

  it("uses custom labels when provided", () => {
    render(
      <ConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        title="Confirm"
        description="Go ahead?"
        onConfirm={() => {}}
        confirmLabel="Yes, proceed"
        cancelLabel="No, go back"
      />,
    )

    expect(
      screen.getByRole("button", { name: "Yes, proceed" }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "No, go back" }),
    ).toBeInTheDocument()
  })

  it("handles async onConfirm", async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined)
    const user = userEvent.setup()

    render(
      <ConfirmationDialog
        open={true}
        onOpenChange={() => {}}
        title="Please confirm"
        description="Continue?"
        onConfirm={onConfirm}
        confirmLabel="Continue"
      />,
    )

    await user.click(screen.getByRole("button", { name: "Continue" }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })
})
