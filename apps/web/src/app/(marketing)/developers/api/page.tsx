import { ApiReference, ApiReferenceUnavailable } from "@/components/marketing/developers/ApiReference";
import { buildReference, fetchPublicApiDocument } from "@/lib/marketing/public-api";
import { pageMetadata } from "@/lib/marketing/seo";

// Next reads segment config at build time, so it must be a literal: keep it equal to
// PUBLIC_API_REVALIDATE_SECONDS in lib/marketing/public-api.
export const revalidate = 3600;

export const metadata = pageMetadata({
  title: "Public API",
  description:
    "The Social Hood public API: authenticate with an API key, read and update contacts, tags and conversations, send messages inside the reply window, and subscribe REST hooks for Zapier.",
  path: "/developers/api",
});

/** GR-25: the public API's reference, rendered from the API's own OpenAPI document (/public/v1). */
export default async function PublicApiPage() {
  const document = await fetchPublicApiDocument();
  if (!document) return <ApiReferenceUnavailable />;
  return (
    <ApiReference
      reference={buildReference(document)}
      baseUrl={process.env.NEXT_PUBLIC_API_BASE_URL ?? "https://api.socialhood.com"}
    />
  );
}
