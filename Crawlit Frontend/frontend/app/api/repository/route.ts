import { NextResponse } from "next/server";
import { saveRepo } from "@/lib/repository";

const BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL!;

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);

  const owner = searchParams.get("owner");
  const repo = searchParams.get("repo");

  if (!owner || !repo) {
    return NextResponse.json({ error: "Missing parameters" }, { status: 400 });
  }

  const response = await fetch(`${BASE_URL}/repositories/${owner}/${repo}`, {
    cache: "no-store",
  });

  const payload = await response.json();
  return NextResponse.json(payload, { status: response.status });
}

export async function POST(req: Request) {
  const body = await req.json();

  const { owner, repo } = body;

  saveRepo(owner, repo);

  return NextResponse.json({ success: true });
}
