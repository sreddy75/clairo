"use client";

import { useAuth } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { TOS_VERSION } from "@/lib/constants";
import Link from "next/link";

export default function AcceptTermsPage() {
  const { getToken } = useAuth();
  const router = useRouter();
  const [accepted, setAccepted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAccept() {
    setSubmitting(true);
    setError(null);

    try {
      const token = await getToken();
      const res = await fetch("/api/v1/auth/accept-terms", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ version: TOS_VERSION }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Failed to accept terms");
      }

      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-lg">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">Terms of Service</CardTitle>
          <CardDescription>
            Please review and accept our terms before continuing
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="rounded-md border p-4 text-sm text-muted-foreground space-y-3">
            <p>
              By using Clairo, you agree to our{" "}
              <Link
                href="/terms"
                target="_blank"
                className="underline text-foreground hover:text-primary"
              >
                Terms of Service
              </Link>{" "}
              and{" "}
              <Link
                href="/privacy"
                target="_blank"
                className="underline text-foreground hover:text-primary"
              >
                Privacy Policy
              </Link>
              .
            </p>
            <p>
              Clairo is AI-assisted decision support for registered tax agents.
              It does not constitute tax advice. You are responsible for all
              professional judgements made using this platform.
            </p>
          </div>

          <div className="flex items-start space-x-3">
            <Checkbox
              id="accept-tos"
              checked={accepted}
              onCheckedChange={(checked) => setAccepted(checked === true)}
            />
            <label
              htmlFor="accept-tos"
              className="text-sm leading-relaxed cursor-pointer"
            >
              I have read and accept the{" "}
              <Link href="/terms" target="_blank" className="underline">
                Terms of Service
              </Link>{" "}
              and{" "}
              <Link href="/privacy" target="_blank" className="underline">
                Privacy Policy
              </Link>
            </label>
          </div>

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          <Button
            onClick={handleAccept}
            disabled={!accepted || submitting}
            className="w-full"
            size="lg"
          >
            {submitting ? "Accepting..." : "Continue"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
