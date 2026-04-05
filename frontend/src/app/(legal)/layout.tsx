import Link from "next/link";
import Image from "next/image";

export default function LegalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center gap-2">
            <Image
              src="/logos/clairo-logo-new.png"
              alt="Clairo"
              width={28}
              height={28}
            />
            <span className="text-lg font-semibold">Clairo</span>
          </Link>
          <Link
            href="/"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            Back to home
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-6 py-12">{children}</main>
      <footer className="border-t">
        <div className="mx-auto flex max-w-3xl items-center justify-center gap-6 px-6 py-6 text-sm text-muted-foreground">
          <Link href="/terms" className="hover:text-foreground">
            Terms of Service
          </Link>
          <Link href="/privacy" className="hover:text-foreground">
            Privacy Policy
          </Link>
          <Link href="/acceptable-use" className="hover:text-foreground">
            Acceptable Use
          </Link>
        </div>
      </footer>
    </div>
  );
}
