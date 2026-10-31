import { GLOSSARY, GLOSSARY_PATH, glossaryPath, type GlossaryTerm } from "./glossary";
import { organizationId } from "./seo";
import { absoluteUrl, siteUrl } from "./site";

/** The set's name, as the index's h1 says it. */
export const GLOSSARY_NAME = "Meta messaging glossary";

function setNode(origin: string): Record<string, unknown> {
  const url = absoluteUrl(GLOSSARY_PATH, origin);
  return { "@type": "DefinedTermSet", "@id": `${url}#set`, name: GLOSSARY_NAME, url };
}

function termNode(term: GlossaryTerm, origin: string, inSet: Record<string, unknown>): Record<string, unknown> {
  const url = absoluteUrl(glossaryPath(term.slug), origin);
  return {
    "@type": "DefinedTerm",
    "@id": `${url}#term`,
    name: term.term,
    ...(term.aka?.length ? { alternateName: [...term.aka] } : {}),
    description: term.definition,
    url,
    inDefinedTermSet: inSet,
  };
}

/** The index (C-163): a DefinedTermSet with every term, each pointing back at the set. */
export function definedTermSetJsonLd(terms: readonly GlossaryTerm[] = GLOSSARY, origin: string = siteUrl()): Record<string, unknown> {
  const set = setNode(origin);
  return {
    "@context": "https://schema.org",
    ...set,
    description: "Plain definitions of the WhatsApp, Instagram and Messenger terms businesses meet, from Meta's own documentation.",
    inLanguage: "en",
    publisher: { "@id": organizationId(origin) },
    hasDefinedTerm: terms.map((term) => termNode(term, origin, { "@id": set["@id"] })),
  };
}

/** One term's page (C-163): a DefinedTerm in the set. */
export function definedTermJsonLd(term: GlossaryTerm, origin: string = siteUrl()): Record<string, unknown> {
  return { "@context": "https://schema.org", ...termNode(term, origin, setNode(origin)) };
}
