import React from 'react'
import { useAuth } from './AuthContext'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export const UserProfile: React.FC = () => {
  const { user, signOut } = useAuth()

  const handleSignOut = async () => {
    await signOut()
  }

  return (
    <div className="p-6 max-w-md mx-auto">
      <Card>
        <CardHeader>
          <CardTitle>User Profile</CardTitle>
          <CardDescription>Your account information</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">Email</label>
            <p className="text-sm text-gray-900 bg-gray-50 p-2 rounded border">
              {user?.email}
            </p>
          </div>
          
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">User ID</label>
            <p className="text-sm text-gray-900 bg-gray-50 p-2 rounded border font-mono">
              {user?.id}
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">Last Sign In</label>
            <p className="text-sm text-gray-900 bg-gray-50 p-2 rounded border">
              {user?.last_sign_in_at ? new Date(user.last_sign_in_at).toLocaleString() : 'Never'}
            </p>
          </div>

          <Button 
            onClick={handleSignOut} 
            variant="destructive" 
            className="w-full"
          >
            Sign Out
          </Button>
        </CardContent>
      </Card>
    </div>
  )
} 