import React from "react"
import { render, screen } from "@testing-library/react"
import "@testing-library/jest-dom"
import { NewsletterList } from "../NewsletterList"
import { Newsletter } from "@/lib/api"

// Mock the child component to isolate the list component's behavior
jest.mock("../NewsletterCard", () => ({
  NewsletterCard: ({
    newsletter,
    isAuthEnabled,
  }: {
    newsletter: Newsletter
    isAuthEnabled?: boolean
  }) => (
    <div
      data-testid={`newsletter-card-${newsletter.id}`}
      data-auth-enabled={String(isAuthEnabled)}
    >
      {newsletter.name}
    </div>
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
  it("renders a list of newsletter cards and forwards isAuthEnabled", () => {
    render(
      <NewsletterList
        newsletters={mockNewsletters}
        onEditNewsletter={() => {}}
        isAuthEnabled={false}
      />
    )

    expect(screen.getByText("Newsletter One")).toBeInTheDocument()
    expect(screen.getByText("Newsletter Two")).toBeInTheDocument()
    expect(screen.getByTestId("newsletter-card-1")).toHaveAttribute("data-auth-enabled", "false")
    expect(screen.getByTestId("newsletter-card-2")).toHaveAttribute("data-auth-enabled", "false")
  })

  it("renders nothing when the newsletter list is empty", () => {
    const { container } = render(<NewsletterList newsletters={[]} onEditNewsletter={() => {}} />)
    expect(container.firstChild).toBeEmptyDOMElement()
  })
})
