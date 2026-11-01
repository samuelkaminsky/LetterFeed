import { buildOpml, downloadOpml } from "../opml"
import { Newsletter } from "../api"

const newsletter = (overrides: Partial<Newsletter>): Newsletter => ({
  id: "abc123",
  name: "Daily News",
  slug: "daily-news",
  is_active: true,
  extract_content: false,
  senders: [],
  entries_count: 0,
  ...overrides,
})

describe("buildOpml", () => {
  it("lists one absolute, ID-based feed URL per newsletter", () => {
    const opml = buildOpml(
      [newsletter({}), newsletter({ id: "xyz789", name: "Weekly", slug: null })],
      "https://letterfeed.example.com"
    )

    expect(opml).toContain('<opml version="2.0">')
    expect(opml).toContain('xmlUrl="https://letterfeed.example.com/api/feeds/abc123"')
    expect(opml).toContain('xmlUrl="https://letterfeed.example.com/api/feeds/xyz789"')
    expect(opml).not.toContain("daily-news")
    expect(opml.match(/type="rss"/g)).toHaveLength(2)
  })

  it("escapes XML special characters in newsletter names", () => {
    const opml = buildOpml([newsletter({ name: `Tom & Jerry's "<News>"` })], "https://x.test")

    expect(opml).toContain('text="Tom &amp; Jerry&apos;s &quot;&lt;News&gt;&quot;"')
    expect(new DOMParser().parseFromString(opml, "application/xml").querySelector("parsererror")).toBeNull()
  })
})

describe("downloadOpml", () => {
  it("downloads the OPML as letterfeed.opml", () => {
    const createObjectURL = jest.fn(() => "blob:opml")
    const revokeObjectURL = jest.fn()
    Object.assign(URL, { createObjectURL, revokeObjectURL })
    const click = jest.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      expect(this.download).toBe("letterfeed.opml")
      expect(this.href).toBe("blob:opml")
    })

    downloadOpml([newsletter({})], "https://x.test")

    expect(click).toHaveBeenCalledTimes(1)
    expect(createObjectURL).toHaveBeenCalledWith(expect.any(Blob))
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:opml")
    click.mockRestore()
  })
})
