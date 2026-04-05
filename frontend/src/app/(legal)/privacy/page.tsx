import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "Clairo Privacy Policy",
};

export default function PrivacyPage() {
  return (
    <article className="prose prose-stone max-w-none">
      <h1>Privacy Policy</h1>
      <p className="text-muted-foreground">
        Last updated: 1 April 2026
      </p>

      <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
        Draft — final version coming soon. This policy is a placeholder and
        will be replaced with the final legal text before public launch.
      </div>

      <h2>1. Information We Collect</h2>
      <p>
        We collect information you provide directly: account details (name,
        email, practice name), financial data you import from Xero or upload,
        and interactions with the AI features of the Service.
      </p>

      <h2>2. How We Use Your Information</h2>
      <p>
        We use your information to provide the Service, including BAS
        preparation assistance, tax planning support, and AI-powered insights.
        We do not sell your data to third parties.
      </p>

      <h2>3. Data Storage and Security</h2>
      <p>
        All data is stored in Australian data centres (Sydney region). Data is
        encrypted at rest and in transit using industry-standard encryption
        (TLS 1.3, AES-256).
      </p>

      <h2>4. Third-Party Services</h2>
      <p>
        We use the following third-party services to operate the platform:
        Clerk (authentication), Xero (accounting data integration), Anthropic
        (AI processing), and Resend (transactional email). Each service
        processes data in accordance with their own privacy policies.
      </p>

      <h2>5. Data Retention</h2>
      <p>
        We retain your data for as long as your account is active. Financial
        data and audit logs are retained for a minimum of 7 years in
        accordance with ATO record-keeping requirements. You may request
        deletion of your account and personal data at any time, subject to
        legal retention obligations.
      </p>

      <h2>6. Your Rights</h2>
      <p>
        Under the Australian Privacy Act 1988, you have the right to access,
        correct, and request deletion of your personal information. Contact us
        at <a href="mailto:privacy@clairo.com.au">privacy@clairo.com.au</a> to
        exercise these rights.
      </p>

      <h2>7. Cookies and Analytics</h2>
      <p>
        We use cookies and analytics tools to improve the Service. You can
        manage your cookie preferences via the cookie consent banner. See our
        cookie consent settings for details on what is tracked.
      </p>

      <h2>8. Changes to This Policy</h2>
      <p>
        We may update this Privacy Policy from time to time. We will notify
        you of material changes via email or in-app notification.
      </p>

      <h2>9. Contact</h2>
      <p>
        For privacy-related inquiries, contact us at{" "}
        <a href="mailto:privacy@clairo.com.au">privacy@clairo.com.au</a>.
      </p>
    </article>
  );
}
