import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { Skeleton, SkeletonCard, SkeletonText, SkeletonTable, SkeletonStat } from "./Skeleton"

describe("Skeleton", () => {
  it("renders base skeleton with animate-pulse class", () => {
    const { container } = render(<Skeleton />)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain("animate-pulse")
    expect(el.className).toContain("bg-brand-border")
    expect(el.className).toContain("rounded-sm")
  })

  it("accepts custom className", () => {
    const { container } = render(<Skeleton className="h-10 w-20" />)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain("h-10")
    expect(el.className).toContain("w-20")
  })
})

describe("SkeletonCard", () => {
  it("renders with card-like structure", () => {
    const { container } = render(<SkeletonCard />)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain("border-brand-border")
    expect(el.className).toContain("bg-brand-surface")
  })

  it("accepts custom className", () => {
    const { container } = render(<SkeletonCard className="max-w-md" />)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain("max-w-md")
  })
})

describe("SkeletonText", () => {
  it("renders a text-line shaped skeleton", () => {
    const { container } = render(<SkeletonText />)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain("h-4")
    expect(el.className).toContain("animate-pulse")
  })

  it("accepts custom className for width", () => {
    const { container } = render(<SkeletonText className="w-3/4" />)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain("w-3/4")
  })
})

describe("SkeletonTable", () => {
  it("renders default 5 rows", () => {
    const { container } = render(<SkeletonTable />)
    // Each row has 4 skeleton cells, the outer wrapper is the container
    const rows = container.firstChild as HTMLElement
    expect(rows.children.length).toBe(5)
  })

  it("renders configurable row count", () => {
    const { container } = render(<SkeletonTable rows={3} />)
    const rows = container.firstChild as HTMLElement
    expect(rows.children.length).toBe(3)
  })

  it("accepts custom className", () => {
    const { container } = render(<SkeletonTable className="max-w-lg" />)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain("max-w-lg")
  })
})

describe("SkeletonStat", () => {
  it("renders stat card skeleton with icon circle", () => {
    const { container } = render(<SkeletonStat />)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain("border-brand-border")
    expect(el.className).toContain("bg-brand-surface")
    // Should contain a rounded-full skeleton (icon placeholder)
    const circles = el.querySelectorAll<HTMLElement>(".rounded-full")
    expect(circles.length).toBeGreaterThanOrEqual(1)
  })

  it("accepts custom className", () => {
    const { container } = render(<SkeletonStat className="min-w-48" />)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain("min-w-48")
  })
})
