import React, { useState } from 'react'
import { useAuth } from './AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export const LoginForm = () => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [rememberMe, setRememberMe] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  
  const { signIn } = useAuth()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const { error } = await signIn(email, password)

      if (error) {
        setError(error.message)
      }
    } catch (err) {
      setError('An unexpected error occurred')
    } finally {
      setLoading(false)
    }
  }

  const ComputerIllustration = () => (
    <svg viewBox="0 0 400 400" className="w-full h-full">
      {/* Desk Lamp */}
      <g>
        <circle cx="80" cy="100" r="35" fill="#e5e7eb" stroke="#9ca3af" strokeWidth="2"/>
        <path d="M80 100 L80 250" stroke="#6b7280" strokeWidth="4"/>
        <circle cx="80" cy="250" r="15" fill="#6b7280"/>
        <path d="M65 250 L95 250" stroke="#6b7280" strokeWidth="4"/>
      </g>
      
      {/* Monitor */}
      <g>
        <rect x="120" y="120" width="180" height="120" rx="8" fill="#3b82f6" stroke="#1e40af" strokeWidth="3"/>
        <rect x="130" y="130" width="160" height="100" fill="#dbeafe"/>
        <circle cx="210" cy="180" r="25" fill="#ffffff"/>
        <path d="M195 235 L225 235" stroke="#1e40af" strokeWidth="3"/>
        <rect x="180" y="235" width="60" height="5" fill="#1e40af"/>
        <rect x="190" y="240" width="40" height="15" fill="#6b7280"/>
      </g>
      
      {/* Keyboard */}
      <g>
        <rect x="140" y="280" width="140" height="50" rx="5" fill="#e5e7eb" stroke="#9ca3af" strokeWidth="2"/>
        <rect x="150" y="290" width="120" height="30" rx="3" fill="#ffffff"/>
        {/* Keyboard dots pattern */}
        {[...Array(4)].map((_, row) => (
          [...Array(10)].map((_, col) => (
            <circle 
              key={`${row}-${col}`}
              cx={160 + col * 11} 
              cy={297 + row * 7} 
              r="2" 
              fill="#9ca3af"
            />
          ))
        ))}
      </g>
      
      {/* Mouse */}
      <g>
        <ellipse cx="120" cy="305" rx="15" ry="25" fill="#e5e7eb" stroke="#9ca3af" strokeWidth="2"/>
        <line x1="120" y1="290" x2="120" y2="305" stroke="#9ca3af" strokeWidth="1"/>
      </g>
      
      {/* Phone/Device */}
      <g>
        <rect x="300" y="200" width="40" height="70" rx="5" fill="#1e40af" stroke="#1e3a8a" strokeWidth="2"/>
        <rect x="305" y="210" width="30" height="50" fill="#3b82f6"/>
        <line x1="310" y1="220" x2="330" y2="240" stroke="#ffffff" strokeWidth="3"/>
        <line x1="330" y1="220" x2="310" y2="240" stroke="#ffffff" strokeWidth="3"/>
      </g>
    </svg>
  )

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="flex w-full max-w-6xl bg-white rounded-lg shadow-lg overflow-hidden">
        {/* Left side - Illustration */}
        <div className="hidden lg:flex lg:w-5/12 bg-gray-50 p-12 items-center justify-center">
          <ComputerIllustration />
        </div>
        
        {/* Right side - Form */}
        <div className="w-full lg:w-7/12 p-8 lg:p-12">
          {/* Brand Header */}
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-blue-600 mb-2">Valiant Precision</h1>
            <p className="text-sm text-gray-600">AI Optimizer</p>
          </div>

          <Card>
            <CardHeader className="space-y-1">
              <CardTitle className="text-2xl text-center">
                Sign In
              </CardTitle>
              <CardDescription className="text-center">
                Enter your email and password to access your account
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm">
                  {error}
                </div>
              )}
              
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="Enter your email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    disabled={loading}
                  />
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    type="password"
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    disabled={loading}
                  />
                </div>

                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="remember"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="w-4 h-4 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 cursor-pointer"
                    style={{
                      backgroundColor: '#f3f4f6',
                      borderColor: '#d1d5db',
                      accentColor: '#6b7280'
                    }}
                  />
                  <Label htmlFor="remember" className="text-sm font-normal cursor-pointer">
                    Keep me signed in on this device
                  </Label>
                </div>

                <Button 
                  type="submit" 
                  className="w-full" 
                  disabled={loading}
                >
                  {loading ? 'Loading...' : 'Sign In'}
                </Button>
              </form>

            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
} 