import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import {
  ApiPathError,
  apiRequest,
  CSRF_HEADER,
  csrfCookieName,
  readCookie,
  resolveApiPath,
  setUnauthorizedHandler,
  type HttpMethod,
} from "./client.ts";
import { ApiError } from "./errors.ts";

const ORIGIN = window.location.origin;
const CSRF_VALUE = "csrf-test-value";

function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

function clearCookies(): void {
  for (const part of document.cookie.split(";")) {
    const name = part.split("=")[0]?.trim();
    if (name) document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
  }
}

let fetchMock: Mock<typeof fetch>;

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>();
  vi.stubGlobal("fetch", fetchMock);
  clearCookies();
});

afterEach(() => {
  clearCookies();
});

function lastInit(): RequestInit {
  const call = fetchMock.mock.calls.at(-1);
  if (call === undefined) throw new Error("fetch was not called");
  return call[1] ?? {};
}

function lastHeaders(): Headers {
  return new Headers(lastInit().headers);
}

describe("relative-path enforcement (SC-40, NT3-40)", () => {
  it.each([
    "https://evil.test/api/x",
    "http://evil.test/x",
    "//evil.test/x",
    "//evil.test/api/x",
    "/\\evil.test/api/x",
    "\\\\evil.test/api/x",
    "api/x",
    "/x",
    "/apix",
    "/api",
    "/api/../admin/",
    "/api/%2e%2e/admin",
    "/api/x\nHost: evil",
    "/api/ x",
    "/api/x#frag",
    "javascript:alert(1)",
    "",
  ])("rejects %j without calling fetch", async (path) => {
    await expect(apiRequest(path, { method: "POST" })).rejects.toBeInstanceOf(ApiPathError);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("accepts a same-origin /api/ path and sends only the path and query", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }));
    await apiRequest("/api/v1/me?x=1");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/me?x=1", expect.anything());
  });

  it("normalises in-prefix dot segments", () => {
    expect(resolveApiPath("/api/v1/a/../b", ORIGIN)).toBe("/api/v1/b");
  });

  it("uses same-origin credentials and refuses redirects", async () => {
    fetchMock.mockResolvedValue(jsonResponse({}));
    await apiRequest("/api/v1/me");
    expect(lastInit().credentials).toBe("same-origin");
    expect(lastInit().redirect).toBe("error");
  });
});

describe("CSRF header (NT3-40)", () => {
  beforeEach(() => {
    document.cookie = `${csrfCookieName()}=${CSRF_VALUE}; path=/`;
    fetchMock.mockImplementation(() => Promise.resolve(jsonResponse({})));
  });

  it.each<HttpMethod>(["POST", "PUT", "PATCH", "DELETE"])(
    "sends X-CSRFToken from the cookie on %s",
    async (method) => {
      await apiRequest("/api/v1/thing", { method, body: { a: 1 } });
      expect(lastHeaders().get(CSRF_HEADER)).toBe(CSRF_VALUE);
    },
  );

  it.each<HttpMethod>(["GET", "HEAD"])("does not send X-CSRFToken on %s", async (method) => {
    await apiRequest("/api/v1/thing", { method });
    expect(lastHeaders().has(CSRF_HEADER)).toBe(false);
  });

  it("ignores a caller-supplied CSRF header on a safe method", async () => {
    await apiRequest("/api/v1/thing", { headers: { "X-CSRFToken": "injected" } });
    expect(lastHeaders().has(CSRF_HEADER)).toBe(false);
  });

  it("replaces a caller-supplied CSRF header with the cookie value", async () => {
    await apiRequest("/api/v1/thing", {
      method: "POST",
      headers: { "x-csrftoken": "injected" },
    });
    expect(lastHeaders().get(CSRF_HEADER)).toBe(CSRF_VALUE);
  });

  it("omits the header when the cookie is absent", async () => {
    clearCookies();
    await apiRequest("/api/v1/thing", { method: "POST" });
    expect(lastHeaders().has(CSRF_HEADER)).toBe(false);
  });

  it("sends a JSON body with a JSON content type", async () => {
    await apiRequest("/api/v1/thing", { method: "POST", body: { name: "Table 1" } });
    expect(lastInit().body).toBe(JSON.stringify({ name: "Table 1" }));
    expect(lastHeaders().get("Content-Type")).toBe("application/json");
  });
});

describe("csrfCookieName and readCookie", () => {
  it("uses rms_csrf in development and __Host-rms_csrf otherwise", () => {
    expect(csrfCookieName(true)).toBe("rms_csrf");
    expect(csrfCookieName(false)).toBe("__Host-rms_csrf");
  });

  it("reads an exact cookie name only", () => {
    const cookies = "xrms_csrf=wrong; rms_csrf=right%20value; other=1";
    expect(readCookie("rms_csrf", cookies)).toBe("right value");
    expect(readCookie("missing", cookies)).toBeNull();
  });

  it("returns null for an undecodable cookie value", () => {
    expect(readCookie("rms_csrf", "rms_csrf=%E0%A4%A")).toBeNull();
  });
});

describe("responses and errors", () => {
  it("resolves with the parsed JSON body", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ status: "ok" }));
    await expect(apiRequest("/api/v1/thing")).resolves.toEqual({ status: "ok" });
  });

  it("resolves undefined for 204", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    await expect(apiRequest("/api/v1/thing", { method: "DELETE" })).resolves.toBeUndefined();
  });

  it("rejects with the parsed envelope on an error status", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        {
          error: {
            code: "validation_error",
            message: "Check the fields.",
            fields: { name: ["Required."] },
            request_id: "req-1",
          },
        },
        400,
      ),
    );
    const error = await apiRequest("/api/v1/thing", { method: "POST" }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 400,
      code: "validation_error",
      fields: { name: ["Required."] },
      requestId: "req-1",
    });
  });

  it("rejects with a generic error for a non-JSON error response", async () => {
    fetchMock.mockResolvedValue(
      new Response("<html>502</html>", {
        status: 502,
        headers: { "Content-Type": "text/html", "X-Request-ID": "req-2" },
      }),
    );
    await expect(apiRequest("/api/v1/thing")).rejects.toMatchObject({
      status: 502,
      code: "unexpected_response",
      requestId: "req-2",
    });
  });

  it("rejects with a generic error for invalid JSON on success", async () => {
    fetchMock.mockResolvedValue(
      new Response("{not json", { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    await expect(apiRequest("/api/v1/thing")).rejects.toMatchObject({
      code: "unexpected_response",
    });
  });

  it("turns a network failure into network_error with status 0", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(apiRequest("/api/v1/thing")).rejects.toMatchObject({
      status: 0,
      code: "network_error",
    });
  });

  it("rethrows an abort untouched", async () => {
    fetchMock.mockRejectedValue(new DOMException("aborted", "AbortError"));
    await expect(apiRequest("/api/v1/thing")).rejects.toMatchObject({ name: "AbortError" });
  });

  it("calls the 401 handler and still rejects", async () => {
    const handler = vi.fn();
    const restore = setUnauthorizedHandler(handler);
    try {
      fetchMock.mockResolvedValue(
        jsonResponse({ error: { code: "not_authenticated", message: "Sign in." } }, 401),
      );
      await expect(apiRequest("/api/v1/me")).rejects.toMatchObject({ status: 401 });
      expect(handler).toHaveBeenCalledOnce();
      expect(handler.mock.calls[0]?.[0]).toBeInstanceOf(ApiError);
    } finally {
      restore();
    }
  });
});
