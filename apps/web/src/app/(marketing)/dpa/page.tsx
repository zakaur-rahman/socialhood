import Link from "next/link";

import { LegalFacts, LegalPage, type LegalSection } from "@/components/marketing/legal/LegalPage";
import { SubprocessorTable } from "@/components/marketing/legal/SubprocessorTable";
import { LEGAL, isSet, operatorName } from "@/lib/legal";
import { SITE_NAME } from "@/lib/marketing/site";
import { pageMetadata } from "@/lib/marketing/seo";

export const metadata = pageMetadata({
  title: "Data Processing Agreement",
  description: `How ${SITE_NAME} processes its customers' data for them: GDPR Article 28 terms, the EU Standard Contractual Clauses, the UK Addendum and our security measures.`,
  path: "/dpa",
});

const N = SITE_NAME;
const email = LEGAL.contactEmail;
const mail = <a href={`mailto:${email}`}>{email}</a>;

// C-156: a plain-language controller-to-processor agreement modelled on GDPR Art. 28(3), with the
// 2021 SCCs (Commission Implementing Decision (EU) 2021/914, Modules 2 and 3) and the ICO's UK
// Addendum incorporated by reference. Annex 2 is true to the code and infra (infra/vm, C-145;
// security/crypto.py; lib/security/headers.ts; jobs/tasks/purge.py; infra/vm/backup.sh); Annex 3 is
// the shared list in lib/subprocessors.ts. NOT reviewed by a lawyer (no lawyer budget, C-156).
function sections(): LegalSection[] {
  const operator = operatorName(LEGAL);
  const where = isSet(LEGAL.publicLocation) ? LEGAL.publicLocation.trim() : "India";
  return [
    {
      id: "about",
      title: "About this agreement",
      body: (
        <>
          <p>
            This Data Processing Agreement (&quot;DPA&quot;) is between {operator}, a sole proprietorship based in {where}{" "}
            (&quot;we&quot;, &quot;us&quot;), and the business or creator that uses {N} (&quot;you&quot;). It forms part of
            our <Link href="/terms">Terms of Service</Link>: when you accept the Terms, you accept this DPA too, and you
            don&apos;t need to sign anything else. If you&apos;d like a signed copy, email {mail}.
          </p>
          <p>
            It applies when we process personal data on your behalf to provide {N} (&quot;customer personal data&quot;).
            Where this DPA and the Terms disagree about personal data, this DPA wins. Words such as &quot;controller&quot;,
            &quot;processor&quot;, &quot;personal data breach&quot; and &quot;data subject&quot; mean what they mean in the
            EU General Data Protection Regulation (GDPR).
          </p>
          <p>
            The data protection laws it covers include the GDPR, the UK GDPR, India&apos;s Digital Personal Data Protection
            Act 2023 and the California Consumer Privacy Act, wherever they apply to the processing.
          </p>
        </>
      ),
    },
    {
      id: "roles",
      title: "Who does what",
      body: (
        <ul>
          <li>
            <strong>You are the controller</strong> of customer personal data: the messages, comments, contacts, orders and
            profiles of the people who reach you on Instagram, Facebook, WhatsApp and website chat, including a
            creator&apos;s followers. If you use {N} for your own clients, you are their processor and we are your
            subprocessor.
          </li>
          <li>
            <strong>We are your processor.</strong> We process customer personal data only to provide {N} to you, as
            described in <a href="#annex-1">Annex 1</a>.
          </li>
          <li>
            <strong>We are a separate controller</strong> for the data about your own account: your team&apos;s sign-in
            details, billing, support and security records. Our <Link href="/privacy">Privacy Policy</Link> covers that
            data, not this DPA.
          </li>
          <li>
            You are responsible for having a lawful basis for the data you bring to {N}, for the notices and consents your
            customers need, and for the instructions you give us.
          </li>
        </ul>
      ),
    },
    {
      id: "our-duties",
      title: "What we promise",
      body: (
        <ol>
          <li>
            <strong>Instructions.</strong> We process customer personal data only on your documented instructions: the
            Terms, this DPA, and what you set up and do in {N} (for example the accounts you connect, your AI mode and your
            automations). The law may require something else; if so, we&apos;ll tell you first unless the law forbids it.
            If we think an instruction breaks data protection law, we&apos;ll tell you.
          </li>
          <li>
            <strong>Confidentiality.</strong> Everyone we allow to process customer personal data is bound to keep it
            confidential. Today that is only the people who run {N}, and they look at a workspace&apos;s data only to help
            you, to investigate a problem or abuse, or when the law requires it.
          </li>
          <li>
            <strong>Security.</strong> We keep the technical and organisational measures in{" "}
            <a href="#annex-2">Annex 2</a>, as GDPR Article 32 requires, and may improve them over time without lowering
            the overall level of protection.
          </li>
          <li>
            <strong>Subprocessors.</strong> See <a href="#subprocessors">Subprocessors</a> below.
          </li>
          <li>
            <strong>Helping with people&apos;s requests.</strong> {N} lets you find, correct, export (contacts as a CSV
            file, and your data through the API) and delete customer personal data. Where that isn&apos;t enough, we help
            you answer requests from people exercising their rights. If someone asks us directly about data you control,
            we pass the request to you and don&apos;t answer it ourselves unless you ask us to.
          </li>
          <li>
            <strong>Helping with your obligations.</strong> Taking into account what we process and the information we
            have, we help you with security, breach notifications, data protection impact assessments and consultations
            with a supervisory authority (GDPR Articles 32 to 36).
          </li>
          <li>
            <strong>Breaches.</strong> If we become aware of a personal data breach affecting customer personal data, we
            tell you without undue delay, and within 72 hours of becoming aware of it. We tell you what happened, the data
            and people likely affected, the likely consequences, and what we&apos;re doing about it, and we send more
            details as we learn them. Telling you is not an admission of fault.
          </li>
          <li>
            <strong>Deletion at the end.</strong> When you delete a connected account&apos;s data or your workspace, or when
            the Terms end, we delete customer personal data within 24 hours, as our{" "}
            <Link href="/privacy#retention">Privacy Policy</Link> describes, unless the law requires us to keep it.
            Before that, you can export your contacts and read your data through the API; if you need a copy in another
            common format, ask us before you delete. Copies in our database backups are deleted when those backups expire,
            within 30 days.
          </li>
          <li>
            <strong>Information and audits.</strong> We make available the information you reasonably need to show that we
            meet this DPA, starting with written answers to your questions and our documentation. If that isn&apos;t enough,
            or a supervisory authority asks, you may audit us, or have an independent auditor bound by confidentiality do
            so, on reasonable request: with 30 days&apos; notice, at most once a year unless there has been a breach or an
            authority requires it, during working hours, without access to other customers&apos; data, and at your cost.
          </li>
        </ol>
      ),
    },
    {
      id: "subprocessors",
      title: "Subprocessors",
      body: (
        <>
          <p>
            You give us general authorisation to use subprocessors. The current ones are on our{" "}
            <Link href="/subprocessors">subprocessors page</Link> (<a href="#annex-3">Annex 3</a>).
          </p>
          <ul>
            <li>
              We bind each subprocessor by written contract to data protection duties that are at least as protective as
              this DPA, and we remain responsible to you for its work.
            </li>
            <li>
              Before a new subprocessor starts processing customer personal data, we update the page and email the owner
              of each workspace at least 30 days ahead. If we must replace one urgently, for security or to keep {N}{" "}
              running, we tell you as soon as we can.
            </li>
            <li>
              You can object on reasonable data protection grounds by emailing {mail} within that notice period. We&apos;ll
              work with you in good faith on a solution. If we can&apos;t find one, you can stop using {N} and delete your
              workspace, and we refund any fees you paid in advance for the time left.
            </li>
          </ul>
        </>
      ),
    },
    {
      id: "transfers",
      title: "International transfers",
      body: (
        <>
          <p>
            We are based in India, our servers are in Singapore, and some subprocessors work in other countries, including
            the United States (see <a href="#annex-3">Annex 3</a>).
          </p>
          <ul>
            <li>
              <strong>From the EEA.</strong> Where you transfer customer personal data subject to the GDPR to us, in a
              country without an EU adequacy decision, the Standard Contractual Clauses adopted by the European Commission
              in Implementing Decision (EU) 2021/914 (&quot;SCCs&quot;) apply and are incorporated into this DPA by
              reference: Module 2 where you are a controller, and Module 3 where you are a processor. You are the data
              exporter and we are the data importer. For the SCCs: the optional docking clause (Clause 7) applies; Clause
              9(a) Option 2 (general authorisation) applies, with the notice period above; the optional wording in Clause
              11 does not apply; Clause 13 follows the data exporter&apos;s establishment; the governing law (Clause 17)
              and the courts (Clause 18) are those of the EU member state where you are established, or Ireland if you
              aren&apos;t established in the EU. Annexes I and II of the SCCs are completed by Annexes 1 and 2 below, and
              Annex III by Annex 3.
            </li>
            <li>
              <strong>From the UK.</strong> For transfers subject to the UK GDPR, the International Data Transfer Addendum
              to the EU Commission Standard Contractual Clauses, issued by the UK Information Commissioner (version B1.0),
              applies and is incorporated by reference. Its Tables 1 to 3 are completed with the details of this DPA and the
              SCCs above; for Table 4, neither party may end the Addendum when it changes.
            </li>
            <li>
              <strong>Onward transfers.</strong> When a subprocessor processes the data in another country, we rely on the
              SCCs (and the UK Addendum) in its data processing terms, or on another transfer mechanism the law allows.
            </li>
            <li>If the SCCs and the rest of this DPA or the Terms disagree, the SCCs win.</li>
          </ul>
        </>
      ),
    },
    {
      id: "other-laws",
      title: "India and California",
      body: (
        <ul>
          <li>
            <strong>India (DPDP Act).</strong> You are the Data Fiduciary and we are your Data Processor. We process
            customer personal data only under this DPA and the Terms, keep reasonable security safeguards, and erase the
            data as described above.
          </li>
          <li>
            <strong>California (CCPA).</strong> We act as your service provider. We don&apos;t sell or share customer
            personal data, and we don&apos;t keep, use or disclose it for any purpose other than providing {N} to you, or
            outside our direct business relationship with you, or combine it with personal data from other sources except
            as the CCPA allows. We tell you if we can no longer meet these duties.
          </li>
        </ul>
      ),
    },
    {
      id: "term",
      title: "How long it lasts, and liability",
      body: (
        <>
          <p>
            This DPA lasts as long as we process customer personal data for you, and ends once that data has been deleted.
            Duties that by their nature should continue, such as confidentiality, continue.
          </p>
          <p>
            Each party&apos;s liability under this DPA is subject to the limits in the Terms, to the extent the law allows.
            Nothing in this DPA limits a data subject&apos;s rights under the SCCs.
          </p>
          <p>
            We may update this DPA, for example when the law or our subprocessors change. We&apos;ll tell you before a
            change that reduces your protection takes effect, and we won&apos;t make one unless the law requires it.
          </p>
        </>
      ),
    },
    {
      id: "annex-1",
      title: "Annex 1: Details of processing",
      body: (
        <>
          <ul>
            <li>
              <strong>Parties.</strong> Data exporter: you, the business or creator using {N}, at the contact details in
              your account. Data importer: {operator}, {where}, {email}. Contact for data protection: {mail}.
            </li>
            <li>
              <strong>Subject matter and duration.</strong> Providing {N} to you, for as long as you use it and until the
              data is deleted as described in this DPA.
            </li>
            <li>
              <strong>Nature of the processing.</strong> Receiving messages, comments and profiles from Meta&apos;s
              platforms and website chat; storing and organising them; showing them to your team; analysing them with AI,
              drafting replies and, if you turn on Auto mode, sending replies; sending your replies, automated messages and
              posts; running your automations; sending data to the tools you connect; and deleting it.
            </li>
            <li>
              <strong>Purpose.</strong> Only to provide {N} to you under the Terms, and to keep it secure.
            </li>
            <li>
              <strong>Data subjects.</strong> People who message or comment on your connected accounts or your website
              chat, including your customers, leads and followers; contacts you add or import; and people named in your
              content.
            </li>
            <li>
              <strong>Categories of personal data.</strong> Names, usernames, profile pictures and platform IDs; phone
              numbers and email addresses; message and comment content, including photos, videos, voice notes and files;
              whether someone follows your Instagram account; the ad or link a chat started from; orders, delivery addresses
              and payment status; notes, tags and custom fields; marketing consent records; the AI&apos;s analysis of
              messages; and, for website chat visitors, IP addresses and a random visitor ID.
            </li>
            <li>
              <strong>Sensitive data.</strong> {N} isn&apos;t designed for special categories of data, and you shouldn&apos;t
              ask people to send it. Messages may still contain it if people choose to send it.
            </li>
            <li>
              <strong>Frequency.</strong> Continuous, while you use {N}.
            </li>
            <li>
              <strong>Retention.</strong> As in the retention table of our{" "}
              <Link href="/privacy#retention">Privacy Policy</Link>, and as you choose in {N}.
            </li>
            <li>
              <strong>Competent supervisory authority.</strong> The one competent for you as data exporter under Clause 13
              of the SCCs.
            </li>
          </ul>
        </>
      ),
    },
    {
      id: "annex-2",
      title: "Annex 2: Security measures",
      body: (
        <ul>
          <li>
            <strong>Encryption in transit.</strong> HTTPS everywhere, with HTTP Strict Transport Security; Meta&apos;s
            platforms are reached only through their official APIs over HTTPS.
          </li>
          <li>
            <strong>Encryption at rest.</strong> Access tokens and payment keys are encrypted in our database with keys
            that can be rotated. Google Cloud encrypts its disks at rest.
          </li>
          <li>
            <strong>Separation.</strong> Every workspace&apos;s data is kept separate, and every request is checked against
            the workspace and the member&apos;s role (owner, admin or agent).
          </li>
          <li>
            <strong>Network.</strong> The database and cache run on a private network and are never exposed to the
            internet. Only our web proxy accepts outside connections.
          </li>
          <li>
            <strong>Access.</strong> Only the people who run {N} can reach production, with SSH keys. Secrets are kept in
            files only the server can read and are never committed to our code. Our application services run as
            unprivileged users.
          </li>
          <li>
            <strong>Sign-in.</strong> Sign-in is handled by Clerk, with bot protection. We never ask for or receive
            Instagram or Facebook passwords.
          </li>
          <li>
            <strong>Incoming data.</strong> Webhooks from Meta are checked against Meta&apos;s signature, and requests are
            rate-limited to limit abuse.
          </li>
          <li>
            <strong>Error reports.</strong> Message text, email addresses, tokens, cookies and request bodies are removed
            before error reports leave our servers.
          </li>
          <li>
            <strong>Backups and recovery.</strong> The database is backed up every night, each backup is checked, and
            backups are deleted after at most 30 days. We have tested restoring them.
          </li>
          <li>
            <strong>Deletion.</strong> Deleting a workspace or an account&apos;s data stops processing at once and removes
            the data within 24 hours; expired data is removed by daily jobs.
          </li>
          <li>
            <strong>Changes and testing.</strong> Every code change runs automated tests before release, and we check our
            dependencies for known vulnerabilities and our code for leaked secrets.
          </li>
          <li>
            <strong>Reporting problems.</strong> Anyone can report a security problem as our{" "}
            <Link href="/security">security page</Link> describes.
          </li>
        </ul>
      ),
    },
    {
      id: "annex-3",
      title: "Annex 3: Subprocessors",
      body: (
        <>
          <p>
            The subprocessors you authorise are those on our <Link href="/subprocessors">subprocessors page</Link>, which
            we keep up to date. Today they are:
          </p>
          <SubprocessorTable />
        </>
      ),
    },
    {
      id: "contact",
      title: "Contact",
      body: (
        <>
          <p>Questions about this DPA, requests for a signed copy, and objections: {mail}.</p>
          <LegalFacts />
        </>
      ),
    },
  ];
}

export default function DpaPage() {
  return (
    <LegalPage
      document="dpa"
      sections={sections()}
      summary={
        <>
          <p>
            When you use {N}, you decide what happens to your customers&apos; and followers&apos; data, and we process it
            for you. This agreement sets out how: only on your instructions, kept secure and confidential, with subprocessors
            you are told about, breaches reported within 72 hours, and deletion when you ask.
          </p>
          <p>
            It is part of our <Link href="/terms">Terms of Service</Link>, so it applies as soon as you accept them. It
            includes the EU Standard Contractual Clauses and the UK Addendum for transfers out of Europe.
          </p>
        </>
      }
    />
  );
}
