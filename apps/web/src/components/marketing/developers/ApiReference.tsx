import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { curlExample, type Reference, type ReferenceField, type ReferenceOperation } from "@/lib/marketing/public-api";
import { cn } from "@/lib/utils";
import { EYEBROW, MARKETING_HEADING, READING, SECTION_TITLE } from "@/styles/tokens";

import { Container, SECTION_EYEBROW } from "../primitives";

const slug = (tag: string) => tag.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-");

const METHOD_TONE = { GET: "success", POST: "brand", PUT: "warning", PATCH: "warning", DELETE: "danger" } as const;

function Fields({ title, fields }: { title: string; fields: ReferenceField[] }) {
  if (fields.length === 0) return null;
  return (
    <div className="space-y-2">
      <h4 className={EYEBROW}>{title}</h4>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left">
              <th scope="col" className="py-2 pr-4 font-semibold">
                Name
              </th>
              <th scope="col" className="py-2 pr-4 font-semibold">
                Type
              </th>
              <th scope="col" className="py-2 font-semibold">
                Notes
              </th>
            </tr>
          </thead>
          <tbody>
            {fields.map((field) => (
              <tr key={field.name} className="border-b border-line-subtle align-top">
                <td className="py-2 pr-4 font-mono text-xs">
                  {field.name}
                  {field.required ? <span className="ml-1 text-fg-secondary">required</span> : null}
                </td>
                <td className="py-2 pr-4 text-fg-secondary">{field.type}</td>
                <td className="py-2 text-fg-secondary">{field.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Operation({ operation, baseUrl }: { operation: ReferenceOperation; baseUrl: string }) {
  const titleId = `${operation.id}-title`;
  return (
    <Card asChild padding="roomy">
      <article id={operation.id} aria-labelledby={titleId} className="scroll-mt-24 space-y-4" data-operation={operation.id}>
        <header className="space-y-2">
          <h3 id={titleId} className="flex flex-wrap items-center gap-2 text-base font-semibold">
            <Badge tone={METHOD_TONE[operation.method as keyof typeof METHOD_TONE] ?? "neutral"} shape="tag">
              {operation.method}
            </Badge>
            <code className="font-mono text-sm break-all">{operation.path}</code>
          </h3>
          <p className="text-sm font-medium capitalize">{operation.summary}</p>
          {operation.scope ? (
            <p className="text-xs text-fg-secondary">
              Needs the <code className="font-mono">{operation.scope}</code> scope.
            </p>
          ) : null}
        </header>
        {operation.paragraphs
          .filter((p) => !p.startsWith("Requires the `"))
          .map((paragraph) => (
            <p key={paragraph} className="text-sm text-fg-secondary">
              {paragraph.replaceAll("`", "")}
            </p>
          ))}
        <Fields title="Parameters" fields={operation.parameters} />
        {operation.body ? <Fields title="Request body (JSON)" fields={operation.body} /> : null}
        {operation.responses.length > 0 ? (
          <div className="space-y-2">
            <h4 className={EYEBROW}>Responses</h4>
            <ul className="space-y-1 text-sm text-fg-secondary">
              {operation.responses.map((response) => (
                <li key={response.status}>
                  <code className="font-mono text-xs text-fg">{response.status}</code> {response.description}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <pre className="overflow-x-auto rounded-md bg-field p-3 font-mono text-xs">
          <code>{curlExample(operation, baseUrl)}</code>
        </pre>
      </article>
    </Card>
  );
}

/**
 * The public API's reference (GR-25): how to authenticate, the scopes, then every operation by
 * area, from the API's own OpenAPI document. Server-rendered and static; a contents list sits
 * beside it on wide screens and above it on a phone.
 */
export function ApiReference({ reference, baseUrl }: { reference: Reference; baseUrl: string }) {
  return (
    <main id="main" tabIndex={-1} className="flex-1 outline-none">
      <Container className="py-12 sm:py-16">
        <header className="max-w-3xl">
          <p className={SECTION_EYEBROW}>Developers</p>
          <h1 className={cn(MARKETING_HEADING, "mt-3")}>{reference.title}</h1>
          <p className="mt-2 text-sm text-fg-secondary">Version {reference.version}</p>
          <div className={cn(READING, "mt-6 space-y-3 text-fg-secondary")}>
            {reference.paragraphs.map((paragraph) => (
              <p key={paragraph}>{paragraph.replaceAll("`", "")}</p>
            ))}
          </div>
        </header>

        <div className="mt-10 grid gap-10 lg:grid-cols-[14rem_1fr]">
          <nav aria-label="Contents" className="lg:sticky lg:top-24 lg:self-start">
            <h2 className={EYEBROW}>Contents</h2>
            <ul className="mt-3 grid gap-0.5 text-sm">
              <li>
                <a className="flex min-h-8 items-center rounded-md px-2 text-fg-secondary hover:bg-hover hover:text-fg pointer-coarse:min-h-10" href="#authentication">
                  Authentication
                </a>
              </li>
              {reference.groups.map((group) => (
                <li key={group.tag}>
                  <a
                    className="flex min-h-8 items-center rounded-md px-2 text-fg-secondary hover:bg-hover hover:text-fg pointer-coarse:min-h-10"
                    href={`#${slug(group.tag)}`}
                  >
                    {group.tag}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          <div className="min-w-0 max-w-3xl space-y-12">
            <section id="authentication" aria-labelledby="authentication-title" className="scroll-mt-24 space-y-4">
              <h2 id="authentication-title" className={SECTION_TITLE}>
                Authentication
              </h2>
              <p className="text-sm text-fg-secondary">
                Make a key in Settings, Integrations, API keys. Send it on every request. A key belongs to one
                workspace and carries scopes; a request that needs a scope the key lacks is refused with 403.
              </p>
              <pre className="overflow-x-auto rounded-md bg-field p-3 font-mono text-xs">
                <code>{`curl "${baseUrl.replace(/\/+$/, "")}/public/v1/contacts" \\\n  -H "Authorization: Bearer $SOCIALHOOD_API_KEY"`}</code>
              </pre>
              {reference.scopes.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <caption className="sr-only">Scopes</caption>
                    <thead>
                      <tr className="border-b border-line text-left">
                        <th scope="col" className="py-2 pr-4 font-semibold">
                          Scope
                        </th>
                        <th scope="col" className="py-2 font-semibold">
                          Allows
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {reference.scopes.map((scope) => (
                        <tr key={scope.scope} className="border-b border-line-subtle align-top">
                          <td className="py-2 pr-4 font-mono text-xs">{scope.scope}</td>
                          <td className="py-2 text-fg-secondary">{scope.description}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </section>

            {reference.groups.map((group) => (
              <section key={group.tag} id={slug(group.tag)} aria-labelledby={`${slug(group.tag)}-title`} className="scroll-mt-24 space-y-4">
                <h2 id={`${slug(group.tag)}-title`} className={SECTION_TITLE}>
                  {group.tag}
                </h2>
                {group.operations.map((operation) => (
                  <Operation key={operation.id} operation={operation} baseUrl={baseUrl} />
                ))}
              </section>
            ))}
          </div>
        </div>
      </Container>
    </main>
  );
}

/** Shown when the API can't be reached: no stale or invented reference. */
export function ApiReferenceUnavailable() {
  return (
    <main id="main" tabIndex={-1} className="flex-1 outline-none">
      <Container className="py-12 sm:py-16">
        <p className={SECTION_EYEBROW}>Developers</p>
        <h1 className={cn(MARKETING_HEADING, "mt-3")}>Amplychat public API</h1>
        <Card padding="roomy" className="mt-6 max-w-xl" role="status">
          <p className="text-sm">The API reference isn&rsquo;t available right now. Try again in a moment.</p>
        </Card>
      </Container>
    </main>
  );
}
