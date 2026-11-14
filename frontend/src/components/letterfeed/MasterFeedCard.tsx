"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Rss, ExternalLink, Copy, Check, Download } from "lucide-react"
import { getMasterFeedUrl, type Newsletter } from "@/lib/api"
import { downloadOpml } from "@/lib/opml"
import { toast } from "sonner"
import { toAbsoluteUrl, useOrigin } from "@/hooks/useOrigin"

interface MasterFeedCardProps {
  masterFeedToken?: string | null
  newsletters?: Newsletter[]
}

export function MasterFeedCard({ masterFeedToken, newsletters = [] }: MasterFeedCardProps) {
  const feedUrl = getMasterFeedUrl(masterFeedToken)
  const origin = useOrigin()
  const absoluteUrl = toAbsoluteUrl(feedUrl, origin)
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(absoluteUrl)
      setCopied(true)
      toast.success("Master feed link copied to clipboard!")
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error("Failed to copy feed URL:", err)
      toast.error("Failed to copy link.")
    }
  }

  return (
    <Card className="mb-8 border border-orange-100 dark:border-orange-950 bg-gradient-to-br from-white to-orange-50/20 dark:from-neutral-900 dark:to-orange-950/10 hover:shadow-md transition-shadow">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-lg font-bold">
          <Rss className="w-5 h-5 text-orange-500 motion-safe:animate-pulse" />
          Master RSS Feed
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground leading-relaxed">
          Subscribing to this aggregated feed lets you receive new entries from all of your newsletters combined in a single channel in your RSS reader.
        </p>
        <div className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Aggregated RSS URL
          </h4>
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 bg-neutral-50 dark:bg-neutral-800/50 p-2.5 rounded-lg border border-neutral-200 dark:border-neutral-800">
            <span className="font-mono text-xs text-neutral-600 dark:text-neutral-400 break-all select-all flex-grow px-1.5 py-1">
              {absoluteUrl}
            </span>
            <div className="flex items-center gap-2 self-end sm:self-auto">
              <Button
                variant="outline"
                size="sm"
                onClick={handleCopy}
                className="h-8 text-xs flex items-center gap-1.5 font-medium hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
              >
                {copied ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-green-500 motion-safe:animate-in motion-safe:zoom-in-75 duration-150" />
                    <span>Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5 text-neutral-500" />
                    <span>Copy</span>
                  </>
                )}
              </Button>
              <a
                href={absoluteUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="h-8 px-2.5 inline-flex items-center justify-center rounded-md border border-neutral-200 dark:border-neutral-800 text-xs font-medium hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-700 dark:text-neutral-300 transition-colors"
                title="Open feed in browser"
              >
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>
          </div>
        </div>
        {newsletters.length > 0 && (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1">
            <p className="text-xs text-muted-foreground">
              Prefer one feed per newsletter? Export them all as OPML and import the file into your RSS reader.
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => downloadOpml(newsletters, origin)}
              className="h-8 text-xs flex items-center gap-1.5 font-medium self-end sm:self-auto shrink-0"
            >
              <Download className="w-3.5 h-3.5 text-neutral-500" />
              <span>Export OPML</span>
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
