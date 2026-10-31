import { notFound } from "next/navigation";

import { TermView } from "@/components/marketing/glossary/GlossaryView";
import { GLOSSARY, findTerm, glossaryPath } from "@/lib/marketing/glossary";
import { pageMetadata } from "@/lib/marketing/seo";

/** Only the terms in lib/marketing/glossary exist; any other slug is a 404. */
export const dynamicParams = false;

export function generateStaticParams(): { term: string }[] {
  return GLOSSARY.map((term) => ({ term: term.slug }));
}

export async function generateMetadata({ params }: PageProps<"/glossary/[term]">) {
  const term = findTerm((await params).term);
  if (!term) return {};
  return pageMetadata({ title: term.title, description: term.definition, path: glossaryPath(term.slug) });
}

/** One glossary term (C-163). Static: one page per term at build time. */
export default async function TermPage({ params }: PageProps<"/glossary/[term]">) {
  const term = findTerm((await params).term);
  if (!term) notFound();
  return <TermView term={term} />;
}
