import { t } from "../../i18n/messages.ts";

/** Field-level validation messages from the error envelope (`docs/conventions/api.md`). */
export type FieldErrors = Readonly<Record<string, readonly string[]>>;

/** Client-side codes for failures that never produced a parseable server envelope. */
export const CLIENT_ERROR_CODES = {
  network: "network_error",
  unexpected: "unexpected_response",
} as const;

export interface ApiErrorInit {
  status: number;
  code: string;
  message: string;
  fields?: FieldErrors;
  requestId?: string | null;
}

/**
 * Every failed API call rejects with an ApiError.
 * `status` is 0 when no HTTP response was received (network failure).
 * `message` is safe to show to users; `code` is the stable machine-readable value.
 */
export class ApiError extends Error {
  override readonly name = "ApiError";
  readonly status: number;
  readonly code: string;
  readonly fields: FieldErrors;
  readonly requestId: string | null;

  constructor(init: ApiErrorInit) {
    super(init.message);
    this.status = init.status;
    this.code = init.code;
    this.fields = init.fields ?? {};
    this.requestId = init.requestId ?? null;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseFields(value: unknown): FieldErrors | null {
  if (value === undefined || value === null) return {};
  if (!isRecord(value)) return null;
  const out: Record<string, readonly string[]> = {};
  for (const [field, list] of Object.entries(value)) {
    if (!Array.isArray(list) || !list.every((m): m is string => typeof m === "string")) {
      return null;
    }
    out[field] = list;
  }
  return out;
}

/**
 * Parse a response body into an ApiError.
 *
 * A body that does not match the envelope shape exactly is never trusted for its
 * message: it becomes a generic `unexpected_response` error, so proxy or HTML error
 * pages are never shown to the user.
 */
export function parseErrorEnvelope(
  status: number,
  body: unknown,
  headerRequestId: string | null = null,
): ApiError {
  const generic = (): ApiError =>
    new ApiError({
      status,
      code: CLIENT_ERROR_CODES.unexpected,
      message: t("api.error.unexpected"),
      requestId: headerRequestId,
    });

  if (!isRecord(body) || !isRecord(body.error)) return generic();
  const { code, message, fields, request_id: requestId } = body.error;
  if (typeof code !== "string" || code === "" || typeof message !== "string") return generic();
  if (requestId !== undefined && requestId !== null && typeof requestId !== "string") {
    return generic();
  }
  const parsedFields = parseFields(fields);
  if (parsedFields === null) return generic();

  return new ApiError({
    status,
    code,
    message,
    fields: parsedFields,
    requestId: requestId ?? headerRequestId,
  });
}

export function networkError(): ApiError {
  return new ApiError({
    status: 0,
    code: CLIENT_ERROR_CODES.network,
    message: t("api.error.network"),
  });
}
