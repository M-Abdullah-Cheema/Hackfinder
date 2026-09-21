"use client";

import dynamic from "next/dynamic";
import { useEffect, useState, useCallback } from "react";
import { Opportunity } from "@/types/opportunity";
import { fetchOpportunities, fetchCategories, fetchOrganizations } from "@/lib/api";

const EventsMap = dynamic(() => import("@/components/EventsMap"), {
  ssr: false,
  loading: () => (
    <div className="neo-border h-[360px] animate-pulse bg-[#dce8f5]" />
  ),
});

const CATEGORY_COLORS: Record<string, { bg: string; side: string; label: string }> = {
  Hackathon: { bg: "bg-[#FFE566]", side: "bg-[#E6C200]", label: "Hackathon" },
  Workshop: { bg: "bg-[#5BB8FF]", side: "bg-[#2E8FD9]", label: "Workshop" },
  Internship: { bg: "bg-[#FF7EB3]", side: "bg-[#E0558F]", label: "Internship" },
  Job: { bg: "bg-[#B8F55A]", side: "bg-[#8FCC2E]", label: "Job" },
  Scholarship: { bg: "bg-[#FFB347]", side: "bg-[#E68A20]", label: "Scholarship" },
  Other: { bg: "bg-[#D4D4D4]", side: "bg-[#A8A8A8]", label: "Other" },
};

function getCategoryStyle(cat: string) {
  return CATEGORY_COLORS[cat] ?? CATEGORY_COLORS.Other;
}

function formatEventWhen(opp: Opportunity): string | null {
  if (!opp.start_datetime_utc) return null;
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(opp.start_datetime_utc));
  } catch {
    return null;
  }
}

function isSeedOpportunity(opp: Opportunity): boolean {
  return (opp.platform_post_id || "").startsWith("ig_seed_");
}

function OpportunityCard({ opp }: { opp: Opportunity }) {
  const style = getCategoryStyle(opp.category);
  const place = [opp.city, opp.country].filter(Boolean).join(", ");
  const when = formatEventWhen(opp);
  const ctaLabel = opp.registration_url?.includes("instagram.com/")
    ? "View post"
    : "Register";

  return (
    <article className="neo-border neo-shadow bg-white flex flex-col overflow-hidden">
      <div
        className={`${style.bg} px-4 py-3 border-b-4 border-black flex items-center justify-between`}
      >
        <span className="font-display text-sm uppercase tracking-wider">
          {style.label}
        </span>
        {opp.format ? (
          <span className="text-[10px] font-bold uppercase tracking-wide bg-black text-white px-2 py-0.5">
            {opp.format}
          </span>
        ) : null}
      </div>

      <div className="p-5 flex flex-col gap-3 flex-1 bg-[#fdf8e1]">
        <h2 className="font-display text-xl uppercase leading-tight tracking-tight line-clamp-3">
          {opp.title}
        </h2>
        <p className="font-bold text-sm">{opp.organization_name}</p>

        {(place || when || opp.subcategory) && (
          <div className="flex flex-col gap-1 text-xs text-gray-700">
            {place ? <span>{place}</span> : null}
            {when ? <span>{when}</span> : null}
            {opp.subcategory ? <span>{opp.subcategory}</span> : null}
          </div>
        )}

        <div className="flex-1" />

        {opp.registration_url ? (
          <a
            href={opp.registration_url}
            target="_blank"
            rel="noopener noreferrer"
            className="keycap bg-[#1a1a4e] text-white font-display uppercase text-sm text-center py-3 px-4"
          >
            {ctaLabel} ↗
          </a>
        ) : (
          <span className="neo-border-2 text-center py-3 text-sm font-bold text-gray-500 bg-white/70">
            Link coming soon
          </span>
        )}
      </div>
    </article>
  );
}

