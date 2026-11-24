import type { Route } from "next";
import { redirect } from "next/navigation";

type Query = Record<string, string | string[] | undefined>;

/** C-180: Connections is its own page now. Old links, emails and the connect return keep working, query and all. */
export default async function OldConnectionsRoute({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<Query>;
}) {
  const { slug } = await params;
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(await searchParams)) {
    for (const item of [value].flat()) if (item !== undefined) query.append(key, item);
  }
  const rest = query.size > 0 ? `?${query}` : "";
  redirect(`/w/${slug}/connections${rest}` as Route);
}
