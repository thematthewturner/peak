import type { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Production Caddy routes /api directly. This same-origin forwarding path keeps
// local development and standalone images working with runtime API addresses.
async function forward(request: NextRequest) {
  const origin = process.env.API_INTERNAL_URL || "http://127.0.0.1:8000";
  const target = new URL(
    request.nextUrl.pathname + request.nextUrl.search,
    origin,
  );
  const headers = new Headers(request.headers);
  for (const name of [
    "host",
    "connection",
    "transfer-encoding",
    "content-length",
  ]) {
    headers.delete(name);
  }
  headers.set("accept-encoding", "identity");
  try {
    const init: RequestInit & { duplex?: "half" } = {
      method: request.method,
      headers,
      body: request.body,
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(30_000),
      ...(request.body ? { duplex: "half" } : {}),
    };
    const upstream = await fetch(target, init);
    const responseHeaders = new Headers(upstream.headers);
    for (const name of [
      "connection",
      "transfer-encoding",
      "content-encoding",
      "content-length",
    ]) {
      responseHeaders.delete(name);
    }
    responseHeaders.set("cache-control", "no-store");
    return new Response(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return Response.json(
      {
        detail:
          "The practice service is temporarily unavailable. Your saved work is safe; try again.",
      },
      { status: 502 },
    );
  }
}

export const GET = forward;
export const POST = forward;
