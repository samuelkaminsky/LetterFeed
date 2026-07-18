import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { Header } from "../Header"
import { Toaster } from "@/components/ui/sonner"
import { toast } from "sonner"
import * as api from "@/lib/api"
import { useAuth } from "@/hooks/useAuth"

jest.mock("@/lib/api")
jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
}))
jest.mock("@/hooks/useAuth")

const mockedApi = api as jest.Mocked<typeof api>
const mockedUseAuth = useAuth as jest.Mock

// Mock the toast functions
jest.mock("sonner", () => {
  const original = jest.requireActual("sonner")
  return {
    ...original,
    toast: {
      success: jest.fn(),
      error: jest.fn(),
    },
  }
})

describe("Header", () => {
  const onOpenAddNewsletter = jest.fn()
  const onOpenSettings = jest.fn()
  const logout = jest.fn()
  const consoleError = jest.spyOn(console, "error").mockImplementation(() => {})

  beforeEach(() => {
    jest.clearAllMocks()
    consoleError.mockClear()
    mockedUseAuth.mockReturnValue({
      logout,
      isAuthEnabled: true, // Default to auth being enabled for most tests
    })
  })

  afterAll(() => {
    consoleError.mockRestore()
  })

  it("renders the header with title and buttons including logout", () => {
    render(
      <Header
        onOpenAddNewsletter={onOpenAddNewsletter}
        onOpenSettings={onOpenSettings}
      />
    )
    expect(screen.getByText("LetterFeed")).toBeInTheDocument()
    expect(screen.getByText("Add Newsletter")).toBeInTheDocument()
    expect(screen.getByText("Settings")).toBeInTheDocument()
    expect(screen.getByText("Process Now")).toBeInTheDocument()
    expect(screen.getByText("Logout")).toBeInTheDocument()
  })

  it("does not render the logout button if auth is disabled", () => {
    mockedUseAuth.mockReturnValue({
      logout,
      isAuthEnabled: false,
    })
    render(
      <Header
        onOpenAddNewsletter={onOpenAddNewsletter}
        onOpenSettings={onOpenSettings}
      />
    )
    expect(screen.queryByText("Logout")).not.toBeInTheDocument()
  })

  it('calls onOpenAddNewsletter when "Add Newsletter" button is clicked', () => {
    render(
      <Header
        onOpenAddNewsletter={onOpenAddNewsletter}
        onOpenSettings={onOpenSettings}
      />
    )
    fireEvent.click(screen.getByText("Add Newsletter"))
    expect(onOpenAddNewsletter).toHaveBeenCalledTimes(1)
  })

  it('calls onOpenSettings when "Settings" button is clicked', () => {
    render(
      <Header
        onOpenAddNewsletter={onOpenAddNewsletter}
        onOpenSettings={onOpenSettings}
      />
    )
    fireEvent.click(screen.getByText("Settings"))
    expect(onOpenSettings).toHaveBeenCalledTimes(1)
  })

  it('calls the process emails API when "Process Now" button is clicked and shows success toast', async () => {
    mockedApi.processEmails.mockResolvedValue({ message: "Success" })

    render(
      <>
        <Header
          onOpenAddNewsletter={onOpenAddNewsletter}
          onOpenSettings={onOpenSettings}
        />
        <Toaster />
      </>
    )

    fireEvent.click(screen.getByText("Process Now"))

    await waitFor(() => {
      expect(api.processEmails).toHaveBeenCalledTimes(1)
    })

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith(
        "Email processing finished successfully!"
      )
    })
  })

  it("shows an error toast if the process emails API call fails", async () => {
    mockedApi.processEmails.mockRejectedValue(new Error("Failed to process"))

    render(
      <>
        <Header
          onOpenAddNewsletter={onOpenAddNewsletter}
          onOpenSettings={onOpenSettings}
        />
        <Toaster />
      </>
    )

    fireEvent.click(screen.getByText("Process Now"))

    await waitFor(() => {
      expect(api.processEmails).toHaveBeenCalledTimes(1)
    })

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Failed to process")
    })
  })
})
