const API_BASE_URL = '/api';

export interface Sender {
    id: string;
    email: string;
    newsletter_id: string;
}

export interface Newsletter {
  id: string
  name: string
  slug: string | null
  is_active: boolean
  search_folder?: string | null
  move_to_folder?: string | null
  extract_content: boolean
  senders: { id: string; email: string }[]
  entries_count: number
}

export interface NewsletterCreate {
    name: string;
    slug?: string | null;
    sender_emails: string[];
    search_folder?: string | null;
    move_to_folder?: string | null;
    extract_content: boolean;
}

export interface NewsletterUpdate {
    name: string;
    slug?: string | null;
    sender_emails: string[];
    search_folder?: string | null;
    move_to_folder?: string | null;
    extract_content: boolean;
}

export interface Settings {
    id: number;
    imap_server: string;
    imap_username: string;
    search_folder: string;
    move_to_folder?: string | null;
    mark_as_read: boolean;
    email_check_interval: number;
    auto_add_new_senders: boolean;
    locked_fields: string[];
    master_feed_token?: string | null;
}

export interface SettingsCreate {
    imap_server: string;
    imap_username: string;
    imap_password?: string | null;
    search_folder: string;
    move_to_folder?: string | null;
    mark_as_read: boolean;
    email_check_interval: number;
    auto_add_new_senders: boolean;
}


import { toast } from "sonner";

async function fetcher<T>(
    url: string,
    options: RequestInit = {},
    errorMessagePrefix: string,
    returnEmptyArrayOnFailure: boolean = false
): Promise<T> {
    try {
        // Enforce same-origin credentials to automatically send HttpOnly cookies
        options.credentials = 'same-origin';

        const response = await fetch(url, options);
        if (!response.ok) {
            let errorText = `${errorMessagePrefix}: ${response.statusText}`;
            try {
                const errorData = await response.json();
                if (errorData.detail) {
                    errorText = errorData.detail;
                }
            } catch (e) { // eslint-disable-line @typescript-eslint/no-unused-vars
                // ignore error if response is not JSON
            }

            toast.error(errorText);
            if (returnEmptyArrayOnFailure) {
                return [] as T;
            }
            throw new Error(errorText);
        }
        // For login or delete, we might not have a body
        if (response.status === 204) {
            return {} as T;
        }
        return response.json();
    } catch (error) {
        if (error instanceof TypeError) {
            toast.error("Network error: Could not connect to the backend.");
        }
        if (returnEmptyArrayOnFailure) {
            return [] as T;
        }
        throw error;
    }
}

export async function getAuthStatus(): Promise<{ auth_enabled: boolean }> {
    return fetcher<{ auth_enabled: boolean }>(`${API_BASE_URL}/auth/status`, {}, "Failed to fetch auth status");
}

export async function login(username: string, password: string): Promise<void> {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    await fetcher<{ access_token: string }>(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        body: formData,
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
    }, "Login failed");
}

export async function logout(): Promise<void> {
    await fetcher<void>(`${API_BASE_URL}/auth/logout`, {
        method: 'POST',
    }, "Logout failed");
}

export async function verifyAuth(): Promise<boolean> {
    try {
        const response = await fetch(`${API_BASE_URL}/auth/verify`, { credentials: 'same-origin' });
        return response.ok;
    } catch {
        return false;
    }
}


export async function getNewsletters(): Promise<Newsletter[]> {
    return fetcher<Newsletter[]>(`${API_BASE_URL}/newsletters`, {}, "Failed to fetch newsletters");
}

export async function createNewsletter(newsletter: NewsletterCreate): Promise<Newsletter> {
    return fetcher<Newsletter>(`${API_BASE_URL}/newsletters`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(newsletter),
    }, "Failed to create newsletter");
}

export async function updateNewsletter(id: string, newsletter: NewsletterUpdate): Promise<Newsletter> {
    return fetcher<Newsletter>(`${API_BASE_URL}/newsletters/${id}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(newsletter),
    }, "Failed to update newsletter");
}

export async function deleteNewsletter(id: string): Promise<void> {
    await fetcher<void>(`${API_BASE_URL}/newsletters/${id}`, {
        method: 'DELETE',
    }, "Failed to delete newsletter");
}

export async function getSettings(): Promise<Settings> {
    return fetcher<Settings>(`${API_BASE_URL}/imap/settings`, {}, "Failed to fetch settings");
}

export async function updateSettings(settings: SettingsCreate): Promise<Settings> {
    return fetcher<Settings>(`${API_BASE_URL}/imap/settings`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings),
    }, "Failed to update settings");
}

export async function getImapFolders(): Promise<string[]> {
    return fetcher<string[]>(`${API_BASE_URL}/imap/folders`, {}, "Failed to fetch IMAP folders", true);
}

export async function testImapConnection(settings?: SettingsCreate): Promise<{ message: string }> {
    return fetcher<{ message: string }>(`${API_BASE_URL}/imap/test`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: settings ? JSON.stringify(settings) : undefined,
    }, "Failed to test IMAP connection");
}

export async function processEmails(): Promise<{ message: string }> {
    return fetcher<{ message: string }>(`${API_BASE_URL}/imap/process`, {
        method: 'POST',
    }, "Failed to process emails");
}

export function getFeedUrl(newsletter: Newsletter): string {
    return `${API_BASE_URL}/feeds/${newsletter.id}`;
}

export function getMasterFeedUrl(masterFeedToken?: string | null): string {
    if (masterFeedToken) {
        return `${API_BASE_URL}/feeds/all?token=${masterFeedToken}`;
    }
    return `${API_BASE_URL}/feeds/all`;
}
