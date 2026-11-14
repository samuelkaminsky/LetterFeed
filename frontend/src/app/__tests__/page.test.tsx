import React from "react"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import "@testing-library/jest-dom"
import HomePage from "@/app/page"
import * as api from "@/lib/api"
import { useAuth } from "@/hooks/useAuth"

jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  getNewsletters: jest.fn(),
  getSettings: jest.fn(),
  getImapFolders: jest.fn(),
  processEmails: jest.fn(),
}))

jest.mock("@/hooks/useAuth")
jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
}))
jest.mock("sonner", () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}))

const mockedApi = api as jest.Mocked<typeof api>
const mockedUseAuth = useAuth as jest.Mock

const mockSettings: api.Settings = {
  id: 1,
  imap_server: "imap.example.com",
  imap_username: "user@example.com",
  search_folder: "INBOX",
  move_to_folder: null,
  mark_as_read: false,
  email_check_interval: 15,
  auto_add_new_senders: false,
  locked_fields: [],
  master_feed_token: "master-123",
}

const mockNewsletters: api.Newsletter[] = [
  {
    id: "nl-1",
    name: "Weekly Digest",
    slug: "weekly-digest",
    is_active: true,
    extract_content: false,
    senders: [{ id: "s-1", email: "digest@example.com" }],
    entries_count: 3,
  },
]

describe("Dashboard Page", () => {
  beforeEach(() => {
    jest.clearAllMocks()
    mockedUseAuth.mockReturnValue({
      isAuthenticated: true,
      isAuthEnabled: false,
      isLoading: false,
      logout: jest.fn(),
      login: jest.fn(),
    })
    mockedApi.getNewsletters.mockResolvedValue(mockNewsletters)
    mockedApi.getSettings.mockResolvedValue(mockSettings)
    mockedApi.getImapFolders.mockResolvedValue(["INBOX", "Archive"])
    mockedApi.processEmails.mockResolvedValue({ message: "Done" })
  })

  it("renders dashboard without calling getImapFolders on initial load and passes isAuthEnabled to cards", async () => {
    render(<HomePage />)

    await waitFor(() => {
      expect(screen.getByText("Weekly Digest")).toBeInTheDocument()
    })

    expect(mockedApi.getNewsletters).toHaveBeenCalledTimes(1)
    expect(mockedApi.getSettings).toHaveBeenCalledTimes(1)
    expect(mockedApi.getImapFolders).not.toHaveBeenCalled()
    expect(screen.getByText(/\/api\/feeds\/weekly-digest$/)).toBeInTheDocument()
  })

  it("loads IMAP folders lazily when opening a dialog and refreshes newsletters after Process Now", async () => {
    render(<HomePage />)

    await waitFor(() => {
      expect(screen.getByText("Weekly Digest")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole("button", { name: /Add Newsletter/i }))
    await waitFor(() => {
      expect(mockedApi.getImapFolders).toHaveBeenCalledTimes(1)
    })

    fireEvent.click(screen.getByRole("button", { name: /Cancel/i }))
    fireEvent.click(screen.getByRole("button", { name: /Process Now/i }))

    await waitFor(() => {
      expect(mockedApi.processEmails).toHaveBeenCalledTimes(1)
      expect(mockedApi.getNewsletters).toHaveBeenCalledTimes(2)
    })
  })
})
