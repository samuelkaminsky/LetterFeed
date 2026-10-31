import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"
import "@testing-library/jest-dom"
import { MasterFeedCard } from "../MasterFeedCard"
import { downloadOpml } from "@/lib/opml"
import { Newsletter } from "@/lib/api"

// Mock the getMasterFeedUrl function
jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  getMasterFeedUrl: jest.fn(() => "http://mock-api/feeds/all"),
}))

jest.mock("@/lib/opml", () => ({
  downloadOpml: jest.fn(),
}))

// Mock the toast
jest.mock("sonner", () => ({
  toast: {
    success: jest.fn(),
  },
}))

// Mock navigator.clipboard
Object.assign(navigator, {
  clipboard: {
    writeText: jest.fn(),
  },
})

describe("MasterFeedCard", () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it("renders the master feed card with the correct URL", () => {
    render(<MasterFeedCard />)

    expect(screen.getByText("Master RSS Feed")).toBeInTheDocument()
    expect(
      screen.getByText(
        "Subscribing to this aggregated feed lets you receive new entries from all of your newsletters combined in a single channel in your RSS reader."
      )
    ).toBeInTheDocument()

    const feedLink = screen.getByRole("link")
    expect(feedLink).toHaveAttribute("href", "http://mock-api/feeds/all")
    expect(screen.getByText("http://mock-api/feeds/all")).toBeInTheDocument()
  })

  it("hides the OPML export when there are no newsletters", () => {
    render(<MasterFeedCard />)
    expect(screen.queryByRole("button", { name: /export opml/i })).not.toBeInTheDocument()
  })

  it("exports the newsletters as OPML when clicked", () => {
    const newsletters: Newsletter[] = [
      {
        id: "abc123",
        name: "Daily News",
        slug: null,
        is_active: true,
        extract_content: false,
        senders: [],
        entries_count: 0,
      },
    ]
    render(<MasterFeedCard newsletters={newsletters} />)

    fireEvent.click(screen.getByRole("button", { name: /export opml/i }))
    expect(downloadOpml).toHaveBeenCalledWith(newsletters, expect.any(String))
  })
})
