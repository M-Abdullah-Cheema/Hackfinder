import { NextResponse } from "next/server";
import { isUpcomingOpportunity } from "@/lib/filters";
import { fetchOpportunitiesFromDb } from "@/lib/supabase";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET() {
  try {
    const rows = await fetchOpportunitiesFromDb({ limit: 500 });
    const cats = Array.from(
      new Set(
        rows
          .filter((r) => isUpcomingOpportunity(r, true))
          .map((r) => r.category)
          .filter(Boolean)
      )
    ).sort();
    return NextResponse.json(cats);
  } catch (err) {
    console.error("[api/opportunities/categories]", err);
    return NextResponse.json([]);
  }
}
