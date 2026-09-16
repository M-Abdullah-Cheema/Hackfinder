import { NextRequest, NextResponse } from "next/server";
import { haversineKm, isUpcomingOpportunity } from "@/lib/filters";
import { fetchOpportunitiesFromDb } from "@/lib/supabase";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  try {
    const sp = req.nextUrl.searchParams;
    const upcomingOnly = sp.get("upcoming_only") !== "false";
    const includeUndated = sp.get("include_undated") !== "false";
    const lat = sp.get("lat") ? Number(sp.get("lat")) : null;
    const lng = sp.get("lng") ? Number(sp.get("lng")) : null;
    const radiusKm = sp.get("radius_km") ? Number(sp.get("radius_km")) : 50;
    const limit = Math.min(Number(sp.get("limit") || 200), 500);

    let rows = await fetchOpportunitiesFromDb({
      category: sp.get("category"),
      organization_name: sp.get("organization_name"),
      city: sp.get("city"),
      country: sp.get("country"),
      domain: sp.get("domain"),
      subcategory: sp.get("subcategory"),
      limit,
    });

    if (upcomingOnly) {
      rows = rows.filter((r) => isUpcomingOpportunity(r, includeUndated));
    }

    if (lat != null && lng != null && !Number.isNaN(lat) && !Number.isNaN(lng)) {
      rows = rows.filter((r) => {
        if (r.latitude == null || r.longitude == null) return false;
        return haversineKm(lat, lng, r.latitude, r.longitude) <= radiusKm;
      });
    }

    return NextResponse.json(rows);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    console.error("[api/opportunities]", message);
    return NextResponse.json(
      {
        detail:
          message.includes("Missing SUPABASE")
            ? "Supabase env vars missing on Vercel/local. Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
            : "Database unreachable. Check Supabase credentials / network.",
      },
      { status: 503 }
    );
  }
}
