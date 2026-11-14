import React from "react"
import { render, screen, fireEvent } from "@testing-library/react"
import "@testing-library/jest-dom"
import { NewsletterCard } from "../NewsletterCard"
import { Newsletter, getFeedUrl } from "@/lib/api"

// Mock the getFeedUrl function
jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  getFeedUrl: jest.fn((newsletter: Newsletter) => `http://mock-api/feeds/${newsletter.slug || newsletter.id}`),
}))

const mockNewsletter: Newsletter = {
  id: "1",
  name: "Tech Weekly",
  slug: "tech-weekly",
  is_active: true,
  extract_content: false,
  senders: [
    { id: "1", email: "contact@techweekly.com" },
    { id: "2", email: "updates@techweekly.com" },
  ],
  entries_count: 42,
}

describe("NewsletterCard", () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it("renders newsletter details correctly", () => {
    const handleEdit = jest.fn()
    render(<NewsletterCard newsletter={mockNewsletter} onEdit={handleEdit} />)

    expect(screen.getByText("Tech Weekly")).toBeInTheDocument()
    expect(screen.queryByText("Paused")).not.toBeInTheDocument()
    expect(screen.getByText("42 entries")).toBeInTheDocument()
    expect(screen.getByText("contact@techweekly.com")).toBeInTheDocument()
    expect(screen.getByText("updates@techweekly.com")).toBeInTheDocument()

    const feedLink = screen.getByRole("link")
    expect(feedLink).toHaveAttribute("href", "http://mock-api/feeds/tech-weekly")
    expect(screen.getByText("http://mock-api/feeds/tech-weekly")).toBeInTheDocument()
    expect(getFeedUrl).toHaveBeenCalledWith(mockNewsletter, true)
  })

  it("passes isAuthEnabled to getFeedUrl", () => {
    render(<NewsletterCard newsletter={mockNewsletter} onEdit={jest.fn()} isAuthEnabled={false} />)
    expect(getFeedUrl).toHaveBeenCalledWith(mockNewsletter, false)
  })

  it('renders a "Paused" badge when newsletter is inactive', () => {
    const pausedNewsletter = { ...mockNewsletter, is_active: false }
    render(<NewsletterCard newsletter={pausedNewsletter} onEdit={jest.fn()} />)
    expect(screen.getByText("Paused")).toBeInTheDocument()
  })

  it('calls the onEdit function with the correct newsletter when the edit button is clicked', () => {
    const handleEdit = jest.fn()
    render(<NewsletterCard newsletter={mockNewsletter} onEdit={handleEdit} />)

    const editButton = screen.getByRole("button", { name: /edit newsletter/i })
    fireEvent.click(editButton)

    expect(handleEdit).toHaveBeenCalledTimes(1)
    expect(handleEdit).toHaveBeenCalledWith(mockNewsletter)
  })

  it('displays "entry" for a single entry', () => {
    const singleEntryNewsletter = { ...mockNewsletter, entries_count: 1 }
    render(<NewsletterCard newsletter={singleEntryNewsletter} onEdit={jest.fn()} />)

    expect(screen.getByText("1 entry")).toBeInTheDocument()
  })
})
