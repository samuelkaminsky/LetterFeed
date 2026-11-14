import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Loader2, CheckCircle, XCircle } from "lucide-react"
import {
  Settings as AppSettings,
  SettingsCreate,
  updateSettings,
  testImapConnection,
} from "@/lib/api"
import { isToastedError } from "@/lib/utils"
import { toast } from "sonner"

const toFormState = (settings: AppSettings): SettingsCreate => ({
  imap_server: settings.imap_server,
  imap_username: settings.imap_username,
  imap_password: "",
  search_folder: settings.search_folder,
  move_to_folder: settings.move_to_folder ?? null,
  mark_as_read: settings.mark_as_read,
  email_check_interval: settings.email_check_interval,
  auto_add_new_senders: settings.auto_add_new_senders,
  auth_username: settings.auth_username ?? "",
  auth_password: "",
})

const buildSettingsPayload = (currentSettings: SettingsCreate): SettingsCreate => {
  const payload: SettingsCreate = { ...currentSettings }
  if (payload.imap_password === "") {
    delete payload.imap_password
  }
  const trimmedAuthUsername = payload.auth_username?.trim() ?? ""
  if (trimmedAuthUsername === "") {
    payload.auth_username = null
    if (payload.auth_password === "") {
      payload.auth_password = null
    }
  } else {
    payload.auth_username = trimmedAuthUsername
    if (payload.auth_password === "") {
      delete payload.auth_password
    }
  }
  return payload
}

interface SettingsDialogProps {
  settings: AppSettings
  folderOptions: string[]
  isOpen: boolean
  onOpenChange: (isOpen: boolean) => void
  onSuccess: () => void
}

