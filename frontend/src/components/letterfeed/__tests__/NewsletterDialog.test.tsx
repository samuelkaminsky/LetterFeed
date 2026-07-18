import React from "react"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import "@testing-library/jest-dom"
import { NewsletterDialog } from "../NewsletterDialog"
import { Newsletter } from "@/lib/api"
import * as api from "@/lib/api"

// Mock the API module
jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  createNewsletter: jest.fn(),
  updateNewsletter: jest.fn(),
  deleteNewsletter: jest.fn(),
}))

const mockedApi = api as jest.Mocked<typeof api>

const mockNewsletter: Newsletter = {
  id: "1",
  name: "Existing Newsletter",
  slug: "existing-newsletter",
  is_active: true,
  extract_content: false,
  senders: [{ id: "1", email: "current@example.com" }],
  entries_count: 5,
  search_folder: "",
  move_to_folder: "",
}

describe("NewsletterDialog", () => {
  const handleOpenChange = jest.fn()
  const handleSuccess = jest.fn()

  beforeEach(() => {
    jest.clearAllMocks()
    window.confirm = jest.fn(() => true)
  })

  describe("Add Mode", () => {
    it("allows user to fill out the form and submit", async () => {
      mockedApi.createNewsletter.mockResolvedValueOnce({
        id: "2",
        name: "My New Newsletter",
        slug: "my-new-newsletter",
        is_active: true,
        extract_content: false,
        senders: [{ id: "2", email: "test@example.com" }],
        entries_count: 0,
      })

      render(<NewsletterDialog isOpen={true} folderOptions={["INBOX", "Archive"]} onOpenChange={handleOpenChange} onSuccess={handleSuccess} />)

      expect(screen.getByText("Register New Newsletter")).toBeInTheDocument()

      fireEvent.change(screen.getByLabelText(/Newsletter Name/i), { target: { value: "My New Newsletter" } })
      fireEvent.change(screen.getByLabelText(/Custom URL/i), { target: { value: "my-new-newsletter" } })
      fireEvent.change(screen.getByPlaceholderText(/Enter email address/i), { target: { value: "test@example.com" } })

      fireEvent.click(screen.getByRole("button", { name: /Register Newsletter/i }))

      await waitFor(() => {
        expect(mockedApi.createNewsletter).toHaveBeenCalledWith({
          name: "My New Newsletter",
          slug: "my-new-newsletter",
          sender_emails: ["test@example.com"],
          search_folder: null,
          move_to_folder: null,
          extract_content: false,
        })
        expect(handleSuccess).toHaveBeenCalledTimes(1)
        expect(handleOpenChange).toHaveBeenCalledWith(false)
      })
    })

    it("allows adding and removing email fields", () => {
      render(<NewsletterDialog isOpen={true} folderOptions={[]} onOpenChange={() => {}} onSuccess={() => {}} />)
      expect(screen.getAllByPlaceholderText(/Enter email address/i)).toHaveLength(1)
      fireEvent.click(screen.getByRole("button", { name: /Add Another Email/i }))
      expect(screen.getAllByPlaceholderText(/Enter email address/i)).toHaveLength(2)
      fireEvent.click(screen.getAllByRole("button", { name: /Remove/i })[0])
      expect(screen.getAllByPlaceholderText(/Enter email address/i)).toHaveLength(1)
    })
  })

  describe("Edit Mode", () => {
    it("renders with initial newsletter data and allows updates", async () => {
      mockedApi.updateNewsletter.mockResolvedValueOnce({ ...mockNewsletter, name: "Updated Name" })

      render(
        <NewsletterDialog
          newsletter={mockNewsletter}
          isOpen={true}
          folderOptions={["INBOX", "Archive"]}
          onOpenChange={handleOpenChange}
          onSuccess={handleSuccess}
        />
      )

      expect(screen.getByText("Edit Newsletter")).toBeInTheDocument()
      const nameInput = screen.getByLabelText(/Newsletter Name/i)
      const slugInput = screen.getByLabelText(/Custom URL/i)
      expect(nameInput).toHaveValue("Existing Newsletter")
      expect(slugInput).toHaveValue("existing-newsletter")
      expect(screen.getByDisplayValue("current@example.com")).toBeInTheDocument()

      fireEvent.change(nameInput, { target: { value: "Updated Name" } })
      fireEvent.click(screen.getByRole("button", { name: /Save Changes/i }))

      await waitFor(() => {
        expect(mockedApi.updateNewsletter).toHaveBeenCalledWith("1", {
          name: "Updated Name",
          slug: "existing-newsletter",
          sender_emails: ["current@example.com"],
          search_folder: null,
          move_to_folder: null,
          extract_content: false,
        })
        expect(handleSuccess).toHaveBeenCalledTimes(1)
        expect(handleOpenChange).toHaveBeenCalledWith(false)
      })
    })

    it("calls deleteNewsletter when delete button is clicked and confirmed", async () => {
      mockedApi.deleteNewsletter.mockResolvedValueOnce(undefined)

      render(
        <NewsletterDialog
          newsletter={mockNewsletter}
          isOpen={true}
          folderOptions={["INBOX", "Archive"]}
          onOpenChange={handleOpenChange}
          onSuccess={handleSuccess}
        />
      )

      fireEvent.click(screen.getByRole("button", { name: /Delete Newsletter/i }))
      expect(window.confirm).toHaveBeenCalledWith('Are you sure you want to delete the "Existing Newsletter" newsletter?')

      await waitFor(() => {
        expect(mockedApi.deleteNewsletter).toHaveBeenCalledWith("1")
        expect(handleSuccess).toHaveBeenCalledTimes(1)
        expect(handleOpenChange).toHaveBeenCalledWith(false)
      })
    })
  })
})
