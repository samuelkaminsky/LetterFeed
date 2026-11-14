import React from "react"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import "@testing-library/jest-dom"
import { SettingsDialog } from "../SettingsDialog"
import { Settings } from "@/lib/api"
import * as api from "@/lib/api"
import { toast } from "sonner"

// Mock the API module
jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  updateSettings: jest.fn(),
  testImapConnection: jest.fn(),
}))

// Mock the toast module
jest.mock("sonner", () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}))

const mockedApi = api as jest.Mocked<typeof api>

const mockSettings: Settings = {
  id: 1,
  imap_server: "imap.example.com",
  imap_username: "user@example.com",
  search_folder: "INBOX",
  move_to_folder: "Archive",
  mark_as_read: true,
  email_check_interval: 30,
  auto_add_new_senders: false,
  auth_username: "admin",
  locked_fields: ["imap_server", "auth_password"],
  master_feed_token: "secret-master-token",
}

const mockFolderOptions = ["INBOX", "Sent", "Archive", "Spam"]

describe("SettingsDialog", () => {
  const handleOpenChange = jest.fn()
  const handleSuccess = jest.fn()
  const consoleError = jest.spyOn(console, "error").mockImplementation(() => {})

  beforeEach(() => {
    jest.clearAllMocks()
    consoleError.mockClear()
  })

  afterAll(() => {
    consoleError.mockRestore()
  })

  it("renders settings, respects locked fields, and associates select labels", () => {
    render(
      <SettingsDialog
        settings={mockSettings}
        folderOptions={mockFolderOptions}
        isOpen={true}
        onOpenChange={handleOpenChange}
        onSuccess={handleSuccess}
      />
    )

    expect(screen.getByLabelText(/IMAP Server/i)).toBeDisabled()
    expect(screen.getByLabelText(/IMAP Username/i)).toBeEnabled()
    expect(screen.getByLabelText(/Auth Username/i)).toBeEnabled()
    expect(screen.getByLabelText(/Auth Password/i)).toBeDisabled()
    expect(screen.getByLabelText(/Folder to Search/i)).toHaveAttribute("id", "search-folder")
    expect(screen.getByLabelText(/Move to Folder/i)).toHaveAttribute("id", "move-folder")

    expect(screen.getByLabelText(/IMAP Username/i)).toHaveValue(
      mockSettings.imap_username
    )
    expect(screen.getByLabelText(/Auth Username/i)).toHaveValue("admin")
    expect(screen.getByLabelText(/Mark emails as read/i)).toBeChecked()
  })

  it("uses Auto-detect Archive (Default) label when move_to_folder is unset", () => {
    render(
      <SettingsDialog
        settings={{ ...mockSettings, move_to_folder: null }}
        folderOptions={mockFolderOptions}
        isOpen={true}
        onOpenChange={handleOpenChange}
        onSuccess={handleSuccess}
      />
    )

    expect(screen.getByText("Auto-detect Archive (Default)")).toBeInTheDocument()
  })

  it("excludes response-only fields and strips empty auth_password when auth_username is set", async () => {
    mockedApi.updateSettings.mockResolvedValueOnce(mockSettings)

    render(
      <SettingsDialog
        settings={mockSettings}
        folderOptions={mockFolderOptions}
        isOpen={true}
        onOpenChange={handleOpenChange}
        onSuccess={handleSuccess}
      />
    )

    fireEvent.change(screen.getByLabelText(/IMAP Username/i), {
      target: { value: "new.user@example.com" },
    })

    fireEvent.click(screen.getByRole("button", { name: /Save Settings/i }))

    await waitFor(() => {
      expect(mockedApi.updateSettings).toHaveBeenCalledTimes(1)
    })

    const savedPayload = mockedApi.updateSettings.mock.calls[0][0]
    expect(savedPayload).toEqual(
      expect.objectContaining({
        imap_username: "new.user@example.com",
        auth_username: "admin",
      })
    )
    expect(savedPayload).not.toHaveProperty("id")
    expect(savedPayload).not.toHaveProperty("locked_fields")
    expect(savedPayload).not.toHaveProperty("master_feed_token")
    expect(savedPayload).not.toHaveProperty("imap_password")
    expect(savedPayload).not.toHaveProperty("auth_password")
    expect(toast.success).toHaveBeenCalledWith("Settings saved successfully!")
    expect(handleSuccess).toHaveBeenCalledTimes(1)
    expect(handleOpenChange).toHaveBeenCalledWith(false)
  })

  it("clears auth_username and auth_password when auth_username is cleared", async () => {
    mockedApi.updateSettings.mockResolvedValueOnce({ ...mockSettings, auth_username: null })

    render(
      <SettingsDialog
        settings={mockSettings}
        folderOptions={mockFolderOptions}
        isOpen={true}
        onOpenChange={handleOpenChange}
        onSuccess={handleSuccess}
      />
    )

    fireEvent.change(screen.getByLabelText(/Auth Username/i), {
      target: { value: "" },
    })

    fireEvent.click(screen.getByRole("button", { name: /Save Settings/i }))

    await waitFor(() => {
      expect(mockedApi.updateSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          auth_username: null,
          auth_password: null,
        })
      )
    })
  })

  it("disables save button while saving is in progress", async () => {
    let resolveUpdate!: (value: Settings) => void
    mockedApi.updateSettings.mockImplementation(
      () =>
        new Promise<Settings>((resolve) => {
          resolveUpdate = resolve
        })
    )

    render(
      <SettingsDialog
        settings={mockSettings}
        folderOptions={mockFolderOptions}
        isOpen={true}
        onOpenChange={handleOpenChange}
        onSuccess={handleSuccess}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: /Save Settings/i }))

    expect(screen.getByRole("button", { name: /Saving/i })).toBeDisabled()
    expect(screen.getByRole("button", { name: /Cancel/i })).toBeDisabled()

    resolveUpdate(mockSettings)
    await waitFor(() => {
      expect(handleSuccess).toHaveBeenCalledTimes(1)
    })
  })

  it("shows an error toast if saving settings fails with an untoasted error", async () => {
    mockedApi.updateSettings.mockRejectedValueOnce(new Error("Failed to save"))

    render(
      <SettingsDialog
        settings={mockSettings}
        folderOptions={mockFolderOptions}
        isOpen={true}
        onOpenChange={handleOpenChange}
        onSuccess={handleSuccess}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: /Save Settings/i }))

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Failed to save settings.")
      expect(handleSuccess).not.toHaveBeenCalled()
    })
  })

  it("does not duplicate toast when saving fails with an already-toasted error", async () => {
    const toastedError = Object.assign(new Error("Validation failed"), { toasted: true })
    mockedApi.updateSettings.mockRejectedValueOnce(toastedError)

    render(
      <SettingsDialog
        settings={mockSettings}
        folderOptions={mockFolderOptions}
        isOpen={true}
        onOpenChange={handleOpenChange}
        onSuccess={handleSuccess}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: /Save Settings/i }))

    await waitFor(() => {
      expect(mockedApi.updateSettings).toHaveBeenCalledTimes(1)
    })
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Save Settings/i })).toBeEnabled()
    })
    expect(toast.error).not.toHaveBeenCalled()
  })

  it("handles successful connection test", async () => {
    mockedApi.testImapConnection.mockResolvedValueOnce({
      message: "Connection successful!",
    })

    render(
      <SettingsDialog
        settings={mockSettings}
        folderOptions={mockFolderOptions}
        isOpen={true}
        onOpenChange={handleOpenChange}
        onSuccess={handleSuccess}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: /Test Connection/i }))

    await waitFor(() => {
      expect(mockedApi.testImapConnection).toHaveBeenCalledWith(
        expect.not.objectContaining({ id: expect.anything() }),
        { suppressToast: true }
      )
      expect(screen.getByText("Connection successful!")).toBeInTheDocument()
      expect(screen.getByTestId("connection-status")).toHaveClass(
        "text-green-600"
      )
    })
  })

  it("handles failed connection test", async () => {
    mockedApi.testImapConnection.mockRejectedValueOnce(
      new Error("Authentication failed")
    )

    render(
      <SettingsDialog
        settings={mockSettings}
        folderOptions={mockFolderOptions}
        isOpen={true}
        onOpenChange={handleOpenChange}
        onSuccess={handleSuccess}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: /Test Connection/i }))

    await waitFor(() => {
      expect(screen.getByText("Authentication failed")).toBeInTheDocument()
      expect(screen.getByTestId("connection-status")).toHaveClass("text-red-600")
    })
  })
})
