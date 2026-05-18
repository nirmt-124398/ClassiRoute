import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { getProfile, updateProfile, type UserProfile } from "@/api/users"
import { ApiError } from "@/api/client"
import { useAuth } from "@/context/AuthContext"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { Loader2, User, Save } from "lucide-react"

export default function Profile() {
  const { loading: authLoading, logout } = useAuth()
  const navigate = useNavigate()
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [username, setUsername] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")
  const [success, setSuccess] = useState("")

  useEffect(() => {
    if (authLoading) return
    getProfile()
      .then((p) => {
        setProfile(p)
        setUsername(p.username)
        setEmail(p.email)
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          navigate("/login", { replace: true })
          return
        }
        setError(err instanceof Error ? err.message : "Failed to load profile")
      })
      .finally(() => setLoading(false))
  }, [authLoading, navigate])

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setError("")
    setSuccess("")
    setSaving(true)

    try {
      const payload: Record<string, string> = {}
      if (username !== profile?.username) payload.username = username
      if (email !== profile?.email) payload.email = email
      if (password) payload.password = password

      if (Object.keys(payload).length === 0) {
        setSuccess("No changes to save.")
        setSaving(false)
        return
      }

      const updated = await updateProfile(payload)
      setProfile(updated)
      setPassword("")
      setSuccess("Profile updated successfully.")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update profile")
    } finally {
      setSaving(false)
    }
  }

  if (authLoading || loading) {
    return (
      <div className="animate-fade-in">
        <div className="flex h-full items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-brand-orange" />
        </div>
      </div>
    )
  }

  if (!profile) {
    return (
      <div className="animate-fade-in">
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <User className="mb-4 h-12 w-12 text-brand-mid" />
          <p className="text-sm text-brand-mid font-body">{error || "Could not load profile."}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="animate-fade-in">
    <div className="mx-auto max-w-lg space-y-6">
      <div>
        <h1 className="font-heading text-xl font-semibold text-brand-dark">Profile</h1>
        <p className="text-sm text-brand-mid font-body">Manage your account settings</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Account Info</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSave} className="space-y-4">
            <div className="space-y-1">
              <label className="font-body text-xs text-brand-muted">
                Username
              </label>
              <Input value={username} onChange={(e) => setUsername(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="font-body text-xs text-brand-muted">
                Email
              </label>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="font-body text-xs text-brand-muted">
                New Password <span className="font-normal normal-case text-brand-muted/60">(leave blank to keep current)</span>
              </label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter new password"
              />
            </div>

            {error && (
              <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>
            )}
            {success && (
              <div className="rounded-lg bg-green-50 p-3 text-sm text-green-600">{success}</div>
            )}

            <div className="flex gap-3">
              <Button type="submit" disabled={saving}>
                {saving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Save className="h-4 w-4" />
                )}
                Save Changes
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={logout}
                className="text-red-600 hover:text-red-700"
              >
                Logout
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
    </div>
  )
}