import { notFound } from "next/navigation";

/** Any address under a workspace that no page claims: render the workspace's 404 (not-found.tsx). */
export default function UnknownWorkspacePage(): never {
  notFound();
}
