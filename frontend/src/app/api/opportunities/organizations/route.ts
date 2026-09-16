import { NextResponse } from "next/server";
import { isUpcomingOpportunity } from "@/lib/filters";
import { fetchOpportunitiesFromDb } from "@/lib/supabase";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET() {
  try {
    const rows = await fetchOpportunitiesFromDb({ limit: 500 });
    const orgs = Array.from(
      new Set(
        rows
          .filter((r) => isUpcomingOpportunity(r, true))
          .map((r) => r.organization_name)
          .filter(Boolean)
      )
    ).sort();
    return NextResponse.json(orgs);
  } catch (err) {
    console.error("[api/opportunities/organizations]", err);
    return NextResponse.json([]);
  }
}
