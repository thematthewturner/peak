// One fetch wrapper: CSRF header, typed errors and 401 handling.
import { useMemo } from "react";
import { ApiError, goToLogin } from "./session";

export type Api = <T = any>( // eslint-disable-line @typescript-eslint/no-explicit-any
  path: string,
  method?: string,
  body?: unknown,
) => Promise<T>;

export function createApi(
  getCsrf: () => string,
  options: { redirectOn401?: boolean } = {},
): Api {
  const redirectOn401 = options.redirectOn401 ?? true;
  return async <T,>(path: string, method = "GET", body?: unknown) => {
    const form = body instanceof FormData;
    const res = await fetch(`/api${path}`, {
      method,
      credentials: "same-origin",
      cache: "no-store",
      headers: {
        ...(method !== "GET" ? { "X-CSRF-Token": getCsrf() } : {}),
        ...(body && !form ? { "Content-Type": "application/json" } : {}),
      },
      body: body ? (form ? (body as FormData) : JSON.stringify(body)) : undefined,
    });
    if (!res.ok) {
      const data = await res
        .json()
        .catch(() => ({ detail: `Request failed (${res.status})` }));
      const message =
        typeof data.detail === "string" ? data.detail : "Check the fields and try again";
      const ref = res.headers.get("X-Request-ID");
      if (res.status === 401 && redirectOn401) goToLogin();
      throw new ApiError(
        res.status >= 500 && ref && !message.includes(ref) ? `${message} (Ref ${ref})` : message,
        res.status,
      );
    }
    return (await res.json().catch(() => ({}))) as T;
  };
}

/** A stable api function plus a setter for the CSRF token learned from /api/me. */
export function useApi(options?: { redirectOn401?: boolean }) {
  return useMemo(() => {
    const state = { csrf: "" };
    return {
      api: createApi(() => state.csrf, options),
      setCsrf: (value: string) => {
        state.csrf = value;
      },
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
