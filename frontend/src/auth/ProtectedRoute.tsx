import React from 'react'
import { useAuth } from './AuthContext'
import { LoginForm } from './LoginForm'

interface ProtectedRouteProps {
  children: React.ReactNode
}

// Check if auth is enabled via environment variable
const AUTH_ENABLED = import.meta.env.VITE_AUTH_ENABLED === 'true'

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { user, loading } = useAuth()

  // Dev mode: bypass auth when VITE_AUTH_ENABLED=false
  if (!AUTH_ENABLED) {
    return <>{children}</>
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (!user) {
    return <LoginForm />
  }

  return <>{children}</>
}
