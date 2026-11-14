"use client"

import { useState, useEffect, useRef } from "react"

import withAuth from "@/components/withAuth"
import { useAuth } from "@/hooks/useAuth"
import {
  getNewsletters,
  getSettings,
  getImapFolders,
  Newsletter,
  Settings as AppSettings,
} from "@/lib/api"
import { LoadingSpinner } from "@/components/letterfeed/LoadingSpinner"
import { Header } from "@/components/letterfeed/Header"
import { NewsletterList } from "@/components/letterfeed/NewsletterList"
import { EmptyState } from "@/components/letterfeed/EmptyState"
import { MasterFeedCard } from "@/components/letterfeed/MasterFeedCard"
import { NewsletterDialog } from "@/components/letterfeed/NewsletterDialog"
import { SettingsDialog } from "@/components/letterfeed/SettingsDialog"

async function loadDashboardData() {
  const [newsletters, settings] = await Promise.all([
    getNewsletters(),
    getSettings(),
  ])
  return { newsletters, settings }
}

function LetterFeedApp() {
  const { isAuthEnabled } = useAuth()
  const [newsletters, setNewsletters] = useState<Newsletter[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [folderOptions, setFolderOptions] = useState<string[]>([])

  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false)
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [editingNewsletter, setEditingNewsletter] = useState<Newsletter | null>(null)

  const foldersLoadedRef = useRef(false)
  const foldersInFlightRef = useRef<Promise<void> | null>(null)

  const fetchData = () =>
    loadDashboardData()
      .then((data) => {
        setNewsletters(data.newsletters)
        setSettings(data.settings)
      })
      .catch((error) => {
        console.error("Failed to fetch data:", error)
      })
      .finally(() => {
        setIsLoading(false)
      })

  const refreshFolders = () => {
    if (foldersInFlightRef.current) {
      return foldersInFlightRef.current
    }
    const request = getImapFolders()
      .then((folders) => {
        setFolderOptions(folders)
        foldersLoadedRef.current = true
      })
      .catch((error) => {
        console.error("Failed to fetch IMAP folders:", error)
      })
      .finally(() => {
        foldersInFlightRef.current = null
      })
    foldersInFlightRef.current = request
    return request
  }

  const ensureFoldersLoaded = () => {
    if (!foldersLoadedRef.current) {
      void refreshFolders()
    }
  }

  useEffect(() => {
    let active = true
    loadDashboardData()
      .then((data) => {
        if (!active) return
        setNewsletters(data.newsletters)
        setSettings(data.settings)
      })
      .catch((error) => {
        console.error("Failed to fetch data:", error)
      })
      .finally(() => {
        if (active) {
          setIsLoading(false)
        }
      })
    return () => {
      active = false
    }
  }, [])

  const openAddDialog = () => {
    setIsAddDialogOpen(true)
    ensureFoldersLoaded()
  }

  const openSettingsDialog = () => {
    setIsSettingsOpen(true)
    ensureFoldersLoaded()
  }

  const openEditDialog = (newsletter: Newsletter) => {
    setEditingNewsletter(newsletter)
    ensureFoldersLoaded()
  }

  const closeEditDialog = (open: boolean) => {
    if (!open) {
      setEditingNewsletter(null)
    }
  }

  if (isLoading) {
    return <LoadingSpinner />
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Header
          onOpenAddNewsletter={openAddDialog}
          onOpenSettings={openSettingsDialog}
          onProcessSuccess={fetchData}
        />

        {newsletters.length > 0 && <MasterFeedCard masterFeedToken={settings?.master_feed_token} />}

        {newsletters.length > 0 ? (
          <NewsletterList
            newsletters={newsletters}
            onEditNewsletter={openEditDialog}
            isAuthEnabled={isAuthEnabled}
          />
        ) : (
          <EmptyState onAddNewsletter={openAddDialog} />
        )}

        <NewsletterDialog
          isOpen={isAddDialogOpen}
          folderOptions={folderOptions}
          isAuthEnabled={isAuthEnabled}
          onOpenChange={setIsAddDialogOpen}
          onSuccess={fetchData}
        />

        <NewsletterDialog
          newsletter={editingNewsletter}
          isOpen={!!editingNewsletter}
          folderOptions={folderOptions}
          isAuthEnabled={isAuthEnabled}
          onOpenChange={closeEditDialog}
          onSuccess={() => {
            setEditingNewsletter(null)
            fetchData()
          }}
        />

        {settings && (
          <SettingsDialog
            settings={settings}
            folderOptions={folderOptions}
            isOpen={isSettingsOpen}
            onOpenChange={setIsSettingsOpen}
            onSuccess={() => {
              fetchData()
              foldersLoadedRef.current = false
              void refreshFolders()
            }}
          />
        )}
      </div>
    </div>
  )
}

export default withAuth(LetterFeedApp)
