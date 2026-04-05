import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Acceptable Use Policy",
  description: "Clairo Acceptable Use Policy",
};

export default function AcceptableUsePage() {
  return (
    <article className="prose prose-stone max-w-none">
      <h1>Acceptable Use Policy</h1>
      <p className="text-muted-foreground">
        Last updated: 1 April 2026
      </p>

      <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
        Draft — final version coming soon. This policy is a placeholder and
        will be replaced with the final legal text before public launch.
      </div>

      <h2>1. Intended Use</h2>
      <p>
        Clairo is designed for use by registered tax agents and Australian
        accounting practices for BAS preparation, tax planning, and compliance
        workflows. Use of the Service outside this scope is not supported.
      </p>

      <h2>2. Prohibited Activities</h2>
      <p>You agree not to:</p>
      <ul>
        <li>
          Use the Service to provide tax advice to the public without
          appropriate professional registration
        </li>
        <li>
          Upload real client data containing Tax File Numbers (TFNs) or
          bank account details outside of the designated secure fields
        </li>
        <li>
          Attempt to reverse-engineer, extract, or replicate the AI models
          or algorithms used by the Service
        </li>
        <li>
          Use the Service to generate content that is misleading, fraudulent,
          or intended to deceive the ATO or other regulatory bodies
        </li>
        <li>
          Share your account credentials or allow unauthorised access to
          the Service
        </li>
        <li>
          Use automated tools to scrape, crawl, or extract data from the
          Service
        </li>
      </ul>

      <h2>3. AI Output Usage</h2>
      <p>
        AI-generated content from Clairo is decision support only. You must
        not represent AI outputs as professional tax advice without
        independent verification and the application of professional
        judgement by a registered tax agent.
      </p>

      <h2>4. Data Handling</h2>
      <p>
        You are responsible for ensuring that any client data uploaded to
        the Service complies with the Australian Privacy Act 1988 and that
        you have appropriate consent from your clients to process their data
        through the platform.
      </p>

      <h2>5. Enforcement</h2>
      <p>
        Violation of this Acceptable Use Policy may result in suspension or
        termination of your account. We reserve the right to take action
        against any use that we determine, in our sole discretion, violates
        this policy.
      </p>

      <h2>6. Contact</h2>
      <p>
        To report a violation or ask questions about this policy, contact us
        at <a href="mailto:support@clairo.com.au">support@clairo.com.au</a>.
      </p>
    </article>
  );
}
