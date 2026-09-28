import { toApiError } from "../errors";

type Result<T> = { data?: T; error?: unknown; response: Response };

/** Return the data of an openapi-fetch call, or throw an ApiError (problem+json or network). */
export async function unwrap<T>(call: Promise<Result<T>>): Promise<T> {
  let result: Result<T>;
  try {
    result = await call;
  } catch (error) {
    throw toApiError(error);
  }
  if (result.error !== undefined || result.data === undefined) {
    throw toApiError(result.error, result.response.status);
  }
  return result.data;
}

/** For endpoints that answer 204: throw an ApiError unless the response is 2xx. */
export async function expectOk(call: Promise<{ error?: unknown; response: Response }>): Promise<void> {
  let result: { error?: unknown; response: Response };
  try {
    result = await call;
  } catch (error) {
    throw toApiError(error);
  }
  if (!result.response.ok) throw toApiError(result.error, result.response.status);
}
