import React from "react"
import { render, screen } from "@testing-library/react"
import "@testing-library/jest-dom"
import { MasterFeedCard } from "../MasterFeedCard"

// Mock the getMasterFeedUrl function
jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  getMasterFeedUrl: jest.fn(() => "http://mock-api/feeds/all"),
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
})
