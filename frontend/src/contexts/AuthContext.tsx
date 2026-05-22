"use client"

import { createContext, useState, useEffect, ReactNode } from "react"
import { getAuthStatus, login as apiLogin, logout as apiLogout, verifyAuth } from "@/lib/api"
import { useRouter } from "next/navigation"

interface AuthContextType {
  isAuthenticated: boolean
  isAuthEnabled: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  isLoading: boolean
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isAuthEnabled, setIsAuthEnabled] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    const checkAuth = async () => {
      setIsLoading(true);
      try {
        const { auth_enabled } = await getAuthStatus();
        setIsAuthEnabled(auth_enabled);
        if (!auth_enabled) {
          setIsAuthenticated(true);
        } else {
          const isValid = await verifyAuth();
          setIsAuthenticated(isValid);
        }
      } catch (error) {
        setIsAuthenticated(false);
        console.error("Authentication check failed", error);
      } finally {
        setIsLoading(false);
      }
    };
    checkAuth();
  }, []);

  const login = async (username: string, password: string) => {
    try {
      await apiLogin(username, password)
      setIsAuthenticated(true)
      router.push("/")
    } catch (error) {
      console.error("Login failed", error)
      throw error
    }
  }

  const logout = () => {
    apiLogout().catch((error) => {
      console.error("Logout API call failed", error);
    });
    setIsAuthenticated(false)
    router.push("/login")
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated, isAuthEnabled, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  )
}
