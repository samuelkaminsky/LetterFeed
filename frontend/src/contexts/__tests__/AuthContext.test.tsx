import React from "react"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import "@testing-library/jest-dom"
import { AuthProvider, AuthContext } from "@/contexts/AuthContext"
import * as api from "@/lib/api"
import { useRouter } from "next/navigation"

jest.mock("@/lib/api")
jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
}))

const mockedApi = api as jest.Mocked<typeof api>
const mockedUseRouter = useRouter as jest.Mock

describe("AuthContext", () => {
  const push = jest.fn()
  const consoleError = jest.spyOn(console, "error").mockImplementation(() => {})

  beforeEach(() => {
    jest.clearAllMocks()
    mockedUseRouter.mockReturnValue({ push })
    consoleError.mockClear()
  })

  afterAll(() => {
    consoleError.mockRestore()
  })

  it("authenticates and sets auth enabled to false if auth is not enabled on server", async () => {
    mockedApi.getAuthStatus.mockResolvedValue({ auth_enabled: false })
    render(
      <AuthProvider>
        <AuthContext.Consumer>
          {(value) => (
            <div>
              <span>
                Is Authenticated: {value?.isAuthenticated.toString()}
              </span>
              <span>
                Is Auth Enabled: {value?.isAuthEnabled.toString()}
              </span>
            </div>
          )}
        </AuthContext.Consumer>
      </AuthProvider>
    )
    await waitFor(() => {
      expect(screen.getByText("Is Authenticated: true")).toBeInTheDocument()
      expect(screen.getByText("Is Auth Enabled: false")).toBeInTheDocument()
    })
  })

  it("authenticates if auth is enabled and token verification succeeds", async () => {
    mockedApi.getAuthStatus.mockResolvedValue({ auth_enabled: true })
    mockedApi.verifyAuth.mockResolvedValue(true)
    render(
      <AuthProvider>
        <AuthContext.Consumer>
          {(value) => (
            <div>
              <span>
                Is Authenticated: {value?.isAuthenticated.toString()}
              </span>
              <span>
                Is Auth Enabled: {value?.isAuthEnabled.toString()}
              </span>
            </div>
          )}
        </AuthContext.Consumer>
      </AuthProvider>
    )
    await waitFor(() => {
      expect(screen.getByText("Is Authenticated: true")).toBeInTheDocument()
      expect(screen.getByText("Is Auth Enabled: true")).toBeInTheDocument()
      expect(mockedApi.verifyAuth).toHaveBeenCalledTimes(1)
    })
  })

  it("does not authenticate if auth is enabled and token verification fails", async () => {
    mockedApi.getAuthStatus.mockResolvedValue({ auth_enabled: true })
    mockedApi.verifyAuth.mockResolvedValue(false)
    render(
      <AuthProvider>
        <AuthContext.Consumer>
          {(value) => (
            <span>
              Is Authenticated: {value?.isAuthenticated.toString()}
            </span>
          )}
        </AuthContext.Consumer>
      </AuthProvider>
    )
    await waitFor(() => {
      expect(screen.getByText("Is Authenticated: false")).toBeInTheDocument()
    })
  })

  it("uses single-request fast path without calling verifyAuth when status includes authenticated boolean", async () => {
    mockedApi.getAuthStatus.mockResolvedValue({ auth_enabled: true, authenticated: true })
    render(
      <AuthProvider>
        <AuthContext.Consumer>
          {(value) => (
            <div>
              <span>
                Is Authenticated: {value?.isAuthenticated.toString()}
              </span>
              <span>
                Is Auth Enabled: {value?.isAuthEnabled.toString()}
              </span>
            </div>
          )}
        </AuthContext.Consumer>
      </AuthProvider>
    )
    await waitFor(() => {
      expect(screen.getByText("Is Authenticated: true")).toBeInTheDocument()
      expect(screen.getByText("Is Auth Enabled: true")).toBeInTheDocument()
    })
    expect(mockedApi.verifyAuth).not.toHaveBeenCalled()
  })

  it("sets unauthenticated on fast path when status.authenticated is false without calling verifyAuth", async () => {
    mockedApi.getAuthStatus.mockResolvedValue({ auth_enabled: true, authenticated: false })
    render(
      <AuthProvider>
        <AuthContext.Consumer>
          {(value) => (
            <span>
              Is Authenticated: {value?.isAuthenticated.toString()}
            </span>
          )}
        </AuthContext.Consumer>
      </AuthProvider>
    )
    await waitFor(() => {
      expect(screen.getByText("Is Authenticated: false")).toBeInTheDocument()
    })
    expect(mockedApi.verifyAuth).not.toHaveBeenCalled()
  })

  it("login works correctly", async () => {
    mockedApi.getAuthStatus.mockResolvedValue({ auth_enabled: true })
    mockedApi.verifyAuth.mockResolvedValue(false)
    mockedApi.login.mockResolvedValue()
    render(
      <AuthProvider>
        <AuthContext.Consumer>
          {(value) => (
            <>
              <span>
                Is Authenticated: {value?.isAuthenticated.toString()}
              </span>
              <button onClick={() => value?.login("testuser", "password")}>Login</button>
            </>
          )}
        </AuthContext.Consumer>
      </AuthProvider>
    )
    await waitFor(() => {
      expect(screen.getByText("Is Authenticated: false")).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText("Login"))
    await waitFor(() => {
      expect(mockedApi.login).toHaveBeenCalledWith("testuser", "password")
      expect(screen.getByText("Is Authenticated: true")).toBeInTheDocument()
      expect(push).toHaveBeenCalledWith("/")
    })
  })

  it("logout awaits apiLogout before clearing auth state and redirecting", async () => {
    mockedApi.getAuthStatus.mockResolvedValue({ auth_enabled: true, authenticated: true })
    let resolveLogout!: () => void
    mockedApi.logout.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveLogout = resolve
        })
    )
    render(
      <AuthProvider>
        <AuthContext.Consumer>
          {(value) => (
            <>
              <span>
                Is Authenticated: {value?.isAuthenticated.toString()}
              </span>
              <button onClick={() => value?.logout()}>Logout</button>
            </>
          )}
        </AuthContext.Consumer>
      </AuthProvider>
    )
    await waitFor(() => {
      expect(screen.getByText("Is Authenticated: true")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText("Logout"))
    await waitFor(() => {
      expect(mockedApi.logout).toHaveBeenCalledTimes(1)
    })
    expect(push).not.toHaveBeenCalled()

    resolveLogout()
    await waitFor(() => {
      expect(screen.getByText("Is Authenticated: false")).toBeInTheDocument()
      expect(push).toHaveBeenCalledWith("/login")
    })
  })

  it("logout still clears auth state and redirects if apiLogout fails", async () => {
    mockedApi.getAuthStatus.mockResolvedValue({ auth_enabled: true, authenticated: true })
    mockedApi.logout.mockRejectedValue(new Error("Network error"))
    render(
      <AuthProvider>
        <AuthContext.Consumer>
          {(value) => (
            <>
              <span>
                Is Authenticated: {value?.isAuthenticated.toString()}
              </span>
              <button onClick={() => value?.logout()}>Logout</button>
            </>
          )}
        </AuthContext.Consumer>
      </AuthProvider>
    )
    await waitFor(() => {
      expect(screen.getByText("Is Authenticated: true")).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText("Logout"))
    await waitFor(() => {
      expect(screen.getByText("Is Authenticated: false")).toBeInTheDocument()
      expect(push).toHaveBeenCalledWith("/login")
    })
  })
})
