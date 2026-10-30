import { KeyRound, Server, Tag } from "lucide-react";

import { curlExample, type Reference, type ReferenceField, type ReferenceOperation } from "@/lib/marketing/public-api";

import { Ico } from "../landing/Ico";
import { SECTION_EYEBROW } from "../primitives";

const slug = (tag: string) => tag.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-");

/** A method's chip tone (site.css `.tag`): reads green, writes plain, changes amber, deletes red. */
const METHOD_TONE: Record<string, string> = { GET: "t-ok", POST: "t-plain", PUT: "t-need", PATCH: "t-need", DELETE: "t-stop" };

function Method({ method }: { method: string }) {
  return <span className={`tag method ${METHOD_TONE[method] ?? "t-plain"}`}>{method}</span>;
}

function Fields({ title, fields }: { title: string; fields: ReferenceField[] }) {
  if (fields.length === 0) return null;
  return (
    <div className="ep-part">
      <h4>{title}</h4>
      <div className="overflow-x-auto">
        <table className="ftable">
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Type</th>
              <th scope="col">Notes</th>
            </tr>
          </thead>
          <tbody>
            {fields.map((field) => (
              <tr key={field.name}>
                <td>
                  <code>{field.name}</code>
                  {field.required ? <span className="req">required</span> : null}
                </td>
                <td className="ftype">{field.type}</td>
                <td>{field.description}</td>
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
    <article id={operation.id} aria-labelledby={titleId} className="ep scroll-mt-24" data-operation={operation.id}>
      <header className="ep-head">
        <h3 id={titleId}>
          <Method method={operation.method} />
          <code>{operation.path}</code>
        </h3>
        <p className="ep-sum">{operation.summary}</p>
        {operation.scope ? (
          <p className="ep-scope">
            Needs the <code>{operation.scope}</code> scope.
          </p>
        ) : null}
      </header>
      {operation.paragraphs
        .filter((p) => !p.startsWith("Requires the `"))
        .map((paragraph) => (
          <p key={paragraph} className="ep-p">
            {paragraph.replaceAll("`", "")}
          </p>
        ))}
      <Fields title="Parameters" fields={operation.parameters} />
      {operation.body ? <Fields title="Request body (JSON)" fields={operation.body} /> : null}
      {operation.responses.length > 0 ? (
        <div className="ep-part">
          <h4>Responses</h4>
          <ul className="ep-res">
            {operation.responses.map((response) => (
              <li key={response.status}>
                <code>{response.status}</code> {response.description}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <pre className="code">
        <code>{curlExample(operation, baseUrl)}</code>
      </pre>
    </article>
  );
}

/**
 * The public API's reference (GR-25): how to authenticate, the scopes, then every operation by
 * area, from the API's own OpenAPI document. Server-rendered and static.
 *
 * C-159 look: the head beside a facts card (version, base URL, how to authenticate), a sticky side
 * nav on a wide screen listing each area with its operations and their methods (above the content
 * on a phone), each operation as an endpoint card with a method chip, and code on the night tokens.
 */
export function ApiReference({ reference, baseUrl }: { reference: Reference; baseUrl: string }) {
  const base = baseUrl.replace(/\/+$/, "");
  return (
    <main id="main" tabIndex={-1} className="pp flex-1 outline-none">
      <section className="page-head pp-head">
        <div className="wrap pp-head-grid">
          <div>
            <p className={SECTION_EYEBROW}>Developers</p>
            <h1 className="h-page">{reference.title}</h1>
            <div className="api-intro">
              {reference.paragraphs.map((paragraph) => (
                <p key={paragraph}>{paragraph.replaceAll("`", "")}</p>
              ))}
            </div>
          </div>
          <dl className="pp-toc api-facts">
            <div>
              <dt>
                <Ico icon={Tag} />
                Version
              </dt>
              <dd>{reference.version}</dd>
            </div>
            <div>
              <dt>
                <Ico icon={Server} />
                Base URL
              </dt>
              <dd>
                <code>{base}</code>
              </dd>
            </div>
            <div>
              <dt>
                <Ico icon={KeyRound} />
                Authentication
              </dt>
              <dd>
                <code>Authorization: Bearer</code>
              </dd>
            </div>
          </dl>
        </div>
      </section>

      <div className="band api-band">
        <div className="wrap api">
          <nav aria-label="Contents" className="api-nav">
            <h2>Contents</h2>
            <ul>
              <li>
                <a href="#authentication">Authentication</a>
              </li>
              {reference.groups.map((group) => (
                <li key={group.tag}>
                  <a href={`#${slug(group.tag)}`}>{group.tag}</a>
                  <ul>
                    {group.operations.map((operation) => (
                      <li key={operation.id}>
                        <a href={`#${operation.id}`} className="api-op">
                          <span className="api-m" data-method={operation.method}>
                            {operation.method}
                          </span>
                          <span className="api-p">{operation.summary}</span>
                        </a>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          </nav>

          <div className="api-main">
            <section id="authentication" aria-labelledby="authentication-title" className="api-sec scroll-mt-24">
              <h2 id="authentication-title" className="h-sec">
                Authentication
              </h2>
              <p className="ep-p">
                Make a key in Settings, Integrations, API keys. Send it on every request. A key belongs to one workspace and carries
                scopes; a request that needs a scope the key lacks is refused with 403.
              </p>
              <pre className="code">
                <code>{`curl "${base}/public/v1/contacts" \\\n  -H "Authorization: Bearer $SOCIALHOOD_API_KEY"`}</code>
              </pre>
              {reference.scopes.length > 0 ? (
                <div className="overflow-x-auto ep">
                  <table className="ftable">
                    <caption className="sr-only">Scopes</caption>
                    <thead>
                      <tr>
                        <th scope="col">Scope</th>
                        <th scope="col">Allows</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reference.scopes.map((scope) => (
                        <tr key={scope.scope}>
                          <td>
                            <code>{scope.scope}</code>
                          </td>
                          <td>{scope.description}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </section>

            {reference.groups.map((group) => (
              <section key={group.tag} id={slug(group.tag)} aria-labelledby={`${slug(group.tag)}-title`} className="api-sec scroll-mt-24">
                <h2 id={`${slug(group.tag)}-title`} className="h-sec">
                  {group.tag}
                </h2>
                {group.operations.map((operation) => (
                  <Operation key={operation.id} operation={operation} baseUrl={baseUrl} />
                ))}
              </section>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}

/** Shown when the API can't be reached: no stale or invented reference. */
export function ApiReferenceUnavailable() {
  return (
    <main id="main" tabIndex={-1} className="pp flex-1 outline-none">
      <section className="page-head pp-head">
        <div className="wrap">
          <p className={SECTION_EYEBROW}>Developers</p>
          <h1 className="h-page">Amplychat public API</h1>
          <div className="callout api-down" role="status">
            <p>The API reference isn&rsquo;t available right now. Try again in a moment.</p>
          </div>
        </div>
      </section>
    </main>
  );
}
