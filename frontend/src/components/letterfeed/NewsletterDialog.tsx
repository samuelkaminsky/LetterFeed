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
import { Plus } from "lucide-react"
import { Newsletter, createNewsletter, updateNewsletter, deleteNewsletter } from "@/lib/api"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { isValidEmail } from "@/lib/utils"
import { toast } from "sonner"

interface NewsletterDialogProps {
  newsletter?: Newsletter | null
  isOpen: boolean
  folderOptions: string[]
  isAuthEnabled?: boolean
  onOpenChange: (isOpen: boolean) => void
  onSuccess: () => void
}

const getInitialState = (newsletter: Newsletter | null | undefined) => {
  if (newsletter) {
    return {
      name: newsletter.name,
      slug: newsletter.slug || "",
      is_active: newsletter.is_active,
      emails: newsletter.senders.length > 0 ? newsletter.senders.map((s) => s.email) : [""],
      search_folder: newsletter.search_folder || "",
      move_to_folder: newsletter.move_to_folder || "",
      extract_content: newsletter.extract_content,
    }
  }
  return {
    name: "",
    slug: "",
    is_active: true,
    emails: [""],
    search_folder: "",
    move_to_folder: "",
    extract_content: false,
  }
}

export function NewsletterDialog({
  newsletter,
  isOpen,
  folderOptions,
  isAuthEnabled = true,
  onOpenChange,
  onSuccess,
}: NewsletterDialogProps) {
  const isEditMode = !!newsletter
  const [formData, setFormData] = useState(getInitialState(newsletter))
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false)
  const [touchedEmails, setTouchedEmails] = useState<boolean[]>([])

  // Reset the form whenever the dialog opens or the edited newsletter changes.
  // Done during render (React's "adjusting state on prop change" pattern)
  // rather than in an effect, which would render a stale frame first.
  const [prevProps, setPrevProps] = useState({ isOpen, newsletter })
  if (prevProps.isOpen !== isOpen || prevProps.newsletter !== newsletter) {
    setPrevProps({ isOpen, newsletter })
    if (isOpen) {
      setFormData(getInitialState(newsletter))
      setIsConfirmingDelete(false)
      setIsSubmitting(false)
      setTouchedEmails([])
    }
  }

  const handleEmailChange = (index: number, value: string) => {
    setFormData((prev) => ({
      ...prev,
      emails: prev.emails.map((email, i) => (i === index ? value : email)),
    }))
  }

  const handleEmailBlur = (index: number) => {
    setTouchedEmails((prev) => {
      const next = [...prev]
      next[index] = true
      return next
    })
  }

  const handleAddEmail = () => {
    setFormData((prev) => ({
      ...prev,
      emails: [...prev.emails, ""],
    }))
    setTouchedEmails((prev) => [...prev, false])
  }

  const handleRemoveEmail = (index: number) => {
    setFormData((prev) => ({
      ...prev,
      emails: prev.emails.filter((_, i) => i !== index),
    }))
    setTouchedEmails((prev) => prev.filter((_, i) => i !== index))
  }

  const handleSubmit = async () => {
    if (!formData.name.trim()) {
      toast.error("Please enter a newsletter name.")
      return
    }

    const trimmedEntries = formData.emails.map((email) => email.trim())
    const nonEmptyEmails = trimmedEntries.filter((email) => email.length > 0)

    if (nonEmptyEmails.length === 0) {
      toast.error("Please enter at least one valid email address.")
      return
    }

    const invalidEmails = nonEmptyEmails.filter((email) => !isValidEmail(email))
    if (invalidEmails.length > 0) {
      setTouchedEmails(trimmedEntries.map((email) => email.length > 0 && !isValidEmail(email)))
      toast.error(`Please enter valid email address(es): ${invalidEmails.join(", ")}`)
      return
    }

    const seenEmails = new Set<string>()
    const uniqueEmails: string[] = []
    for (const email of nonEmptyEmails) {
      const normalized = email.toLowerCase()
      if (!seenEmails.has(normalized)) {
        seenEmails.add(normalized)
        uniqueEmails.push(email)
      }
    }

    const payload = {
      name: formData.name.trim(),
      slug: formData.slug.trim() || null,
      is_active: formData.is_active,
      sender_emails: uniqueEmails,
      search_folder: formData.search_folder || null,
      move_to_folder: formData.move_to_folder || null,
      extract_content: formData.extract_content,
    }

    setIsSubmitting(true)
    try {
      if (isEditMode) {
        await updateNewsletter(newsletter.id, payload)
      } else {
        await createNewsletter(payload)
      }
      onOpenChange(false)
      onSuccess()
    } catch (error) {
      console.error(`Failed to ${isEditMode ? "update" : "create"} newsletter:`, error)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDelete = async () => {
    if (!isEditMode) return
    setIsSubmitting(true)
    try {
      await deleteNewsletter(newsletter.id)
      onOpenChange(false)
      onSuccess()
    } catch (error) {
      console.error("Failed to delete newsletter:", error)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!isSubmitting) {
          onOpenChange(open)
        }
      }}
    >
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>{isEditMode ? "Edit" : "Register New"} Newsletter</DialogTitle>
          <DialogDescription>
            {isEditMode ? `Update the details for ${newsletter.name}.` : "Add a new newsletter."}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="name">Newsletter Name</Label>
            <Input
              id="name"
              value={formData.name}
              onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
              placeholder="Enter newsletter name"
              disabled={isSubmitting}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="slug">Custom URL</Label>
            <Input
              id="slug"
              value={formData.slug}
              onChange={(e) => setFormData((prev) => ({ ...prev, slug: e.target.value }))}
              placeholder="my-custom-url"
              aria-describedby={isAuthEnabled ? "slug-auth-note" : undefined}
              disabled={isSubmitting}
            />
            {isAuthEnabled && (
              <p id="slug-auth-note" className="text-xs text-muted-foreground">
                Custom slug URLs are disabled when authentication is enabled; feed links use the newsletter ID.
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="search_folder">Folder to Search</Label>
            <Select
              value={formData.search_folder || "None"}
              onValueChange={(value) =>
                setFormData((prev) => ({ ...prev, search_folder: value === "None" ? "" : value }))
              }
              disabled={isSubmitting}
            >
              <SelectTrigger id="search_folder">
                <SelectValue placeholder="Select folder or leave empty" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="None">Default (use global setting)</SelectItem>
                {folderOptions.map((folder) => (
                  <SelectItem key={folder} value={folder}>
                    {folder}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="move_to_folder">Move To Folder</Label>
            <Select
              value={formData.move_to_folder || "None"}
              onValueChange={(value) =>
                setFormData((prev) => ({ ...prev, move_to_folder: value === "None" ? "" : value }))
              }
              disabled={isSubmitting}
            >
              <SelectTrigger id="move_to_folder">
                <SelectValue placeholder="Select folder or leave empty" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="None">Default (use global setting)</SelectItem>
                {folderOptions.map((folder) => (
                  <SelectItem key={folder} value={folder}>
                    {folder}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Email Addresses</Label>
            {formData.emails.map((email, index) => {
              const trimmed = email.trim()
              const showEmailError =
                Boolean(touchedEmails[index]) && trimmed.length > 0 && !isValidEmail(trimmed)
              const errorId = `newsletter-email-error-${index}`
              return (
                <div key={index} className="space-y-1">
                  <div className="flex gap-2">
                    <Input
                      value={email}
                      onChange={(e) => handleEmailChange(index, e.target.value)}
                      onBlur={() => handleEmailBlur(index)}
                      placeholder="Enter email address"
                      type="email"
                      aria-invalid={showEmailError}
                      aria-describedby={showEmailError ? errorId : undefined}
                      disabled={isSubmitting}
                    />
                    {formData.emails.length > 1 && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => handleRemoveEmail(index)}
                        disabled={isSubmitting}
                      >
                        Remove
                      </Button>
                    )}
                  </div>
                  {showEmailError && (
                    <p id={errorId} className="text-xs text-destructive">
                      Enter a valid email address (for example, newsletter@example.com).
                    </p>
                  )}
                </div>
              )
            })}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleAddEmail}
              className="w-full bg-transparent"
              disabled={isSubmitting}
            >
              <Plus className="w-4 h-4 mr-2" />
              Add Another Email
            </Button>
          </div>

          <div className="flex items-center space-x-2">
            <Checkbox
              id="is-active"
              checked={formData.is_active}
              onCheckedChange={(checked) =>
                setFormData((prev) => ({ ...prev, is_active: !!checked }))
              }
              disabled={isSubmitting}
            />
            <Label htmlFor="is-active">Active (check for new emails)</Label>
          </div>

          <div className="flex items-center space-x-2">
            <Checkbox
              id="extract-content"
              checked={formData.extract_content}
              onCheckedChange={(checked) =>
                setFormData((prev) => ({ ...prev, extract_content: !!checked }))
              }
              disabled={isSubmitting}
            />
            <Label htmlFor="extract-content">Extract main content from emails</Label>
          </div>
        </div>
        <DialogFooter className={isEditMode ? "sm:justify-between" : ""}>
          {isEditMode && !isConfirmingDelete && (
            <Button
              type="button"
              variant="destructive"
              onClick={() => setIsConfirmingDelete(true)}
              disabled={isSubmitting}
            >
              Delete Newsletter
            </Button>
          )}
          {isEditMode && isConfirmingDelete ? (
            <div className="flex w-full flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <span className="text-sm text-destructive font-medium" role="status">
                Delete &ldquo;{newsletter.name}&rdquo;?
              </span>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsConfirmingDelete(false)}
                  disabled={isSubmitting}
                  autoFocus
                >
                  Cancel Confirm
                </Button>
                <Button
                  type="button"
                  variant="destructive"
                  onClick={handleDelete}
                  disabled={isSubmitting}
                >
                  {isSubmitting ? "Deleting..." : "Confirm Delete"}
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button type="button" onClick={handleSubmit} disabled={isSubmitting}>
                {isSubmitting
                  ? isEditMode
                    ? "Saving..."
                    : "Registering..."
                  : isEditMode
                    ? "Save Changes"
                    : "Register Newsletter"}
              </Button>
            </div>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
