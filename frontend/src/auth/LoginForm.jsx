import React, { useState } from 'react'
import { useAuth } from './AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import loginImage from './qqw.png'

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


  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="flex w-full max-w-6xl bg-white rounded-lg shadow-lg overflow-hidden" style={{ transform: 'scale(1.1)' }}>
        {/* Left side - Illustration */}
        <div className="hidden lg:flex lg:w-5/12 bg-gray-50 p-12 items-center justify-center">
          <img 
            src={loginImage} 
            alt="Computer workspace illustration with monitor, keyboard, mouse, desk lamp and phone"
            className="w-full h-auto object-contain"
          />
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
                      backgroundColor: '#f9fafb',
                      borderColor: '#e5e7eb'
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