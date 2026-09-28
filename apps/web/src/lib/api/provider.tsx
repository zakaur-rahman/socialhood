"use client";

import { useAuth } from "@clerk/nextjs";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

import { makeApi, type Api } from "./client";
import { ApiError } from "./errors";

const ApiContext = createContext<Api | null>(null);

function shouldRetry(failureCount: number, error: unknown): boolean {
  // Client errors (4xx) will not change on retry; network and server errors might.
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
  return failureCount < 2;
}

/** One API client and one query cache per tab (TR-FE-02). */
export function ApiProvider({ children }: { children: ReactNode }) {
  const { getToken } = useAuth();
  const api = useMemo(
    () =>
      makeApi(async () => {
        try {
          return await getToken();
        } catch {
          return null; // Clerk Core 3 throws during SSR or offline; the API then answers 401.
        }
      }),
    [getToken],
  );
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: shouldRetry, refetchOnWindowFocus: false, staleTime: 30_000 },
        },
      }),
  );
  return (
    <ApiContext.Provider value={api}>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </ApiContext.Provider>
  );
}

export function useApi(): Api {
  const api = useContext(ApiContext);
  if (!api) throw new Error("useApi must be used inside <ApiProvider>");
  return api;
}
