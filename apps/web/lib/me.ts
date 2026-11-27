"use client";
import { useEffect, useState } from "react";
import { useApi } from "./api";
import type { Me } from "./types";

/** Load the signed-in user (redirecting to sign-in on 401) and prime the CSRF token. */
export function useSession() {
  const { api, setCsrf } = useApi();
  const [me, setMe] = useState<Me | null>(null);
  useEffect(() => {
    api<Me>("/me").then((m) => {
      setCsrf(m.csrf);
      setMe(m);
    }).catch(() => {});
  }, [api, setCsrf]);
  return { api, me };
}
