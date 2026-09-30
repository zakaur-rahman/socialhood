"use client";

import { useAuth } from "@clerk/nextjs";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { inferEntitlement } from "@/lib/copy";

import { makeApi, type Api } from "./client";
import { ApiError, isPlanLimitError } from "./errors";

const ApiContext = createContext<Api | null>(null);

function shouldRetry(failureCount: number, error: unknown): boolean {
  // Client errors (4xx) will not change on retry; network and server errors might.
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
  return failureCount < 2;
}

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: shouldRetry, refetchOnWindowFocus: false, staleTime: 30_000 },
    },
  });
}

// ---- the upgrade dialog (F-15, T8.4): every 402 opens it

/** What the upgrade dialog is about: a 402's code, §1.7 key and limit (C-049). */
export type UpgradeRequest = {
  code: "entitlement_required" | "quota_exceeded";
  entitlement?: string | null;
  limit?: number | null;
  detail?: string | null;
};

export function upgradeRequestFrom(error: ApiError): UpgradeRequest {
  return {
    code: error.code === "quota_exceeded" ? "quota_exceeded" : "entitlement_required",
    entitlement: error.entitlement ?? inferEntitlement(error.detail),
    limit: error.limit,
    detail: error.detail ?? null,
  };
}

const REOPEN_AFTER_MS = 30_000;

function requestKey(request: UpgradeRequest): string {
  return `${request.code}:${request.entitlement ?? request.detail ?? ""}`;
}

type UpgradeContextValue = {
  request: UpgradeRequest | null;
  open: (request: UpgradeRequest) => void;
  close: () => void;
};

const NO_UPGRADE: UpgradeContextValue = { request: null, open: () => {}, close: () => {} };
const UpgradeContext = createContext<UpgradeContextValue>(NO_UPGRADE);

/**
 * The upgrade dialog's state. A 402 from any query or mutation opens it (F-15: "A gated action
 * returns 402. The UI shows the upgrade dialog naming the limit"); screens open it themselves for
 * a limit they know before asking (Auto on Free). components/billing/UpgradeDialog shows it.
 */
export function useUpgradeDialog(): UpgradeContextValue {
  return useContext(UpgradeContext);
}

/**
 * Watches both caches for a 402. A mutation can opt out with `meta: { upgradeDialog: false }`
 * when its screen explains the limit another way.
 */
function usePlanLimitErrors(queryClient: QueryClient, open: (request: UpgradeRequest) => void) {
  useEffect(() => {
    const seen = new WeakSet<object>();
    const onError = (error: unknown) => {
      if (!isPlanLimitError(error) || seen.has(error)) return;
      seen.add(error);
      open(upgradeRequestFrom(error));
    };
    const offMutations = queryClient.getMutationCache().subscribe((event) => {
      if (event.type !== "updated" || event.action.type !== "error") return;
      if (event.mutation.meta?.upgradeDialog === false) return;
      onError(event.action.error);
    });
    const offQueries = queryClient.getQueryCache().subscribe((event) => {
      if (event.type === "updated" && event.action.type === "error") onError(event.action.error);
    });
    return () => {
      offMutations();
      offQueries();
    };
  }, [queryClient, open]);
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
  const [queryClient] = useState(makeQueryClient);
  return (
    <ApiClientProvider api={api} queryClient={queryClient}>
      {children}
    </ApiClientProvider>
  );
}

/** The providers without Clerk: ApiProvider uses it, and tests pass a client with a fake fetch. */
export function ApiClientProvider({
  api,
  queryClient,
  children,
}: {
  api: Api;
  queryClient: QueryClient;
  children: ReactNode;
}) {
  const [request, setRequest] = useState<UpgradeRequest | null>(null);
  const dismissed = useRef<{ key: string; at: number } | null>(null);
  const open = useCallback((next: UpgradeRequest) => setRequest(next), []);
  const close = useCallback(() => {
    if (request) dismissed.current = { key: requestKey(request), at: Date.now() };
    setRequest(null);
  }, [request]);
  // A 402 the member just dismissed doesn't reopen it straight away (say, a retry loop); opening it
  // from a button always does.
  const openFromError = useCallback((next: UpgradeRequest) => {
    const last = dismissed.current;
    if (last && last.key === requestKey(next) && Date.now() - last.at < REOPEN_AFTER_MS) return;
    setRequest(next);
  }, []);
  const upgrade = useMemo(() => ({ request, open, close }), [request, open, close]);
  usePlanLimitErrors(queryClient, openFromError);
  return (
    <ApiContext.Provider value={api}>
      <QueryClientProvider client={queryClient}>
        <UpgradeContext.Provider value={upgrade}>{children}</UpgradeContext.Provider>
      </QueryClientProvider>
    </ApiContext.Provider>
  );
}

export function useApi(): Api {
  const api = useContext(ApiContext);
  if (!api) throw new Error("useApi must be used inside <ApiProvider>");
  return api;
}
