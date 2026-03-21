"use client";

import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Eye,
  Loader2,
  Mail,
  Send,
} from "lucide-react";
import { useState, useCallback } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

interface ClassificationRequestButtonProps {
  connectionId: string;
  sessionId: string;
  clientEmail: string | null;
  unresolvedCount: number;
  getToken: () => Promise<string | null>;
  existingRequest?: {
    id: string;
    status: string;
    classified_count: number;
    transaction_count: number;
  } | null;
}

const STATUS_CONFIG: Record<
  string,
  { label: string; icon: React.ReactNode; variant: "default" | "secondary" | "outline" }
> = {
  sent: { label: "Sent to client", icon: <Mail className="h-3 w-3" />, variant: "secondary" },
  viewed: { label: "Client viewing", icon: <Eye className="h-3 w-3" />, variant: "secondary" },
  in_progress: { label: "Client classifying", icon: <Loader2 className="h-3 w-3 animate-spin" />, variant: "secondary" },
  submitted: { label: "Ready for review", icon: <CheckCircle2 className="h-3 w-3" />, variant: "default" },
  reviewing: { label: "Under review", icon: <Eye className="h-3 w-3" />, variant: "outline" },
  completed: { label: "Completed", icon: <CheckCircle2 className="h-3 w-3" />, variant: "default" },
};

export function ClassificationRequestButton({
  connectionId,
  sessionId,
  clientEmail,
  unresolvedCount,
  getToken,
  existingRequest,
}: ClassificationRequestButtonProps) {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [emailOverride, setEmailOverride] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  const handleSend = useCallback(async () => {
    setSending(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not authenticated");
      const response = await fetch(
        `/api/v1/clients/${connectionId}/bas/sessions/${sessionId}/classification/request`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            message: message || null,
            email_override: emailOverride || null,
          }),
        }
      );
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to send request");
      }
      setSent(true);
      setTimeout(() => {
        setOpen(false);
        setSent(false);
      }, 2000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to send request");
    } finally {
      setSending(false);
    }
  }, [connectionId, sessionId, message, emailOverride]);

  // Show status badge if request already exists
  if (existingRequest && existingRequest.status !== "cancelled" && existingRequest.status !== "expired") {
    const config = STATUS_CONFIG[existingRequest.status] ?? STATUS_CONFIG.sent!;
    return (
      <div className="flex items-center gap-2">
        <Badge variant={config.variant} className="gap-1">
          {config.icon}
          {config.label}
        </Badge>
        {existingRequest.status === "submitted" && (
          <span className="text-xs text-muted-foreground tabular-nums">
            {existingRequest.classified_count}/{existingRequest.transaction_count}
          </span>
        )}
      </div>
    );
  }

  // No unresolved transactions — nothing to classify
  if (unresolvedCount === 0) {
    return null;
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <Send className="h-4 w-4" />
          Request Client Input
          <Badge variant="secondary" className="ml-1 tabular-nums">
            {unresolvedCount}
          </Badge>
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Request Client Input</DialogTitle>
          <DialogDescription>
            Send your client a link to classify {unresolvedCount} unresolved
            transaction{unresolvedCount !== 1 ? "s" : ""}. They&apos;ll see plain-English categories — no tax codes.
          </DialogDescription>
        </DialogHeader>

        {sent ? (
          <div className="flex flex-col items-center gap-3 py-6">
            <CheckCircle2 className="h-10 w-10 text-emerald-500" />
            <p className="text-sm font-medium">Request sent!</p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Email */}
            <div className="space-y-2">
              <Label htmlFor="client-email">Client email</Label>
              {clientEmail ? (
                <div className="flex items-center gap-2">
                  <Mail className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm">{clientEmail}</span>
                </div>
              ) : (
                <>
                  <Input
                    id="client-email"
                    type="email"
                    placeholder="client@business.com.au"
                    value={emailOverride}
                    onChange={(e) => setEmailOverride(e.target.value)}
                  />
                  <p className="text-xs text-amber-600">
                    <AlertCircle className="inline h-3 w-3 mr-1" />
                    No email on file for this client
                  </p>
                </>
              )}
            </div>

            {/* Message */}
            <div className="space-y-2">
              <Label htmlFor="message">Message (optional)</Label>
              <Textarea
                id="message"
                placeholder="Please classify these before Friday..."
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                maxLength={500}
                className="min-h-[80px]"
              />
            </div>

            {/* Info */}
            <div className="rounded-md bg-stone-50 p-3 text-xs text-muted-foreground space-y-1">
              <p>
                <Clock className="inline h-3 w-3 mr-1" />
                Link expires in 7 days
              </p>
              <p>Receipts will be automatically requested for transactions over $82.50</p>
            </div>

            {error && (
              <p className="text-sm text-red-600">
                <AlertCircle className="inline h-4 w-4 mr-1" />
                {error}
              </p>
            )}
          </div>
        )}

        {!sent && (
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSend}
              disabled={sending || (!clientEmail && !emailOverride)}
            >
              {sending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Sending...
                </>
              ) : (
                <>
                  <Send className="h-4 w-4 mr-2" />
                  Send to Client
                </>
              )}
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
