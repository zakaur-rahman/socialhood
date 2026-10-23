"use client";

import { useQuery } from "@tanstack/react-query";

import { useApi } from "../provider";
import type { WeeklyReport } from "../types";
import { keys } from "./keys";
import { unwrap } from "./unwrap";

/**
 * The weekly report (GR-34): a finished Monday to Sunday against the week before, and the weeks
 * leading up to it. `week` is the Monday (YYYY-MM-DD); without one the API gives the latest
 * finished week. Another week keeps the last report on screen until its own arrives (never
 * another workspace's).
 */
export function useWeeklyReport(wid: string, week: string | null) {
  const api = useApi();
  return useQuery<WeeklyReport, Error>({
    queryKey: keys.weeklyReport(wid, week ?? "latest"),
    placeholderData: (previous, previousQuery) => (previousQuery?.queryKey[1] === wid ? previous : undefined),
    queryFn: () =>
      unwrap(api.GET("/v1/w/{wid}/reports/weekly", { params: { path: { wid }, query: week ? { week } : {} } })),
    // A finished week doesn't change much; the digest and the page agree whenever it is opened.
    staleTime: 60_000,
  });
}
