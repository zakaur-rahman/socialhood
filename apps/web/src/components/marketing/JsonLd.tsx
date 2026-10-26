import { breadcrumbJsonLd, jsonLdString } from "@/lib/marketing/seo";

/** A schema.org JSON-LD block; "<" is escaped so the data can't close the script tag. */
export function JsonLd({ data }: { data: unknown }) {
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdString(data) }} />;
}

/** An inner public page's BreadcrumbList: Home, then this page (C-142). */
export function BreadcrumbJsonLd({ name, path }: { name: string; path: string }) {
  return <JsonLd data={breadcrumbJsonLd(name, path)} />;
}