function Filters({
  categories,
  organizations,
  selectedCategory,
  selectedOrg,
  onCategoryChange,
  onOrgChange,
  onReset,
  count,
  nearbyEnabled,
  radiusKm,
  geoError,
  onNearbyToggle,
  onRadiusChange,
  onLocate,
}: {
  categories: string[];
  organizations: string[];
  selectedCategory: string;
  selectedOrg: string;
  onCategoryChange: (v: string) => void;
  onOrgChange: (v: string) => void;
  onReset: () => void;
  count: number;
  nearbyEnabled: boolean;
  radiusKm: number;
  geoError: string | null;
  onNearbyToggle: (v: boolean) => void;
  onRadiusChange: (v: number) => void;
  onLocate: () => void;
}) {
  return (
    <div className="neo-border neo-shadow bg-[#fdf8e1] p-5 flex flex-col gap-5">
      <div>
        <h2 className="font-display text-lg uppercase tracking-wide">Filters</h2>
        <p className="text-xs text-gray-600 mt-1">{count} opportunities</p>
      </div>

      <div className="flex flex-col gap-2">
        <label className="font-display text-xs uppercase tracking-widest">Category</label>
        <select
          value={selectedCategory}
          onChange={(e) => onCategoryChange(e.target.value)}
          className="neo-border bg-[#5BB8FF] font-bold text-sm p-3 focus:outline-none cursor-pointer"
        >
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {getCategoryStyle(c).label}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-col gap-2">
        <label className="font-display text-xs uppercase tracking-widest">Organization</label>
        <select
          value={selectedOrg}
          onChange={(e) => onOrgChange(e.target.value)}
          className="neo-border bg-[#B8F55A] font-bold text-sm p-3 focus:outline-none cursor-pointer"
        >
          <option value="">All organizations</option>
          {organizations.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      </div>

      <div className="neo-border-2 bg-white p-3 flex flex-col gap-3">
        <label className="font-display text-xs uppercase tracking-widest flex items-center gap-2">
          <input
            type="checkbox"
            checked={nearbyEnabled}
            onChange={(e) => onNearbyToggle(e.target.checked)}
          />
          Near me
        </label>
        <button
          type="button"
          onClick={onLocate}
          className="keycap bg-[#5BB8FF] font-display uppercase text-xs py-2"
        >
          Use my location
        </button>
        <label className="text-[11px]">
          Radius: {radiusKm} km
          <input
            type="range"
            min={5}
            max={200}
            step={5}
            value={radiusKm}
            onChange={(e) => onRadiusChange(Number(e.target.value))}
            className="w-full mt-1"
            disabled={!nearbyEnabled}
          />
        </label>
        {geoError ? <p className="text-[11px] text-[#D94435]">{geoError}</p> : null}
      </div>

      <button
        onClick={onReset}
        className="keycap bg-[#FF7EB3] font-display uppercase text-sm py-3 px-4"
      >
        Reset
      </button>
    </div>
  );
}

function NavTabs({
  categories,
  selected,
  onSelect,
}: {
  categories: string[];
  selected: string;
  onSelect: (v: string) => void;
}) {
  const tabs = ["", ...categories];
  return (
    <nav className="flex flex-wrap border-t-4 border-black">
      {tabs.map((cat) => {
        const isActive = selected === cat;
        const label = cat === "" ? "All" : getCategoryStyle(cat).label;
        return (
          <button
            key={cat || "all"}
            onClick={() => onSelect(cat)}
            className={`
              flex-1 min-w-[100px] px-4 py-3 font-display text-xs uppercase tracking-wider
              border-r-4 border-black last:border-r-0 transition-colors
              ${isActive ? "bg-[#5BB8FF] text-black" : "bg-white hover:bg-[#fdf8e1]"}
            `}
          >
            {label}
          </button>
        );
      })}
    </nav>
  );
}

function LoadingGrid() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-6">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="neo-border h-64 animate-pulse bg-[#fdf8e1]" />
      ))}
    </div>
  );
}

