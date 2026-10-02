import { NextRequest, NextResponse } from "next/server";

import {
  adminServerFetch,
  hasAdminSession,
} from "@/lib/admin/server-auth";

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  if (!(await hasAdminSession())) {
    return NextResponse.json({ error: { code: "admin_auth_required", message: "Admin access is required." } }, { status: 401 });
  }
  const { path } = await context.params;
  const body = request.method === "GET" ? undefined : await request.text();
  const upstream = await adminServerFetch(path.join("/"), {
    method: request.method,
    body: body || undefined,
  });
  return new NextResponse(await upstream.arrayBuffer(), {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("Content-Type") ?? "application/json" },
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;

