import React from "react"
import { render, screen, fireEvent } from "@testing-library/react"
import "@testing-library/jest-dom"
import { NewsletterCard } from "../NewsletterCard"
import { Newsletter } from "@/lib/api"

// Mock the getFeedUrl function
jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"), // import and retain all actual implementations
  getFeedUrl: jest.fn((newsletter: Newsletter) => `http://mock-api/feeds/${newsletter.slug || newsletter.id}`),
}))

const mockNewsletter: Newsletter = {
  id: "1",
  name: "Tech Weekly",
  slug: "tech-weekly",
  is_active: true,
  senders: [
    { id: "1", email: "contact@techweekly.com" },
    { id: "2", email: "updates@techweekly.com" },
  ],
  entries_count: 42,
}

describe("NewsletterCard", () => {
  it("renders newsletter details correctly", () => {
    const handleEdit = jest.fn()
    render(<NewsletterCard newsletter={mockNewsletter} onEdit={handleEdit} />)

    // Check for the title
    expect(screen.getByText("Tech Weekly")).toBeInTheDocument()

    // Check for the entries count
    expect(screen.getByText("42 entries")).toBeInTheDocument()

    // Check for sender emails
    expect(screen.getByText("contact@techweekly.com")).toBeInTheDocument()
    expect(screen.getByText("updates@techweekly.com")).toBeInTheDocument()

    // Check for the RSS feed link
    const feedLink = screen.getByRole("link")
    expect(feedLink).toHaveAttribute("href", "http://mock-api/feeds/tech-weekly")
    expect(screen.getByText("http://mock-api/feeds/tech-weekly")).toBeInTheDocument()
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
    const handleEdit = jest.fn()
    render(<NewsletterCard newsletter={singleEntryNewsletter} onEdit={handleEdit} />)

    expect(screen.getByText("1 entry")).toBeInTheDocument()
  })
})