function EmptyState({ hasFilters, onReset }: { hasFilters: boolean; onReset: () => void }) {
  return (
    <div className="neo-border neo-shadow p-12 text-center bg-[#FFE566]">
      <p className="font-display text-2xl uppercase">
        {hasFilters ? "No matches found" : "No upcoming opportunities yet"}
      </p>
      <p className="text-sm mt-3 text-gray-800">
        {hasFilters
          ? "Try clearing filters or choosing another category."
          : "Check back soon — new quests appear after the next update."}
      </p>
      {hasFilters && (
        <button
          onClick={onReset}
          className="keycap bg-[#1a1a4e] text-white font-display uppercase px-8 py-3 mt-8"
        >
          Clear filters
        </button>
      )}
    </div>
  );
}

function ErrorBanner({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="neo-border neo-shadow overflow-hidden">
      <div className="bg-[#FF6B5B] border-b-4 border-black px-4 py-2 font-display text-sm uppercase">
        Could not load opportunities
      </div>
      <div className="p-6 bg-[#fdf8e1] flex flex-col gap-4">
        <p className="font-bold text-sm">{message}</p>
        <button
          onClick={onRetry}
          className="keycap bg-[#1a1a4e] text-white font-display uppercase text-sm py-3 px-4 w-fit"
        >
          Try again
        </button>
      </div>
    </div>
  );
}

