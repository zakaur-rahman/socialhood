import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "@socialhood/api-client";

type ClientOptions = {
  /** Defaults to NEXT_PUBLIC_API_BASE_URL. */
  baseUrl?: string;
  /** Tests pass a fake fetch; the app uses the browser's. */
  fetch?: (request: Request) => Promise<Response>;
};

/**
 * The one API client (TR-FE-02). A provider creates it once with Clerk's getToken (P1); the
 * token is fetched per request because Clerk tokens live about 60 seconds (TR-AUTH-01).
 */
export function makeApi(getToken: () => Promise<string | null>, options: ClientOptions = {}) {
  const api = createClient<paths>({
    baseUrl: options.baseUrl ?? process.env.NEXT_PUBLIC_API_BASE_URL,
    ...(options.fetch ? { fetch: options.fetch } : {}),
  });
  const auth: Middleware = {
    async onRequest({ request }) {
      const token = await getToken();
      if (token) request.headers.set("Authorization", `Bearer ${token}`);
      return request;
    },
  };
  api.use(auth);
  return api;
}

export type Api = ReturnType<typeof makeApi>;
