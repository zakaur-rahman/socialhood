import type { Metadata } from "next";
import { describe, expect, it } from "vitest";

import { DESCRIPTION_MAX, TITLE_MAX } from "@/lib/marketing/seo";
import { PUBLIC_PATHS, SITE_NAME } from "@/lib/marketing/site";

import { metadata as appLayout } from "./(clerk)/(app)/layout";
import { metadata as authLayout } from "./(clerk)/(auth)/layout";
import { metadata as unsubscribe } from "./(marketing)/unsubscribe/page";
import { metadata as notFound } from "./not-found";

/** Every public page module, by its route: "./(marketing)/compare/manychat/page.tsx" is "/compare/manychat". */
// "(marketing)" can't be written in a glob (parentheses are glob syntax), so filter the keys instead.
const MODULES = import.meta.glob<{ metadata?: Metadata }>("./**/page.tsx", { eager: true });
const BY_ROUTE: Record<string, Metadata | undefined> = Object.fromEntries(
  Object.entries(MODULES)
    .filter(([file]) => file.startsWith("./(marketing)/"))
    .map(([file, module]) => [file.replace("./(marketing)", "").replace(/\/page\.tsx$/, "") || "/", module.metadata]),
);

/** Every page the sitemap lists, with its metadata (C-142). */
const PAGES = PUBLIC_PATHS.map((path) => [path, BY_ROUTE[path]] as const);

/** The title a browser tab and a search result show: the root layout's "%s · Amplychat" template. */
function shownTitle(title: Metadata["title"]): string {
  if (typeof title === "string") return `${title} · ${SITE_NAME}`;
  if (title && typeof title === "object" && "absolute" in title) return title.absolute;
  throw new Error(`unexpected title ${JSON.stringify(title)}`);
}

describe("every public page's metadata (C-142)", () => {
  it("every page in the sitemap exists and exports metadata (no 404s in the sitemap)", () => {
    expect(PAGES.filter(([, metadata]) => !metadata).map(([path]) => path)).toEqual([]);
  });

  it.each(PAGES.filter(([, metadata]) => metadata))("%s: a title, a description, its canonical, Open Graph and Twitter", (path, found) => {
    const metadata = found as Metadata;
    const title = shownTitle(metadata.title);
    expect(title.length, title).toBeLessThanOrEqual(TITLE_MAX);
    expect(typeof metadata.description).toBe("string");
    const description = metadata.description as string;
    expect(description.length, description).toBeGreaterThanOrEqual(50);
    expect(description.length, description).toBeLessThanOrEqual(DESCRIPTION_MAX);
    expect(metadata.alternates?.canonical).toBe(path);
    expect(metadata.openGraph).toMatchObject({ url: path, images: [expect.objectContaining({ url: "/og.png" })] });
    expect(metadata.twitter).toMatchObject({ card: "summary_large_image" });
    expect(metadata.robots).toBeUndefined();
  });

  it("titles and descriptions are unique", () => {
    const found = PAGES.flatMap(([, metadata]) => (metadata ? [metadata] : []));
    const titles = found.map((metadata) => shownTitle(metadata.title));
    const descriptions = found.map((metadata) => metadata.description);
    expect(new Set(titles).size).toBe(titles.length);
    expect(new Set(descriptions).size).toBe(descriptions.length);
  });
});

describe("pages that are never indexed (C-142)", () => {
  it("the app, sign-in and sign-up, unsubscribe links and the 404", () => {
    expect(appLayout.robots).toMatchObject({ index: false });
    expect(authLayout.robots).toMatchObject({ index: false });
    expect(unsubscribe.robots).toMatchObject({ index: false });
    expect(notFound.robots).toMatchObject({ index: false });
  });
});
