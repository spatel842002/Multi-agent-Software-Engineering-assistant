import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, authApi, clearTokens, getAccessToken, repositoriesApi, setTokens } from "./api";

describe("api client", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("stores and retrieves tokens from localStorage", () => {
    expect(getAccessToken()).toBeNull();
    setTokens("access-123", "refresh-456");
    expect(getAccessToken()).toBe("access-123");
    clearTokens();
    expect(getAccessToken()).toBeNull();
  });

  it("attaches the bearer token on authenticated requests", async () => {
    setTokens("my-token", "refresh");
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }));

    await repositoriesApi.list();

    const [, options] = fetchMock.mock.calls[0];
    const headers = options.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer my-token");
  });

  it("does not attach a token to the register/login calls", async () => {
    setTokens("should-not-be-sent", "refresh");
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ id: "1", email: "a@b.com", is_active: true }), { status: 201 }),
    );

    await authApi.register("a@b.com", "correct-horse-battery-staple");

    const [, options] = fetchMock.mock.calls[0];
    const headers = options.headers as Headers;
    expect(headers.has("Authorization")).toBe(false);
  });

  it("raises ApiError with the server's detail message on a non-2xx response", async () => {
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Invalid email or password." }), { status: 401 }),
    );

    await expect(authApi.login("a@b.com", "wrong")).rejects.toMatchObject({
      message: "Invalid email or password.",
      status: 401,
    } satisfies Partial<ApiError>);
  });
});
