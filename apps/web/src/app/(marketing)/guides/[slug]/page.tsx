import { notFound } from "next/navigation";

import { GuideView } from "@/components/marketing/guides/GuideView";
import { GUIDES, GUIDES_FEED_PATH, findGuide, guidePath } from "@/lib/marketing/guides";
import { pageMetadata } from "@/lib/marketing/seo";
import { SITE_NAME } from "@/lib/marketing/site";

/** Only the guides in lib/marketing/guides exist; any other slug is a 404. */
export const dynamicParams = false;

export function generateStaticParams(): { slug: string }[] {
  return GUIDES.map((guide) => ({ slug: guide.slug }));
}

export async function generateMetadata({ params }: PageProps<"/guides/[slug]">) {
  const guide = findGuide((await params).slug);
  if (!guide) return {};
  return pageMetadata({
    title: guide.title,
    description: guide.description,
    path: guidePath(guide.slug),
    article: { publishedTime: guide.published, modifiedTime: guide.updated, authors: [guide.author], tags: [...guide.tags] },
    feeds: { [`${SITE_NAME} guides`]: GUIDES_FEED_PATH },
  });
}

/** A guide (C-153), from lib/marketing/guides. Static: one page per guide at build time. */
export default async function GuidePage({ params }: PageProps<"/guides/[slug]">) {
  const guide = findGuide((await params).slug);
  if (!guide) notFound();
  return <GuideView guide={guide} />;
}
