import { ApiError, networkError, parseErrorEnvelope } from "./errors.ts";

/**
 * The single API client (docs/conventions/frontend.md).
 *
 * Security properties (change 0003, SC-40):
 * - Only same-origin paths under /api/ are accepted, so cookies and the CSRF header
 *   can never be sent to another origin.
 * - `credentials: "same-origin"`; auth lives only in HttpOnly cookies set by the server.
 * - The CSRF token is read from the CSRF cookie and sent as `X-CSRFToken` on unsafe
 *   methods only.
 */

export type HttpMethod = "GET" | "HEAD" | "POST" | "PUT" | "PATCH" | "DELETE";

const UNSAFE_METHODS: ReadonlySet<HttpMethod> = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const API_PREFIX = "/api/";
export const CSRF_HEADER = "X-CSRFToken";
export const REQUEST_ID_HEADER = "X-Request-ID";

/** A programming error: a path outside the allowed API space. `resolveApiPath` throws it; `apiRequest` rejects with it. */
export class ApiPathError extends Error {
  override readonly name = "ApiPathError";
}

/**
 * Django CSRF cookie name. Development uses `rms_csrf` because the `__Host-` prefix
 * requires HTTPS; every other build uses `__Host-rms_csrf` (design 6.2/6.4).
 */
export function csrfCookieName(isDev: boolean = import.meta.env.DEV): string {
  return isDev ? "rms_csrf" : "__Host-rms_csrf";
}

export function readCookie(name: string, cookieString: string = document.cookie): string | null {
  for (const part of cookieString.split(";")) {
    const eq = part.indexOf("=");
    if (eq === -1) continue;
    if (part.slice(0, eq).trim() !== name) continue;
    const raw = part.slice(eq + 1).trim();
    try {
      return decodeURIComponent(raw);
    } catch {
      return null;
    }
  }
  return null;
}

// Backslashes, whitespace and control characters are rewritten by URL parsers; reject them.
// eslint-disable-next-line no-control-regex -- matching control characters is the point.
const FORBIDDEN_PATH_CHARS = /[\\\s\u0000-\u001f\u007f]/;

const PATH_ERROR = "API client accepts only relative paths starting with /api/";

/**
 * Validate and normalise an API path. Returns `pathname + search` of the resolved
 * same-origin URL. Rejects absolute URLs, protocol-relative URLs, anything that
 * resolves outside /api/ (for example via `..`), and fragments.
 */
export function resolveApiPath(path: string, origin: string = window.location.origin): string {
  if (!path.startsWith(API_PREFIX) || FORBIDDEN_PATH_CHARS.test(path)) {
    throw new ApiPathError(PATH_ERROR);
  }
  const url = new URL(path, origin);
  if (url.origin !== origin || !url.pathname.startsWith(API_PREFIX) || url.hash !== "") {
    throw new ApiPathError(PATH_ERROR);
  }
  return url.pathname + url.search;
}

type UnauthorizedHandler = (error: ApiError) => void;
let onUnauthorized: UnauthorizedHandler = () => {
  // Stub until the app-shell change (0008) adds the re-authentication flow.
};

/** Register the 401 handler (0008). Returns a function that restores the previous one. */
export function setUnauthorizedHandler(handler: UnauthorizedHandler): () => void {
  const previous = onUnauthorized;
  onUnauthorized = handler;
  return () => {
    onUnauthorized = previous;
  };
}

export interface ApiRequestOptions {
  method?: HttpMethod;
  /** JSON-serialisable request body. */
  body?: unknown;
  headers?: Readonly<Record<string, string>>;
  signal?: AbortSignal;
}

function isJson(response: Response): boolean {
  const type = response.headers.get("Content-Type") ?? "";
  return /^application\/(?:[\w.+-]+\+)?json\b/i.test(type);
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return (await response.json()) as unknown;
  } catch {
    return undefined;
  }
}

function isAbortError(error: unknown, signal: AbortSignal | undefined): boolean {
  if (signal?.aborted === true) return true;
  // DOMException is not an Error subclass in every runtime; compare by name.
  return (
    typeof error === "object" && error !== null && "name" in error && error.name === "AbortError"
  );
}

/**
 * Perform an API request. Resolves with the parsed JSON body (or `undefined` for an
 * empty response). Rejects with ApiError on any HTTP error or network failure;
 * rethrows an AbortError untouched so query cancellation keeps working.
 */
export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const url = resolveApiPath(path);

  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  // A caller can never inject a CSRF header; it is set only from the cookie below.
  headers.delete(CSRF_HEADER);
  if (options.body !== undefined) headers.set("Content-Type", "application/json");
  if (UNSAFE_METHODS.has(method)) {
    const token = readCookie(csrfCookieName());
    if (token !== null && token !== "") headers.set(CSRF_HEADER, token);
  }

  const init: RequestInit = {
    method,
    headers,
    credentials: "same-origin",
    // A redirect could point elsewhere; the API never redirects, so treat it as an error.
    redirect: "error",
  };
  if (options.body !== undefined) init.body = JSON.stringify(options.body);
  if (options.signal !== undefined) init.signal = options.signal;

  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (error) {
    if (isAbortError(error, options.signal)) throw error;
    throw networkError();
  }

  const headerRequestId = response.headers.get(REQUEST_ID_HEADER);

  if (!response.ok) {
    const body = isJson(response) ? await readJson(response) : undefined;
    const apiError = parseErrorEnvelope(response.status, body, headerRequestId);
    if (response.status === 401) onUnauthorized(apiError);
    throw apiError;
  }

  if (response.status === 204 || method === "HEAD") return undefined as T;
  const text = await response.text();
  if (text === "") return undefined as T;
  if (!isJson(response)) throw parseErrorEnvelope(response.status, undefined, headerRequestId);
  try {
    return JSON.parse(text) as T;
  } catch {
    throw parseErrorEnvelope(response.status, undefined, headerRequestId);
  }
}
