import { BreadcrumbJsonLd } from "@/components/marketing/JsonLd";
import { LEGAL_DOCUMENTS } from "@/lib/legal";

const { title, path } = LEGAL_DOCUMENTS.terms;

/** The page's BreadcrumbList (C-142), kept beside the document so the text stays the legal page's own. */
export default function Layout({ children }: LayoutProps<"/terms">) {
  return (
    <>
      <BreadcrumbJsonLd name={title} path={path} />
      {children}
    </>
  );
}
