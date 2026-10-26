import { securityTxt } from "@/lib/security/security-txt";

// Rebuilt once a day, so Expires stays about a year out without a deploy (RFC 9116, C-143).
export const revalidate = 86400;

export function GET(): Response {
  return new Response(securityTxt(), {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
