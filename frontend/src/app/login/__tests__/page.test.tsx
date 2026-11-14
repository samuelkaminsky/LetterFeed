import React from "react"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import "@testing-library/jest-dom"
import LoginPage from "@/app/login/page"
import { useAuth } from "@/hooks/useAuth"
import { useRouter } from "next/navigation"
import { toast } from "sonner"

// Mock the necessary hooks and modules
jest.mock("@/hooks/useAuth")
jest.mock("sonner", () => ({
  toast: {
    error: jest.fn(),
  },
}))
jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
}))

const mockedUseAuth = useAuth as jest.Mock
const mockedToast = toast as jest.Mocked<typeof toast>
const mockedUseRouter = useRouter as jest.Mock

describe("LoginPage", () => {
  const login = jest.fn()

  beforeEach(() => {
    jest.clearAllMocks()
    mockedUseAuth.mockReturnValue({
      login,
      isAuthenticated: false,
      isLoading: false,
    })
  })

  it("renders the login page with proper autocomplete attributes when not authenticated", () => {
    render(<LoginPage />)
    expect(screen.getByText("LetterFeed")).toBeInTheDocument()
    const usernameInput = screen.getByLabelText("Username")
    const passwordInput = screen.getByLabelText("Password")
    expect(usernameInput).toHaveAttribute("autocomplete", "username")
    expect(passwordInput).toHaveAttribute("autocomplete", "current-password")
    expect(screen.getByRole("button", { name: "Sign In" })).toBeInTheDocument()
  })

  it("shows loading spinner when isLoading is true", () => {
    mockedUseAuth.mockReturnValue({
      login,
      isAuthenticated: false,
      isLoading: true,
    })
    render(<LoginPage />)
    expect(screen.getByTestId("loading-spinner")).toBeInTheDocument()
  })

  it("redirects when authenticated", () => {
    const push = jest.fn()
    mockedUseRouter.mockReturnValue({ push })
    mockedUseAuth.mockReturnValue({
      login,
      isAuthenticated: true,
      isLoading: false,
    })
    render(<LoginPage />)
    expect(push).toHaveBeenCalledWith("/")
  })

  it("allows typing in the username and password fields", () => {
    render(<LoginPage />)
    const usernameInput = screen.getByLabelText("Username")
    const passwordInput = screen.getByLabelText("Password")
    fireEvent.change(usernameInput, { target: { value: "test-user" } })
    fireEvent.change(passwordInput, { target: { value: "test-password" } })
    expect(usernameInput).toHaveValue("test-user")
    expect(passwordInput).toHaveValue("test-password")
  })

  it("calls login on form submission and disables Sign In button while submitting", async () => {
    let resolveLogin!: () => void
    login.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveLogin = resolve
        })
    )

    render(<LoginPage />)
    const usernameInput = screen.getByLabelText("Username")
    const passwordInput = screen.getByLabelText("Password")
    fireEvent.change(usernameInput, { target: { value: "test-user" } })
    fireEvent.change(passwordInput, { target: { value: "test-password" } })
    fireEvent.click(screen.getByRole("button", { name: "Sign In" }))

    expect(screen.getByRole("button", { name: /Signing In/i })).toBeDisabled()

    resolveLogin()
    await waitFor(() => {
      expect(login).toHaveBeenCalledWith("test-user", "test-password")
      expect(screen.getByRole("button", { name: "Sign In" })).toBeEnabled()
    })
  })

  it("does not show an error if login fails, as it is handled by the api layer", async () => {
    login.mockRejectedValue(new Error("Invalid username or password"))
    render(<LoginPage />)
    const usernameInput = screen.getByLabelText("Username")
    const passwordInput = screen.getByLabelText("Password")
    fireEvent.change(usernameInput, { target: { value: "wrong-user" } })
    fireEvent.change(passwordInput, { target: { value: "wrong-password" } })
    fireEvent.click(screen.getByRole("button", { name: "Sign In" }))
    await waitFor(() => {
      expect(login).toHaveBeenCalled()
      expect(mockedToast.error).not.toHaveBeenCalled()
    })
  })

  it("shows an error if username is not provided", async () => {
    render(<LoginPage />)
    const passwordInput = screen.getByLabelText("Password")
    fireEvent.change(passwordInput, { target: { value: "test-password" } })
    fireEvent.click(screen.getByRole("button", { name: "Sign In" }))
    await waitFor(() => {
      expect(mockedToast.error).toHaveBeenCalledWith("Please fill in all fields")
    })
  })

  it("shows an error if password is not provided", async () => {
    render(<LoginPage />)
    const usernameInput = screen.getByLabelText("Username")
    fireEvent.change(usernameInput, { target: { value: "test-user" } })
    fireEvent.click(screen.getByRole("button", { name: "Sign In" }))
    await waitFor(() => {
      expect(mockedToast.error).toHaveBeenCalledWith("Please fill in all fields")
    })
  })
})