export function SettingsDialog({
  settings,
  folderOptions,
  isOpen,
  onOpenChange,
  onSuccess,
}: SettingsDialogProps) {
  const [currentSettings, setCurrentSettings] = useState<SettingsCreate>(() =>
    toFormState(settings)
  )
  const [isSaving, setIsSaving] = useState(false)
  const [testConnectionStatus, setTestConnectionStatus] = useState<
    "idle" | "loading" | "success" | "error"
  >("idle")
  const [testConnectionMessage, setTestConnectionMessage] = useState("")

  // Re-seed the form when the parent passes fresh settings or re-opens the dialog.
  // Done during render instead of in an effect.
  const [prevProps, setPrevProps] = useState({ settings, isOpen })
  if (prevProps.settings !== settings || prevProps.isOpen !== isOpen) {
    setPrevProps({ settings, isOpen })
    if (isOpen || prevProps.settings !== settings) {
      setCurrentSettings(toFormState(settings))
      setIsSaving(false)
      setTestConnectionStatus("idle")
      setTestConnectionMessage("")
    }
  }

  const handleSettingsChange = <K extends keyof SettingsCreate>(
    key: K,
    value: SettingsCreate[K]
  ) => {
    setCurrentSettings((prev) => ({ ...prev, [key]: value }))
  }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      const payload = buildSettingsPayload(currentSettings)
      await updateSettings(payload)
      toast.success("Settings saved successfully!")
      onOpenChange(false)
      onSuccess()
    } catch (error) {
      console.error("Failed to save settings:", error)
      if (!isToastedError(error)) {
        toast.error("Failed to save settings.")
      }
    } finally {
      setIsSaving(false)
    }
  }

  const handleTestConnection = async () => {
    setTestConnectionStatus("loading")
    try {
      const payload = buildSettingsPayload(currentSettings)
      const result = await testImapConnection(payload, { suppressToast: true })
      setTestConnectionStatus("success")
      setTestConnectionMessage(result.message)
    } catch (error: unknown) {
      setTestConnectionStatus("error")
      if (error instanceof Error) {
        setTestConnectionMessage(error.message || "Connection failed")
      } else {
        setTestConnectionMessage("An unknown error occurred")
      }
    }
  }

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!isSaving) {
          onOpenChange(open)
        }
      }}
    >
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
          <DialogDescription>
            Fields are locked if they are set by environment variables.
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6 py-4">
          {/* IMAP Configuration */}
          <div className="space-y-4">
            <h3 className="text-lg font-medium">
              IMAP Configuration
            </h3>
            <div className="space-y-2">
              <Label htmlFor="imap-server">IMAP Server</Label>
              <Input
                id="imap-server"
                value={currentSettings.imap_server}
                onChange={(e) =>
                  handleSettingsChange("imap_server", e.target.value)
                }
                placeholder="imap.gmail.com"
                disabled={isSaving || settings.locked_fields.includes("imap_server")}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="imap-username">IMAP Username</Label>
              <Input
                id="imap-username"
                value={currentSettings.imap_username}
                onChange={(e) =>
                  handleSettingsChange("imap_username", e.target.value)
                }
                placeholder="your-email@gmail.com"
                disabled={isSaving || settings.locked_fields.includes("imap_username")}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="imap-password">IMAP Password</Label>
              <Input
                id="imap-password"
                type="password"
                value={currentSettings.imap_password ?? ""}
                onChange={(e) =>
                  handleSettingsChange("imap_password", e.target.value)
                }
                placeholder="Your password or app password"
                disabled={isSaving || settings.locked_fields.includes("imap_password")}
              />
            </div>
            <div className="pt-2">
              <Button
                type="button"
                onClick={handleTestConnection}
                disabled={isSaving || testConnectionStatus === "loading"}
                variant="outline"
                size="sm"
              >
                {testConnectionStatus === "loading" && (
                  <Loader2 className="w-4 h-4 mr-2 motion-safe:animate-spin" />
                )}
                Test Connection
              </Button>
              {testConnectionStatus !== "idle" && (
                <div
                  data-testid="connection-status"
                  role="status"
                  aria-live="polite"
                  className={`mt-2 flex items-center text-sm ${
                    testConnectionStatus === "success"
                      ? "text-green-600 dark:text-green-400"
                      : "text-red-600 dark:text-red-400"
                  }`}
                >
                  {testConnectionStatus === "success" && (
                    <CheckCircle className="w-4 h-4 mr-2 shrink-0" />
                  )}
                  {testConnectionStatus === "error" && (
                    <XCircle className="w-4 h-4 mr-2 shrink-0" />
                  )}
                  {testConnectionMessage}
                </div>
              )}
            </div>
          </div>

          {/* Email Processing */}
          <div className="space-y-4">
            <h3 className="text-lg font-medium">
              Email Processing
            </h3>
            <div className="space-y-2">
              <Label htmlFor="search-folder">Folder to Search</Label>
              <Select
                value={currentSettings.search_folder}
                onValueChange={(value) =>
                  handleSettingsChange("search_folder", value)
                }
                disabled={isSaving || settings.locked_fields.includes("search_folder")}
              >
                <SelectTrigger id="search-folder">
                  <SelectValue placeholder="Select folder" />
                </SelectTrigger>
                <SelectContent>
                  {folderOptions.map((folder) => (
                    <SelectItem key={folder} value={folder}>
                      {folder}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="move-folder">Move to Folder</Label>
              <Select
                value={currentSettings.move_to_folder || "None"}
                onValueChange={(value) =>
                  handleSettingsChange(
                    "move_to_folder",
                    value === "None" ? null : value
                  )
                }
                disabled={isSaving || settings.locked_fields.includes("move_to_folder")}
              >
                <SelectTrigger id="move-folder">
                  <SelectValue placeholder="Select folder or leave empty" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="None">Auto-detect Archive (Default)</SelectItem>
                  {folderOptions.map((folder) => (
                    <SelectItem key={folder} value={folder}>
                      {folder}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="check-interval">Check Interval (minutes)</Label>
              <Input
                id="check-interval"
                type="number"
                min="1"
                max="1440"
                value={currentSettings.email_check_interval}
                onChange={(e) =>
                  handleSettingsChange(
                    "email_check_interval",
                    Number.parseInt(e.target.value) || 15
                  )
                }
                placeholder="15"
                disabled={isSaving || settings.locked_fields.includes("email_check_interval")}
              />
            </div>
            <div className="flex items-center space-x-2 pt-2">
              <Checkbox
                id="mark-read"
                checked={currentSettings.mark_as_read}
                onCheckedChange={(checked) =>
                  handleSettingsChange("mark_as_read", !!checked)
                }
                disabled={isSaving || settings.locked_fields.includes("mark_as_read")}
              />
              <Label htmlFor="mark-read" className="text-sm font-normal">
                Mark emails as read
              </Label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="auto-add"
                checked={currentSettings.auto_add_new_senders}
                onCheckedChange={(checked) =>
                  handleSettingsChange("auto_add_new_senders", !!checked)
                }
                disabled={isSaving || settings.locked_fields.includes("auto_add_new_senders")}
              />
              <Label htmlFor="auto-add" className="text-sm font-normal">
                Auto-add new senders
              </Label>
            </div>
          </div>

          {/* Authentication */}
          <div className="space-y-4 md:col-span-2 border-t pt-4">
            <h3 className="text-lg font-medium">Authentication</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="auth-username">Auth Username</Label>
                <Input
                  id="auth-username"
                  value={currentSettings.auth_username ?? ""}
                  onChange={(e) =>
                    handleSettingsChange("auth_username", e.target.value)
                  }
                  placeholder="Leave empty to disable auth"
                  autoComplete="off"
                  disabled={isSaving || settings.locked_fields.includes("auth_username")}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="auth-password">Auth Password</Label>
                <Input
                  id="auth-password"
                  type="password"
                  value={currentSettings.auth_password ?? ""}
                  onChange={(e) =>
                    handleSettingsChange("auth_password", e.target.value)
                  }
                  placeholder={
                    currentSettings.auth_username
                      ? "Leave blank to keep existing"
                      : "Set password"
                  }
                  autoComplete="new-password"
                  disabled={isSaving || settings.locked_fields.includes("auth_password")}
                />
              </div>
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isSaving}
          >
            Cancel
          </Button>
          <Button type="button" onClick={handleSave} disabled={isSaving}>
            {isSaving ? "Saving..." : "Save Settings"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
