import { describe, expect, it } from "vitest";
import { messages } from "../../i18n/messages.ts";
import { ApiError, CLIENT_ERROR_CODES, networkError, parseErrorEnvelope } from "./errors.ts";

describe("parseErrorEnvelope", () => {
  it("parses a full envelope with fields and request_id", () => {
    const error = parseErrorEnvelope(400, {
      error: {
        code: "validation_error",
        message: "Check the highlighted fields.",
        fields: { name: ["This field is required."], price: ["Too long.", "Invalid."] },
        request_id: "req-body",
      },
    });

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(400);
    expect(error.code).toBe("validation_error");
    expect(error.message).toBe("Check the highlighted fields.");
    expect(error.fields).toEqual({
      name: ["This field is required."],
      price: ["Too long.", "Invalid."],
    });
    expect(error.requestId).toBe("req-body");
  });

  it("defaults fields to empty and falls back to the header request ID", () => {
    const error = parseErrorEnvelope(
      404,
      { error: { code: "not_found", message: "Not found.", request_id: null } },
      "req-header",
    );
    expect(error.code).toBe("not_found");
    expect(error.fields).toEqual({});
    expect(error.requestId).toBe("req-header");
  });

  it("prefers the body request_id over the header", () => {
    const error = parseErrorEnvelope(
      403,
      { error: { code: "csrf_failed", message: "Refresh and retry.", request_id: "req-body" } },
      "req-header",
    );
    expect(error.requestId).toBe("req-body");
  });

  it.each([
    ["undefined body", undefined],
    ["string body (HTML error page)", "<html>Bad gateway</html>"],
    ["array body", []],
    ["no error key", { detail: "Not found." }],
    ["error is a string", { error: "boom" }],
    ["missing code", { error: { message: "x" } }],
    ["empty code", { error: { code: "", message: "x" } }],
    ["numeric code", { error: { code: 5, message: "x" } }],
    ["missing message", { error: { code: "x" } }],
    ["fields not an object", { error: { code: "x", message: "y", fields: ["a"] } }],
    ["field value not a list", { error: { code: "x", message: "y", fields: { a: "b" } } }],
    ["field list with non-string", { error: { code: "x", message: "y", fields: { a: [1] } } }],
    ["request_id not a string", { error: { code: "x", message: "y", request_id: 7 } }],
  ])("returns a generic error for a malformed body: %s", (_label, body) => {
    const error = parseErrorEnvelope(502, body, "req-header");
    expect(error.status).toBe(502);
    expect(error.code).toBe(CLIENT_ERROR_CODES.unexpected);
    expect(error.message).toBe(messages["api.error.unexpected"]);
    expect(error.fields).toEqual({});
    expect(error.requestId).toBe("req-header");
  });

  it("never surfaces text from a malformed body", () => {
    const error = parseErrorEnvelope(500, { error: { message: "Traceback: secret path" } });
    expect(error.message).not.toContain("Traceback");
  });
});

describe("networkError", () => {
  it("has status 0 and the network_error code", () => {
    const error = networkError();
    expect(error.status).toBe(0);
    expect(error.code).toBe("network_error");
    expect(error.message).toBe(messages["api.error.network"]);
    expect(error.requestId).toBeNull();
  });
});
