import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "Clairo Terms of Service",
};

export default function TermsPage() {
  return (
    <article className="prose prose-stone max-w-none">
      <h1>Terms of Service</h1>
      <p className="text-muted-foreground">
        Last updated: 1 April 2026
      </p>

      <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
        Draft — final version coming soon. These terms are placeholders and
        will be replaced with the final legal text before public launch.
      </div>

      <h2>1. Acceptance of Terms</h2>
      <p>
        By accessing or using Clairo (&quot;the Service&quot;), operated by KR8IT Pty Ltd
        (&quot;we&quot;, &quot;us&quot;, &quot;our&quot;), you agree to be bound by these Terms of Service.
        If you do not agree, you may not use the Service.
      </p>

      <h2>2. Description of Service</h2>
      <p>
        Clairo is an AI-assisted decision support platform designed for
        registered tax agents and Australian accounting practices. The Service
        assists with BAS preparation, tax planning, and compliance workflows.
      </p>

      <h2>3. AI-Generated Content</h2>
      <p>
        The Service uses artificial intelligence to generate suggestions,
        analyses, and reports. All AI-generated content is decision support
        only and does not constitute tax advice, financial advice, or legal
        advice. You are solely responsible for all professional judgements
        made using the platform.
      </p>

      <h2>4. User Obligations</h2>
      <p>
        You must be a registered tax agent or authorised employee of a
        registered accounting practice to use the professional features of
        this Service. You are responsible for the accuracy and completeness
        of data you provide to the Service.
      </p>

      <h2>5. Data and Privacy</h2>
      <p>
        Your use of the Service is also governed by our{" "}
        <a href="/privacy">Privacy Policy</a>. We process data in accordance
        with the Australian Privacy Act 1988 and store all data in Australian
        data centres.
      </p>

      <h2>6. Limitation of Liability</h2>
      <p>
        To the maximum extent permitted by law, we are not liable for any
        indirect, incidental, special, consequential, or punitive damages
        arising from your use of the Service.
      </p>

      <h2>7. Termination</h2>
      <p>
        We may suspend or terminate your access to the Service at any time
        for violation of these Terms. You may cancel your subscription at
        any time.
      </p>

      <h2>8. Governing Law</h2>
      <p>
        These Terms are governed by the laws of New South Wales, Australia.
        Any disputes will be resolved in the courts of New South Wales.
      </p>

      <h2>9. Contact</h2>
      <p>
        For questions about these Terms, contact us at{" "}
        <a href="mailto:support@clairo.com.au">support@clairo.com.au</a>.
      </p>
    </article>
  );
}
