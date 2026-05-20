import { useState, useEffect } from "react"
import { Outlet, useNavigate, useLocation } from "react-router-dom"
import {
  LayoutDashboard,
  Key,
  BarChart3,
  MessageSquare,
  Menu,
  LogOut,
  ChevronDown,
  User,
} from "lucide-react"
import { useAuth } from "@/context/AuthContext"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/Button"
import { Separator } from "@/components/ui/Separator"
import * as DropdownMenu from "@radix-ui/react-dropdown-menu"

const navItems = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard },
  { path: "/chat", label: "Playground", icon: MessageSquare },
  { path: "/keys", label: "Keys", icon: Key },
  { path: "/analytics", label: "Analytics", icon: BarChart3 },
]

const pageTitles: Record<string, string> = {
  "/": "Dashboard",
  "/chat": "Playground",
  "/keys": "API Keys",
  "/analytics": "Analytics",
}

export default function Layout() {
  const { user, loading, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    if (!loading && !user) {
      navigate("/login", { replace: true })
    }
  }, [user, loading, navigate])

  if (loading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-brand-bg">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-border border-t-brand-orange" />
          <p className="text-sm text-brand-muted font-body">Loading…</p>
        </div>
      </div>
    )
  }

  if (!user) return null

  const pageTitle = pageTitles[location.pathname] ?? "ClassiRoute"

  return (
    <div className="flex h-screen bg-brand-bg">
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-brand-border bg-brand-surface transition-transform duration-200 lg:static lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-16 items-center gap-2 px-6">
          <div className="flex h-8 w-8 items-center justify-center rounded-sm bg-brand-bg text-[10px] font-bold tracking-widest text-white font-heading">
            C
          </div>
          <span className="font-heading text-lg font-semibold text-brand-text tracking-tight">
            ClassiRoute
          </span>
        </div>

        <Separator />

        <nav className="flex-1 space-y-1 px-3 py-4">
          {navItems.map((item) => {
            const isActive =
              item.path === "/"
                ? location.pathname === "/"
                : location.pathname.startsWith(item.path)
            const Icon = item.icon
            return (
              <button
                key={item.path}
                onClick={() => {
                  navigate(item.path)
                  setSidebarOpen(false)
                }}
                className={cn(
                  "flex w-full items-center gap-3 rounded-sm px-3 py-2.5 text-sm font-heading font-medium transition-all duration-150 ease-out border-r-2",
                  isActive
                    ? "border-brand-orange bg-brand-orange/10 text-brand-orange"
                    : "border-transparent text-brand-muted hover:bg-brand-border hover:text-brand-text",
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </button>
            )
          })}
        </nav>

        <Separator />

        <div className="p-4">
          <p className="text-xs text-brand-muted font-body">
            ClassiRoute Admin
          </p>
        </div>
      </aside>

      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-16 items-center justify-between border-b border-brand-border bg-brand-surface px-4 lg:px-6">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden text-brand-muted hover:text-brand-text"
              aria-label="Open sidebar"
            >
              <Menu className="h-5 w-5" />
            </button>
            <h1 className="font-heading text-lg font-semibold text-brand-text">
              {pageTitle}
            </h1>
          </div>

          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <button className="flex items-center gap-2 rounded-sm px-3 py-1.5 text-sm font-body text-brand-text transition-all duration-150 ease-out hover:bg-brand-border">
                <User className="h-4 w-4 text-brand-muted" />
                <span className="hidden sm:inline">{user.username}</span>
                <ChevronDown className="h-3 w-3 text-brand-muted" />
              </button>
            </DropdownMenu.Trigger>

            <DropdownMenu.Portal>
              <DropdownMenu.Content
                align="end"
                sideOffset={4}
                className="z-50 min-w-40 overflow-hidden rounded-sm border border-brand-border bg-brand-surface p-1 shadow-md animate-in fade-in-80"
              >
                <DropdownMenu.Item
                  onSelect={() => navigate("/")}
                  className="relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm font-body text-brand-text outline-none transition-all duration-150 ease-out hover:bg-brand-surface"
                >
                  <LayoutDashboard className="mr-2 h-4 w-4 text-brand-muted" />
                  Dashboard
                </DropdownMenu.Item>
                <DropdownMenu.Item
                  onSelect={() => navigate("/profile")}
                  className="relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm font-body text-brand-text outline-none transition-all duration-150 ease-out hover:bg-brand-surface"
                >
                  <User className="mr-2 h-4 w-4 text-brand-muted" />
                  Profile
                </DropdownMenu.Item>
                <DropdownMenu.Separator className="my-1 h-px bg-brand-border" />
                <DropdownMenu.Item
                  onSelect={logout}
                  className="relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm font-body text-red-400 outline-none transition-all duration-150 ease-out hover:bg-red-950/40"
                >
                  <LogOut className="mr-2 h-4 w-4" />
                  Log out
                </DropdownMenu.Item>
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        </header>

        <main className="flex-1 overflow-y-auto p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
