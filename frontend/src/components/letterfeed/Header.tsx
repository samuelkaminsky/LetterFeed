"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { processEmails } from "@/lib/api"
import { useAuth } from "@/hooks/useAuth"
import { LogOut, Mail, Plus, Settings, Loader2 } from "lucide-react"
import Image from "next/image"
import { toast } from "sonner"

interface HeaderProps {
  onOpenAddNewsletter: () => void
  onOpenSettings: () => void
}

export function Header({ onOpenAddNewsletter, onOpenSettings }: HeaderProps) {
  const { logout, isAuthEnabled } = useAuth()
  const [isProcessing, setIsProcessing] = useState(false)

  const handleProcessEmails = async () => {
    setIsProcessing(true)
    try {
      await processEmails()
      toast.success("Email processing finished successfully!")
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "An unexpected error occurred."
      console.error(error)
      toast.error(message)
    } finally {
      setIsProcessing(false)
    }
  }

  return (
    <div className="flex flex-col md:flex-row items-center justify-between mb-8">
      <div className="flex items-center gap-4 mb-4 md:mb-0">
        <Image
          src="/logo.png"
          alt="LetterFeed Logo"
          width={48}
          height={48}
          className="rounded-lg"
        />
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-foreground">LetterFeed</h1>
          <p className="text-muted-foreground mt-1 hidden md:block">
            Newsletters as RSS feeds
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button onClick={onOpenAddNewsletter} disabled={isProcessing}>
          <Plus className="w-4 h-4 mr-2" />
          Add Newsletter
        </Button>

        <Button variant="outline" onClick={handleProcessEmails} disabled={isProcessing}>
          {isProcessing ? (
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <Mail className="w-4 h-4 mr-2" />
          )}
          {isProcessing ? "Processing..." : "Process Now"}
        </Button>

        <Button variant="outline" onClick={onOpenSettings} disabled={isProcessing}>
          <Settings className="w-4 h-4 mr-2" />
          Settings
        </Button>

        {isAuthEnabled && (
          <Button variant="outline" onClick={logout}>
            <LogOut className="w-4 h-4 mr-2" />
            Logout
          </Button>
        )}
      </div>
    </div>
  )
}
