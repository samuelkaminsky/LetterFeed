import {
  getNewsletters,
  createNewsletter,
  updateNewsletter,
  deleteNewsletter,
  getSettings,
  updateSettings,
  getImapFolders,
  testImapConnection,
  processEmails,
  getFeedUrl,
  login,
  logout,
  verifyAuth,
  NewsletterCreate,
  NewsletterUpdate,
  SettingsCreate,
  Newsletter,
} from "../api"
import { toast } from "sonner"

// Mock the global fetch function
global.fetch = jest.fn()

// Mock the toast object
jest.mock("sonner", () => ({
  toast: {
    error: jest.fn(),
  },
}))

const mockFetch = <T,>(data: T, ok = true, statusText = "OK") => {
  ;(fetch as jest.Mock).mockResolvedValueOnce({
    ok,
    json: () => Promise.resolve(data),
    statusText,
    status: ok ? 200 : 400,
  })
}

const mockFetchError = (data: any = {}, statusText = "Bad Request", status = 400) => { // eslint-disable-line @typescript-eslint/no-explicit-any
  ;(fetch as jest.Mock).mockResolvedValueOnce({
    ok: false,
    json: () => Promise.resolve(data),
    statusText,
    status,
  })
}

describe("API Functions", () => {
  const API_BASE_URL = '/api'

  beforeEach(() => {
    // Reset the mock before each test
    ;(fetch as jest.Mock).mockClear()
    ;(toast.error as jest.Mock).mockClear()
  })

  describe("login", () => {
    it("should login successfully and trigger fetching", async () => {
      const mockToken = { access_token: "test-token", token_type: "bearer" }
      mockFetch(mockToken)

      await login("user", "pass")

      expect(fetch).toHaveBeenCalledWith(`${API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ username: "user", password: "pass" }),
        credentials: "same-origin",
      })
      expect(toast.error).not.toHaveBeenCalled()
    })

    it("should throw an error if login fails", async () => {
      mockFetchError({ detail: "Incorrect username or password" }, "Unauthorized", 401)

      await expect(login("user", "wrong-pass")).rejects.toThrow("Incorrect username or password")
      expect(toast.error).toHaveBeenCalledWith("Incorrect username or password")
    })
  })

  describe("logout", () => {
    it("should post to /auth/logout successfully", async () => {
      mockFetch({ message: "Successfully logged out" })

      await logout()

      expect(fetch).toHaveBeenCalledWith(`${API_BASE_URL}/auth/logout`, {
        method: "POST",
        credentials: "same-origin",
      })
      expect(toast.error).not.toHaveBeenCalled()
    })
  })

  describe("verifyAuth", () => {
    it("should return true if verification succeeds", async () => {
      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
      })

      const isValid = await verifyAuth()
      expect(isValid).toBe(true)
      expect(fetch).toHaveBeenCalledWith(`${API_BASE_URL}/auth/verify`, {
        credentials: "same-origin",
      })
    })

    it("should return false if verification fails", async () => {
      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
      })

      const isValid = await verifyAuth()
      expect(isValid).toBe(false)
    })
  })

  describe("getNewsletters", () => {
    it("should fetch newsletters successfully with same-origin credentials", async () => {
      const mockNewsletters = [{ id: 1, name: "Newsletter 1" }]
      mockFetch(mockNewsletters)

      const newsletters = await getNewsletters()
      expect(newsletters).toEqual(mockNewsletters)
      expect(fetch).toHaveBeenCalledWith(`${API_BASE_URL}/newsletters`, {
        credentials: "same-origin",
      })
      expect(toast.error).not.toHaveBeenCalled()
    })
  })

  describe("createNewsletter", () => {
    it("should create a newsletter successfully", async () => {
      const newNewsletter: NewsletterCreate = { name: "New Newsletter", sender_emails: ["test@example.com"], extract_content: false }
      const createdNewsletter = {
        id: "3",
        ...newNewsletter,
        is_active: true,
        senders: [{ id: "1", email: "test@example.com", newsletter_id: "3" }],
        entries_count: 0,
      }
      mockFetch(createdNewsletter)

      const result = await createNewsletter(newNewsletter)
      expect(result).toEqual(createdNewsletter)
      expect(fetch).toHaveBeenCalledWith(`${API_BASE_URL}/newsletters`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newNewsletter),
        credentials: "same-origin",
      })
      expect(toast.error).not.toHaveBeenCalled()
    })
  })

  describe("updateNewsletter", () => {
    it("should update a newsletter successfully", async () => {
      const updatedNewsletter: NewsletterUpdate = { name: "Updated Newsletter", sender_emails: ["updated@example.com"], extract_content: true }
      const newsletterId = "1"
      const returnedNewsletter = {
        id: newsletterId,
        ...updatedNewsletter,
        is_active: true,
        senders: [{ id: "1", email: "updated@example.com" }],
        entries_count: 12,
      }
      mockFetch(returnedNewsletter)

      const result = await updateNewsletter(newsletterId, updatedNewsletter)
      expect(result).toEqual(returnedNewsletter)
      expect(fetch).toHaveBeenCalledWith(`${API_BASE_URL}/newsletters/${newsletterId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updatedNewsletter),
        credentials: "same-origin",
      })
      expect(toast.error).not.toHaveBeenCalled()
    })
  })

  describe("deleteNewsletter", () => {
    it("should delete a newsletter successfully", async () => {
      const newsletterId = "1"
      mockFetch({}, true)

      await deleteNewsletter(newsletterId)
      expect(fetch).toHaveBeenCalledWith(`${API_BASE_URL}/newsletters/${newsletterId}`, {
        method: "DELETE",
        credentials: "same-origin",
      })
      expect(toast.error).not.toHaveBeenCalled()
    })
  })

  describe("getSettings", () => {
    it("should fetch settings successfully", async () => {
      const mockSettings = {
        id: 1,
        imap_server: "imap.example.com",
        imap_username: "user@example.com",
        search_folder: "INBOX",
        move_to_folder: null,
        mark_as_read: true,
        email_check_interval: 60,
        auto_add_new_senders: false,
        locked_fields: [],
      }
      mockFetch(mockSettings)

      const settings = await getSettings()
      expect(settings).toEqual(mockSettings)
      expect(fetch).toHaveBeenCalledWith(`${API_BASE_URL}/imap/settings`, {
        credentials: "same-origin",
      })
      expect(toast.error).not.toHaveBeenCalled()
    })
  })

  describe("updateSettings", () => {
    it("should update settings successfully", async () => {
      const newSettings: SettingsCreate = {
        imap_server: "new.imap.com",
        imap_username: "newuser@example.com",
        imap_password: "password",
        search_folder: "Archive",
        move_to_folder: "Processed",
        mark_as_read: false,
        email_check_interval: 120,
        auto_add_new_senders: true,
      }
      const updatedSettings = { id: 1, ...newSettings, locked_fields: [] }
      mockFetch(updatedSettings)

      const result = await updateSettings(newSettings)
      expect(result).toEqual(updatedSettings)
      expect(fetch).toHaveBeenCalledWith(`${API_BASE_URL}/imap/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newSettings),
        credentials: "same-origin",
      })
      expect(toast.error).not.toHaveBeenCalled()
    })
  })

  describe("getImapFolders", () => {
    it("should fetch IMAP folders successfully", async () => {
      const mockFolders = ["INBOX", "Sent", "Archive"]
      mockFetch(mockFolders)

      const folders = await getImapFolders()
      expect(folders).toEqual(mockFolders)
      expect(fetch).toHaveBeenCalledWith(`${API_BASE_URL}/imap/folders`, {
        credentials: "same-origin",
      })
      expect(toast.error).not.toHaveBeenCalled()
    })
  })

  describe("testImapConnection", () => {
    it("should test IMAP connection successfully", async () => {
      const mockResponse = { message: "Connection successful" }
      mockFetch(mockResponse)

      const result = await testImapConnection()
      expect(result).toEqual(mockResponse)
      expect(fetch).toHaveBeenCalledWith(`${API_BASE_URL}/imap/test`, {
        method: "POST",
        credentials: "same-origin",
      })
      expect(toast.error).not.toHaveBeenCalled()
    })
  })

  describe("processEmails", () => {
    it("should process emails successfully", async () => {
      const mockResponse = { message: "Emails processed" }
      mockFetch(mockResponse)

      const result = await processEmails()
      expect(result).toEqual(mockResponse)
      expect(fetch).toHaveBeenCalledWith(`${API_BASE_URL}/imap/process`, {
        method: "POST",
        credentials: "same-origin",
      })
      expect(toast.error).not.toHaveBeenCalled()
    })
  })

  describe("getFeedUrl", () => {
    it("should return the correct feed URL using id even if slug is available", () => {
      const newsletter: Newsletter = {
        id: "123",
        slug: "my-newsletter",
        name: "Test",
        is_active: true,
        senders: [],
        entries_count: 0,
        extract_content: false,
      }
      const expectedUrl = `${API_BASE_URL}/feeds/123`
      const url = getFeedUrl(newsletter)
      expect(url).toBe(expectedUrl)
    })

    it("should return the correct feed URL using id when slug is not available", () => {
      const newsletter: Newsletter = {
        id: "123",
        slug: null,
        name: "Test",
        is_active: true,
        senders: [],
        entries_count: 0,
        extract_content: false,
      }
      const expectedUrl = `${API_BASE_URL}/feeds/123`
      const url = getFeedUrl(newsletter)
      expect(url).toBe(expectedUrl)
    })
  })
})
