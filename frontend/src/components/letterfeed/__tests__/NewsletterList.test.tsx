import React from "react"
import { render, screen } from "@testing-library/react"
import "@testing-library/jest-dom"
import { NewsletterList } from "../NewsletterList"
import { Newsletter } from "@/lib/api"

// Mock the child component to isolate the list component's behavior
jest.mock("../NewsletterCard", () => ({
  NewsletterCard: ({ newsletter }: { newsletter: Newsletter }) => (
    <div data-testid={`newsletter-card-${newsletter.id}`}>{newsletter.name}</div>
  ),
}))

const mockNewsletters: Newsletter[] = [
  {
    id: "1",
    name: "Newsletter One",
    slug: null,
    is_active: true,
    extract_content: false,
    senders: [],
    entries_count: 10,
  },
  {
    id: "2",
    name: "Newsletter Two",
    slug: null,
    is_active: true,
    extract_content: false,
    senders: [],
    entries_count: 5,
  },
]

describe("NewsletterList", () => {
  it("renders a list of newsletter cards", () => {
    render(<NewsletterList newsletters={mockNewsletters} onEditNewsletter={() => {}} />)

    // Check that both newsletters are rendered
    expect(screen.getByText("Newsletter One")).toBeInTheDocument()
    expect(screen.getByText("Newsletter Two")).toBeInTheDocument()
    expect(screen.getByTestId("newsletter-card-1")).toBeInTheDocument()
    expect(screen.getByTestId("newsletter-card-2")).toBeInTheDocument()
  })

  it("renders nothing when the newsletter list is empty", () => {
    const { container } = render(<NewsletterList newsletters={[]} onEditNewsletter={() => {}} />)
    // The main div should be empty
    expect(container.firstChild).toBeEmptyDOMElement()
  })
})
