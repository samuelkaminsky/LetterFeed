import { getFeedUrl, type Newsletter } from "@/lib/api"
import { toAbsoluteUrl } from "@/hooks/useOrigin"

const escapeXml = (value: string) =>
  value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;")

/**
 * Build an OPML 2.0 subscription list with one outline per newsletter feed.
 * Feeds use the secure newsletter ID (never the slug), which is the only form
 * served when authentication is enabled.
 */
export function buildOpml(newsletters: Newsletter[], origin: string): string {
  const outlines = newsletters
    .map((newsletter) => {
      const name = escapeXml(newsletter.name)
      const xmlUrl = escapeXml(toAbsoluteUrl(getFeedUrl(newsletter), origin))
      return `      <outline type="rss" text="${name}" title="${name}" xmlUrl="${xmlUrl}" />`
    })
    .join("\n")

  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<opml version="2.0">',
    "  <head>",
    "    <title>LetterFeed Newsletters</title>",
    `    <dateCreated>${new Date().toUTCString()}</dateCreated>`,
    "  </head>",
    "  <body>",
    '    <outline text="LetterFeed" title="LetterFeed">',
    outlines,
    "    </outline>",
    "  </body>",
    "</opml>",
    "",
  ].join("\n")
}

/** Trigger a browser download of the OPML subscription list. */
export function downloadOpml(newsletters: Newsletter[], origin: string): void {
  const blob = new Blob([buildOpml(newsletters, origin)], { type: "text/x-opml" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = "letterfeed.opml"
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