export default function HomePage() {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [organizations, setOrganizations] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState("");
  const [selectedOrg, setSelectedOrg] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(
    null
  );
  const [nearbyEnabled, setNearbyEnabled] = useState(false);
  const [radiusKm, setRadiusKm] = useState(50);
  const [geoError, setGeoError] = useState<string | null>(null);

  useEffect(() => {
    fetchCategories().then(setCategories).catch(() => {});
    fetchOrganizations().then(setOrganizations).catch(() => {});
  }, []);

  const locate = useCallback(() => {
    setGeoError(null);
    if (!navigator.geolocation) {
      setGeoError("Geolocation is not supported in this browser.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setUserLocation({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
        });
        setNearbyEnabled(true);
      },
      (err) => setGeoError(err.message || "Could not read location."),
      { enableHighAccuracy: false, timeout: 12000 }
    );
  }, []);

  const loadOpportunities = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchOpportunities({
        category: selectedCategory || undefined,
        organization_name: selectedOrg || undefined,
        lat: nearbyEnabled && userLocation ? userLocation.lat : undefined,
        lng: nearbyEnabled && userLocation ? userLocation.lng : undefined,
        radius_km: nearbyEnabled && userLocation ? radiusKm : undefined,
      });
      const liveOnly = data.filter((o) => !isSeedOpportunity(o));
      liveOnly.sort((a, b) => b.id - a.id);
      setOpportunities(liveOnly);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setOpportunities([]);
    } finally {
      setLoading(false);
    }
  }, [selectedCategory, selectedOrg, nearbyEnabled, userLocation, radiusKm]);

  useEffect(() => {
    loadOpportunities();
  }, [loadOpportunities]);

  const handleReset = () => {
    setSelectedCategory("");
    setSelectedOrg("");
    setNearbyEnabled(false);
    setGeoError(null);
  };

  const hasFilters = Boolean(selectedCategory || selectedOrg || nearbyEnabled);
  const stats = {
    total: opportunities.length,
    hackathons: opportunities.filter((o) => o.category === "Hackathon").length,
    workshops: opportunities.filter((o) => o.category === "Workshop").length,
  };

  return (
    <div className="min-h-screen flex flex-col">
      <div className="bg-white border-b-4 border-black px-4 py-2 flex items-center justify-between text-xs font-bold uppercase tracking-wider">
        <span>QuestHub</span>
        <span className="bg-[#1a1a4e] text-white px-3 py-1">
          {stats.total > 0 ? `${stats.total} upcoming` : "Upcoming quests"}
        </span>
      </div>

      <header className="bg-white border-b-4 border-black">
        <div className="px-6 py-10 lg:py-12">
          <p className="text-xs uppercase tracking-[0.3em] mb-3 text-[#1a1a4e] font-bold">
            Discover
          </p>
          <h1 className="font-display text-5xl sm:text-6xl lg:text-7xl uppercase leading-[0.9] tracking-tight">
            <span className="text-black">Quest</span>
            <span className="text-[#1a1a4e]">Hub</span>
          </h1>
          <p className="font-bold text-sm mt-4 max-w-xl text-gray-700">
            Upcoming hackathons, workshops, and tech opportunities — curated and
            ready to join.
          </p>
        </div>

        <NavTabs
          categories={categories}
          selected={selectedCategory}
          onSelect={setSelectedCategory}
        />
      </header>

      <section className="bg-[#1a1a4e] text-white border-b-4 border-black">
        <div className="px-6 py-5 grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[
            { label: "Upcoming", value: stats.total, color: "bg-[#5BB8FF]" },
            { label: "Hackathons", value: stats.hackathons, color: "bg-[#FFE566]" },
            { label: "Workshops", value: stats.workshops, color: "bg-[#B8F55A]" },
          ].map((s) => (
            <div
              key={s.label}
              className="border-2 border-white/30 p-4 flex items-center gap-4"
            >
              <span
                className={`${s.color} neo-border-2 w-10 h-10 flex items-center justify-center font-display text-lg text-black`}
              >
                {s.value}
              </span>
              <span className="text-xs uppercase tracking-wider font-bold">
                {s.label}
              </span>
            </div>
          ))}
        </div>
      </section>

      <div className="flex flex-1 flex-col lg:flex-row">
        <aside className="lg:w-80 shrink-0 p-6 border-b-4 lg:border-b-0 lg:border-r-4 border-black">
          <Filters
            categories={categories}
            organizations={organizations}
            selectedCategory={selectedCategory}
            selectedOrg={selectedOrg}
            onCategoryChange={setSelectedCategory}
            onOrgChange={setSelectedOrg}
            onReset={handleReset}
            count={opportunities.length}
            nearbyEnabled={nearbyEnabled}
            radiusKm={radiusKm}
            geoError={geoError}
            onNearbyToggle={(v) => {
              setNearbyEnabled(v);
              if (v && !userLocation) locate();
            }}
            onRadiusChange={setRadiusKm}
            onLocate={locate}
          />
        </aside>

        <main className="flex-1 p-6">
          {hasFilters && (
            <div className="flex flex-wrap gap-3 mb-6">
              {selectedCategory && (
                <span
                  className={`neo-border ${getCategoryStyle(selectedCategory).bg} px-4 py-2 text-sm font-display uppercase flex items-center gap-2`}
                >
                  {getCategoryStyle(selectedCategory).label}
                  <button onClick={() => setSelectedCategory("")} className="font-black">
                    ✕
                  </button>
                </span>
              )}
              {selectedOrg && (
                <span className="neo-border bg-[#5BB8FF] px-4 py-2 text-sm font-display uppercase flex items-center gap-2">
                  {selectedOrg}
                  <button onClick={() => setSelectedOrg("")} className="font-black">
                    ✕
                  </button>
                </span>
              )}
              {nearbyEnabled && (
                <span className="neo-border bg-[#FFE566] px-4 py-2 text-sm font-display uppercase flex items-center gap-2">
                  Near me · {radiusKm}km
                  <button onClick={() => setNearbyEnabled(false)} className="font-black">
                    ✕
                  </button>
                </span>
              )}
            </div>
          )}

          {error ? (
            <ErrorBanner message={error} onRetry={loadOpportunities} />
          ) : loading ? (
            <LoadingGrid />
          ) : opportunities.length === 0 ? (
            <EmptyState hasFilters={hasFilters} onReset={handleReset} />
          ) : (
            <div className="flex flex-col gap-6">
              <EventsMap
                opportunities={opportunities}
                center={nearbyEnabled ? userLocation : null}
                radiusKm={radiusKm}
              />
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-6">
                {opportunities.map((opp) => (
                  <OpportunityCard key={opp.id} opp={opp} />
                ))}
              </div>
            </div>
          )}
        </main>
      </div>

      <footer className="border-t-4 border-black bg-[#1a1a4e] text-white px-6 py-5">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
          <p className="uppercase tracking-widest text-white/80 font-bold">
            QuestHub — upcoming tech opportunities
          </p>
          <p className="text-white/60">Updated from live community sources</p>
        </div>
      </footer>
    </div>
  );
}
