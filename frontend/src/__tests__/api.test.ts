import { afterEach, describe, expect, it, vi } from "vitest";

import { api, EmergeError, setAuthToken } from "@/lib/api";

describe("api client", () => {
  afterEach(() => {
    setAuthToken(null);
    vi.restoreAllMocks();
  });

  it("attaches Authorization header when token set", () => {
    setAuthToken("t123");
    expect(api.defaults.headers.common.Authorization).toBe("Bearer t123");
  });

  it("clears Authorization header when null passed", () => {
    setAuthToken("t123");
    setAuthToken(null);
    expect(api.defaults.headers.common.Authorization).toBeUndefined();
  });

  it("decodes envelope into EmergeError", async () => {
    const fakeError = {
      response: {
        status: 401,
        data: {
          error_code: "UNAUTHORIZED",
          error_message_en: "Authentication required.",
        },
      },
    };
    const interceptor = api.interceptors.response as unknown as {
      handlers: { rejected: (e: unknown) => unknown }[];
    };
    const handler = interceptor.handlers[0]?.rejected;
    expect(handler).toBeTypeOf("function");
    await expect(handler!(fakeError)).rejects.toBeInstanceOf(EmergeError);
  });
});
