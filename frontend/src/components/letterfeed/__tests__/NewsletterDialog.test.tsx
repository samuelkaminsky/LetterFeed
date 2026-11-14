import React from "react"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import "@testing-library/jest-dom"
import { NewsletterDialog } from "../NewsletterDialog"
import { Newsletter } from "@/lib/api"
import * as api from "@/lib/api"
import { toast } from "sonner"

// Mock the API module
jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  createNewsletter: jest.fn(),
  updateNewsletter: jest.fn(),
  deleteNewsletter: jest.fn(),
}))

jest.mock("sonner", () => ({
  toast: {
    error: jest.fn(),
    success: jest.fn(),
  },
}))

const mockedApi = api as jest.Mocked<typeof api>
const mockedToast = toast as jest.Mocked<typeof toast>

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
      expect(screen.getByLabelText(/Active \(check for new emails\)/i)).toBeChecked()
      expect(screen.getByLabelText(/Folder to Search/i)).toHaveAttribute("id", "search_folder")
      expect(screen.getByLabelText(/Move To Folder/i)).toHaveAttribute("id", "move_to_folder")

      fireEvent.change(screen.getByLabelText(/Newsletter Name/i), { target: { value: "My New Newsletter" } })
      fireEvent.change(screen.getByLabelText(/Custom URL/i), { target: { value: "my-new-newsletter" } })
      fireEvent.change(screen.getByPlaceholderText(/Enter email address/i), { target: { value: "test@example.com" } })

      fireEvent.click(screen.getByRole("button", { name: /Register Newsletter/i }))

      await waitFor(() => {
        expect(mockedApi.createNewsletter).toHaveBeenCalledWith({
          name: "My New Newsletter",
          slug: "my-new-newsletter",
          is_active: true,
          sender_emails: ["test@example.com"],
          search_folder: null,
          move_to_folder: null,
          extract_content: false,
        })
        expect(handleSuccess).toHaveBeenCalledTimes(1)
        expect(handleOpenChange).toHaveBeenCalledWith(false)
      })
    })

    it("rejects submission if any non-empty email is invalid instead of dropping it", async () => {
      render(<NewsletterDialog isOpen={true} folderOptions={[]} onOpenChange={handleOpenChange} onSuccess={handleSuccess} />)

      fireEvent.change(screen.getByLabelText(/Newsletter Name/i), { target: { value: "Valid Name" } })
      fireEvent.click(screen.getByRole("button", { name: /Add Another Email/i }))

      const emailInputs = screen.getAllByPlaceholderText(/Enter email address/i)
      fireEvent.change(emailInputs[0], { target: { value: "valid@example.com" } })
      fireEvent.change(emailInputs[1], { target: { value: "not-an-email" } })

      fireEvent.click(screen.getByRole("button", { name: /Register Newsletter/i }))

      await waitFor(() => {
        expect(mockedToast.error).toHaveBeenCalledWith(expect.stringContaining("not-an-email"))
      })
      expect(mockedApi.createNewsletter).not.toHaveBeenCalled()
    })

    it("trims and deduplicates valid email addresses", async () => {
      mockedApi.createNewsletter.mockResolvedValueOnce({
        id: "3",
        name: "Deduped",
        slug: null,
        is_active: false,
        extract_content: false,
        senders: [{ id: "1", email: "news@example.com" }],
        entries_count: 0,
      })

      render(<NewsletterDialog isOpen={true} folderOptions={[]} onOpenChange={handleOpenChange} onSuccess={handleSuccess} />)

      fireEvent.change(screen.getByLabelText(/Newsletter Name/i), { target: { value: "Deduped" } })
      fireEvent.click(screen.getByRole("button", { name: /Add Another Email/i }))

      const emailInputs = screen.getAllByPlaceholderText(/Enter email address/i)
      fireEvent.change(emailInputs[0], { target: { value: "  news@example.com  " } })
      fireEvent.change(emailInputs[1], { target: { value: "NEWS@example.com" } })
      fireEvent.click(screen.getByLabelText(/Active \(check for new emails\)/i))

      fireEvent.click(screen.getByRole("button", { name: /Register Newsletter/i }))

      await waitFor(() => {
        expect(mockedApi.createNewsletter).toHaveBeenCalledWith(
          expect.objectContaining({
            is_active: false,
            sender_emails: ["news@example.com"],
          })
        )
      })
    })

    it("shows helper note under Custom URL when auth is enabled and hides it when disabled", () => {
      const { rerender } = render(
        <NewsletterDialog isOpen={true} folderOptions={[]} isAuthEnabled={true} onOpenChange={() => {}} onSuccess={() => {}} />
      )
      expect(screen.getByText(/Custom slug URLs are disabled when authentication is enabled/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/Custom URL/i)).toBeEnabled()

      rerender(
        <NewsletterDialog isOpen={true} folderOptions={[]} isAuthEnabled={false} onOpenChange={() => {}} onSuccess={() => {}} />
      )
      expect(screen.queryByText(/Custom slug URLs are disabled when authentication is enabled/i)).not.toBeInTheDocument()
      expect(screen.getByLabelText(/Custom URL/i)).toBeEnabled()
    })

    it("allows adding and removing email fields", () => {
      render(<NewsletterDialog isOpen={true} folderOptions={[]} onOpenChange={() => {}} onSuccess={() => {}} />)
      expect(screen.getAllByPlaceholderText(/Enter email address/i)).toHaveLength(1)
      fireEvent.click(screen.getByRole("button", { name: /Add Another Email/i }))
      expect(screen.getAllByPlaceholderText(/Enter email address/i)).toHaveLength(2)
      fireEvent.click(screen.getAllByRole("button", { name: /Remove/i })[0])
      expect(screen.getAllByPlaceholderText(/Enter email address/i)).toHaveLength(1)
    })

    it("disables action buttons while submitting", async () => {
      let resolveCreate!: (value: Newsletter) => void
      mockedApi.createNewsletter.mockImplementation(
        () =>
          new Promise<Newsletter>((resolve) => {
            resolveCreate = resolve
          })
      )

      render(<NewsletterDialog isOpen={true} folderOptions={[]} onOpenChange={handleOpenChange} onSuccess={handleSuccess} />)
      fireEvent.change(screen.getByLabelText(/Newsletter Name/i), { target: { value: "Slow Submit" } })
      fireEvent.change(screen.getByPlaceholderText(/Enter email address/i), { target: { value: "slow@example.com" } })

      fireEvent.click(screen.getByRole("button", { name: /Register Newsletter/i }))

      const savingButton = screen.getByRole("button", { name: /Registering/i })
      expect(savingButton).toBeDisabled()
      expect(screen.getByRole("button", { name: /Cancel/i })).toBeDisabled()

      resolveCreate({
        id: "9",
        name: "Slow Submit",
        slug: null,
        is_active: true,
        extract_content: false,
        senders: [{ id: "1", email: "slow@example.com" }],
        entries_count: 0,
      })

      await waitFor(() => {
        expect(handleSuccess).toHaveBeenCalledTimes(1)
      })
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
      expect(screen.getByLabelText(/Active \(check for new emails\)/i)).toBeChecked()

      fireEvent.change(nameInput, { target: { value: "Updated Name" } })
      fireEvent.click(screen.getByRole("button", { name: /Save Changes/i }))

      await waitFor(() => {
        expect(mockedApi.updateNewsletter).toHaveBeenCalledWith("1", {
          name: "Updated Name",
          slug: "existing-newsletter",
          is_active: true,
          sender_emails: ["current@example.com"],
          search_folder: null,
          move_to_folder: null,
          extract_content: false,
        })
        expect(handleSuccess).toHaveBeenCalledTimes(1)
        expect(handleOpenChange).toHaveBeenCalledWith(false)
      })
    })

    it("reflects inactive state in edit mode", () => {
      render(
        <NewsletterDialog
          newsletter={{ ...mockNewsletter, is_active: false }}
          isOpen={true}
          folderOptions={[]}
          onOpenChange={handleOpenChange}
          onSuccess={handleSuccess}
        />
      )
      expect(screen.getByLabelText(/Active \(check for new emails\)/i)).not.toBeChecked()
    })

    it("requires inline confirmation before calling deleteNewsletter", async () => {
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
      expect(mockedApi.deleteNewsletter).not.toHaveBeenCalled()
      expect(screen.getByText(/Delete “Existing Newsletter”\?/)).toBeInTheDocument()
      expect(screen.getByRole("button", { name: /Cancel Confirm/i })).toHaveFocus()

      fireEvent.click(screen.getByRole("button", { name: /Cancel Confirm/i }))
      expect(mockedApi.deleteNewsletter).not.toHaveBeenCalled()
      expect(screen.getByRole("button", { name: /Delete Newsletter/i })).toBeInTheDocument()

      fireEvent.click(screen.getByRole("button", { name: /Delete Newsletter/i }))
      fireEvent.click(screen.getByRole("button", { name: /Confirm Delete/i }))

      await waitFor(() => {
        expect(mockedApi.deleteNewsletter).toHaveBeenCalledWith("1")
        expect(handleSuccess).toHaveBeenCalledTimes(1)
        expect(handleOpenChange).toHaveBeenCalledWith(false)
      })
    })
  })
})
