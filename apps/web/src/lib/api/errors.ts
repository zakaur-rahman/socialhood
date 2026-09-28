/**
 * API errors (TR-API-03, TR-FE-02). Every non-2xx response is application/problem+json; this
 * turns it into an ApiError the UI can show with the copy for its code (§4.7).
 */
export type ProblemField = { field: string; message: string };

export type Problem = {
  type: string;
  title: string;
  status: number;
  code: string;
  detail?: string;
  errors?: ProblemField[];
  request_id?: string | null;
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail?: string;
  readonly errors: ProblemField[];
  readonly requestId?: string | null;

  constructor(problem: Problem) {
    super(problem.detail ?? problem.title);
    this.name = "ApiError";
    this.status = problem.status;
    this.code = problem.code;
    this.detail = problem.detail;
    this.errors = problem.errors ?? [];
    this.requestId = problem.request_id;
  }
}

function isProblem(value: unknown): value is Problem {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return typeof v.code === "string" && typeof v.status === "number";
}

/** Converts whatever a failed call produced into an ApiError; network failures become "network". */
export function toApiError(error: unknown, status?: number): ApiError {
  if (error instanceof ApiError) return error;
  if (isProblem(error)) return new ApiError(error);
  return new ApiError({
    type: "about:blank",
    title: "Request failed",
    status: status ?? 0,
    code: status ? "internal" : "network",
  });
}
