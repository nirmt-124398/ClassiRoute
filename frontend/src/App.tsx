import { lazy, Suspense } from "react"
import { Routes, Route, Navigate } from "react-router-dom"
import Layout from "@/components/Layout"

const Login = lazy(() => import("@/pages/Login"))
const Register = lazy(() => import("@/pages/Register"))
const Dashboard = lazy(() => import("@/pages/Dashboard"))
const Keys = lazy(() => import("@/pages/Keys"))
const Analytics = lazy(() => import("@/pages/Analytics"))
const Profile = lazy(() => import("@/pages/Profile"))
const Chat = lazy(() => import("@/pages/Chat"))

function PageLoader() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-border border-t-brand-orange" />
    </div>
  )
}

export default function App() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="/keys" element={<Keys />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
