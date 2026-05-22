"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Rss, Mail, ExternalLink, Edit, Copy, Check } from "lucide-react"
import { Newsletter, getFeedUrl } from "@/lib/api"
import { toast } from "sonner"

interface NewsletterCardProps {
  newsletter: Newsletter
  onEdit: (newsletter: Newsletter) => void
}

export function NewsletterCard({ newsletter, onEdit }: NewsletterCardProps) {
  const feedUrl = getFeedUrl(newsletter)
  const [absoluteUrl, setAbsoluteUrl] = useState(feedUrl)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (typeof window !== "undefined") {
      if (feedUrl.startsWith("http://") || feedUrl.startsWith("https://")) {
        setAbsoluteUrl(feedUrl)
      } else {
        setAbsoluteUrl(`${window.location.origin}${feedUrl}`)
      }
    }
  }, [feedUrl])

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(absoluteUrl)
      setCopied(true)
      toast.success(`Feed link for ${newsletter.name} copied!`)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error("Failed to copy feed URL:", err)
      toast.error("Failed to copy link.")
    }
  }

  return (
    <Card className="hover:shadow-md transition-shadow flex flex-col">
      <CardHeader>
        <div className="flex justify-between items-start">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Rss className="w-5 h-5 text-orange-500" />
              {newsletter.name}
            </CardTitle>
            <CardDescription>
              {newsletter.entries_count} entr{newsletter.entries_count !== 1 ? "ies" : "y"}
            </CardDescription>
          </div>
          <Button variant="ghost" size="icon" onClick={() => onEdit(newsletter)} aria-label="Edit Newsletter">
            <Edit className="w-4 h-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 flex-grow">
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-1">
            <Mail className="w-4 h-4" />
            Email Addresses
          </h4>
          <div className="flex flex-wrap gap-1">
            {newsletter.senders.map((sender) => (
              <Badge key={sender.id} variant="secondary" className="text-xs">
                {sender.email}
              </Badge>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            RSS Feed URL
          </h4>
          <div className="flex items-center gap-1.5 bg-neutral-50 dark:bg-neutral-800/50 p-1.5 rounded-md border border-neutral-200 dark:border-neutral-800">
            <span className="font-mono text-[10px] text-neutral-600 dark:text-neutral-400 break-all select-all flex-grow px-1 py-0.5 min-w-0">
              {absoluteUrl}
            </span>
            <div className="flex items-center gap-1 shrink-0">
              <Button
                variant="outline"
                size="icon"
                onClick={handleCopy}
                className="h-7 w-7 text-xs flex items-center justify-center hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
                title="Copy RSS URL"
              >
                {copied ? (
                  <Check className="w-3.5 h-3.5 text-green-500 animate-scale" />
                ) : (
                  <Copy className="w-3.5 h-3.5 text-neutral-500" />
                )}
              </Button>
              <a
                href={absoluteUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="h-7 w-7 inline-flex items-center justify-center rounded-md border border-neutral-200 dark:border-neutral-800 text-xs font-medium hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-700 dark:text-neutral-300 transition-colors"
                title="Open feed in browser"
              >
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
