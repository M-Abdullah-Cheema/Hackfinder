"use client";

import dynamic from "next/dynamic";
import { useEffect, useState, useCallback } from "react";
import { Opportunity } from "@/types/opportunity";
import { fetchOpportunities, fetchCategories, fetchOrganizations } from "@/lib/api";

const EventsMap = dynamic(() => import("@/components/EventsMap"), {
  ssr: false,
  loading: () => (
    <div className="retro-window h-[360px] animate-pulse bg-[#dce8f5]" />
  ),
});

const CATEGORY_COLORS: Record<string, { bg: string; side: string; label: string; key: string }> = {
  Hackathon: { bg: "bg-[#FFE566]", side: "bg-[#E6C200]", label: "Hackathon", key: "H" },
  Workshop: { bg: "bg-[#5BB8FF]", side: "bg-[#2E8FD9]", label: "Workshop", key: "W" },
  Internship: { bg: "bg-[#FF7EB3]", side: "bg-[#E0558F]", label: "Internship", key: "I" },
  Job: { bg: "bg-[#B8F55A]", side: "bg-[#8FCC2E]", label: "Job", key: "J" },
  Scholarship: { bg: "bg-[#FFB347]", side: "bg-[#E68A20]", label: "Scholarship", key: "S" },
  Other: { bg: "bg-[#D4D4D4]", side: "bg-[#A8A8A8]", label: "Other", key: "?" },
};

function getCategoryStyle(cat: string) {
  return CATEGORY_COLORS[cat] ?? CATEGORY_COLORS.Other;
}

const HERO_KEYS = [
  { char: "H", bg: "bg-[#FF6B5B]", side: "bg-[#D94435]" },
  { char: "A", bg: "bg-[#5BB8FF]", side: "bg-[#2E8FD9]" },
  { char: "C", bg: "bg-[#5BB8FF]", side: "bg-[#2E8FD9]" },
  { char: "K", bg: "bg-[#B8F55A]", side: "bg-[#8FCC2E]" },
];

function Keycap({
  char,
  bg,
  side,
  size = "md",
}: {
  char: string;
  bg: string;
  side: string;
  size?: "sm" | "md" | "lg";
}) {
  const sizes = {
    sm: "w-10 h-10 text-lg",
    md: "w-14 h-14 text-2xl",
    lg: "w-20 h-20 text-4xl",
  };

  return (
    <div className={`relative ${sizes[size]} shrink-0`}>
      <div className={`absolute inset-x-0 bottom-0 h-2 ${side} rounded-b-md`} />
      <div
        className={`${bg} ${sizes[size]} neo-border rounded-lg font-display font-black flex items-center justify-center relative z-10`}
        style={{ boxShadow: "0 5px 0 #000, 5px 5px 0 #000" }}
      >
        {char}
      </div>
    </div>
  );
}

function formatEventWhen(opp: Opportunity): string | null {
  if (!opp.start_datetime_utc) return null;
  try {
    const dt = new Date(opp.start_datetime_utc);
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(dt);
  } catch {
    return null;
  }
}

function isUpcomingOpportunity(opp: Opportunity): boolean {
  const now = Date.now();
  const startOfToday = new Date();
  startOfToday.setUTCHours(0, 0, 0, 0);
  const start = opp.start_datetime_utc
    ? new Date(opp.start_datetime_utc).getTime()
    : null;
  const end = opp.end_datetime_utc
    ? new Date(opp.end_datetime_utc).getTime()
    : null;
  if (end != null && !Number.isNaN(end) && end >= now) return true;
  if (start != null && !Number.isNaN(start) && start >= startOfToday.getTime())
    return true;
  if (start != null && end == null && start < startOfToday.getTime()) return false;
  if (end != null && end < now) return false;
  if (start == null && end == null) return true;
  return false;
}

function isSeedOpportunity(opp: Opportunity): boolean {
  return (opp.platform_post_id || "").startsWith("ig_seed_");
}

function OpportunityCard({ opp }: { opp: Opportunity }) {
  const style = getCategoryStyle(opp.category);
  const isDemo = isSeedOpportunity(opp);
  const place =
    [opp.city, opp.country].filter(Boolean).join(", ") ||
    (isDemo ? "Islamabad, Pakistan" : "");
  const when = formatEventWhen(opp);

  return (
    <article className="retro-window overflow-hidden flex flex-col group">
      <div className={`${style.bg} grid-panel px-4 py-3 border-b-4 border-black flex items-center justify-between`}>
        <div className="flex items-center gap-3">
          <Keycap char={style.key} bg={style.bg} side={style.side} size="sm" />
          <span className="font-display text-sm uppercase tracking-wider">{style.label}</span>
        </div>
        <div className="flex items-center gap-2">
          {isDemo ? (
            <span className="font-mono-label text-[10px] bg-[#FF6B5B] text-black px-2 py-0.5 border-2 border-black">
              DEMO
            </span>
          ) : (
            <span className="font-mono-label text-[10px] bg-[#B8F55A] text-black px-2 py-0.5 border-2 border-black">
              LIVE
            </span>
          )}
          <span className="font-mono-label text-[10px] bg-black text-white px-2 py-0.5">
            #{opp.id}
          </span>
        </div>
      </div>

      <div className="p-5 flex flex-col gap-4 flex-1 bg-[#fdf8e1] relative">
        <div className="halftone absolute inset-0 pointer-events-none" />

        <h2 className="font-display text-xl uppercase leading-tight tracking-tight line-clamp-3 relative z-10">
          {opp.title}
        </h2>

        <p className="tilt-tag neo-border-2 bg-[#FFE566] font-bold text-xs px-3 py-1 w-fit relative z-10">
          {opp.organization_name}
        </p>

        {(place || when || opp.format || opp.subcategory) && (
          <div className="relative z-10 flex flex-col gap-1 font-mono-label text-[11px] text-gray-700">
            {place ? <span>{place}</span> : null}
            {when ? <span>{when}</span> : null}
            {opp.domain || opp.subcategory ? (
              <span>
                {[opp.domain, opp.subcategory].filter(Boolean).join(" / ")}
              </span>
            ) : null}
            {opp.format ? <span>{opp.format.toUpperCase()}</span> : null}
          </div>
        )}

        <div className="flex-1" />

        {opp.registration_url ? (
          <a
            href={opp.registration_url}
            target="_blank"
            rel="noopener noreferrer"
            className="keycap bg-[#1a1a4e] text-white font-display uppercase text-sm text-center py-3 px-4 relative z-10"
          >
            {opp.registration_url.includes("instagram.com/")
              ? "View post ↗"
              : "Register ↗"}
          </a>
        ) : (
          <span className="neo-border-2 text-center py-3 text-sm font-bold text-gray-500 bg-white/60 font-mono-label relative z-10">
            NO LINK AVAILABLE
          </span>
        )}
      </div>
    </article>
  );
}

function FilterWindow({
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
  hideDemo,
  onHideDemoToggle,
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
  hideDemo: boolean;
  onHideDemoToggle: (v: boolean) => void;
}) {
  return (
    <div className="retro-window overflow-hidden">
      <div className="retro-titlebar px-4 py-2 flex items-center justify-between font-mono-label text-xs">
        <span>FILTERS.EXE</span>
        <div className="flex gap-1">
          <span className="w-3 h-3 border-2 border-white" />
          <span className="w-3 h-3 border-2 border-white" />
          <span className="w-3 h-3 border-2 border-white bg-white" />
        </div>
      </div>

      <div className="p-5 flex flex-col gap-5 bg-[#fdf8e1]">
        <div className="neo-border-2 bg-white p-3 font-mono-label text-xs">
          <span className="text-gray-500">STATUS:</span> SHOWING{" "}
          <span className="font-bold text-[#1a1a4e]">{count}</span> RESULT
          {count !== 1 ? "S" : ""}
        </div>

        <div className="flex flex-col gap-2">
          <label className="font-display text-xs uppercase tracking-widest">Category</label>
          <select
            value={selectedCategory}
            onChange={(e) => onCategoryChange(e.target.value)}
            className="neo-border neo-shadow-sm bg-[#5BB8FF] font-bold text-sm p-3 focus:outline-none cursor-pointer"
          >
            <option value="">ALL CATEGORIES</option>
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
            className="neo-border neo-shadow-sm bg-[#B8F55A] font-bold text-sm p-3 focus:outline-none cursor-pointer"
          >
            <option value="">ALL ORGANIZATIONS</option>
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
              checked={hideDemo}
              onChange={(e) => onHideDemoToggle(e.target.checked)}
            />
            Live only (hide DEMO seeds)
          </label>
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
          <label className="font-mono-label text-[10px]">
            RADIUS KM: {radiusKm}
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
          {geoError ? (
            <p className="font-mono-label text-[10px] text-[#D94435]">{geoError}</p>
          ) : null}
        </div>

        <button
          onClick={onReset}
          className="keycap bg-[#FF7EB3] font-display uppercase text-sm py-3 px-4"
        >
          Reset ↺
        </button>
      </div>
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
        const label = cat === "" ? "Overview" : getCategoryStyle(cat).label;
        return (
          <button
            key={cat || "all"}
            onClick={() => onSelect(cat)}
            className={`
              flex-1 min-w-[120px] px-4 py-3 font-display text-xs uppercase tracking-wider
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
        <div key={i} className="retro-window h-64 animate-pulse bg-[#fdf8e1]" />
      ))}
    </div>
  );
}

function EmptyState({ hasFilters, onReset }: { hasFilters: boolean; onReset: () => void }) {
  return (
    <div className="retro-window p-12 text-center bg-[#FFE566] relative overflow-hidden">
      <div className="halftone absolute inset-0" />
      <div className="flex justify-center gap-2 mb-6 relative z-10">
        <Keycap char="?" bg="bg-white" side="bg-gray-300" size="lg" />
      </div>
      <p className="font-display text-2xl uppercase relative z-10">
        {hasFilters ? "No matches found" : "Queue empty"}
      </p>
      <p className="font-mono-label text-sm mt-3 relative z-10">
        {hasFilters ? "Try different filters." : "Run the scraper pipeline to populate."}
      </p>
      {hasFilters && (
        <button
          onClick={onReset}
          className="keycap bg-[#1a1a4e] text-white font-display uppercase px-8 py-3 mt-8 relative z-10"
        >
          Clear filters
        </button>
      )}
    </div>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="retro-window overflow-hidden">
      <div className="bg-[#FF6B5B] border-b-4 border-black px-4 py-2 font-mono-label text-sm font-bold">
        ERROR — CONNECTION FAILED
      </div>
      <div className="p-6 bg-[#fdf8e1]">
        <p className="font-bold">{message}</p>
        <p className="font-mono-label text-xs mt-3 text-gray-600">
          Make sure the API is running on{" "}
          <code className="bg-black text-white px-1">localhost:8002</code>
        </p>
        <button className="neo-border-2 bg-black text-white font-mono-label text-xs px-3 py-1 mt-4">
          OK
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
  const [hideDemo, setHideDemo] = useState(true);

  useEffect(() => {
    fetchCategories().then(setCategories).catch(() => {});
    fetchOrganizations().then(setOrganizations).catch(() => {});
  }, []);

  const locate = useCallback(() => {
    setGeoError(null);
    if (!navigator.geolocation) {
      setGeoError("Geolocation not supported in this browser.");
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
      (err) => {
        setGeoError(err.message || "Could not read location.");
      },
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
      // LIVE scraped posts first; seed/demo last
      const sorted = [...data].sort((a, b) => {
        const aLive = isSeedOpportunity(a) ? 1 : 0;
        const bLive = isSeedOpportunity(b) ? 1 : 0;
        return aLive - bLive || b.id - a.id;
      });
      setOpportunities(sorted);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
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
    setHideDemo(true);
  };

  const visibleOpportunities = (hideDemo
    ? opportunities.filter((o) => !isSeedOpportunity(o))
    : opportunities
  ).filter(isUpcomingOpportunity);

  const hasFilters = Boolean(
    selectedCategory || selectedOrg || nearbyEnabled || hideDemo
  );

  const stats = {
    total: visibleOpportunities.length,
    hackathons: visibleOpportunities.filter((o) => o.category === "Hackathon").length,
    workshops: visibleOpportunities.filter((o) => o.category === "Workshop").length,
    live: opportunities.filter((o) => !isSeedOpportunity(o)).length,
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top status bar — Sui Overflow inspired */}
      <div className="bg-white border-b-4 border-black px-4 py-2 flex items-center justify-between font-mono-label text-xs">
        <span>QUESTHUB v1.0</span>
        <span className="bg-[#1a1a4e] text-white px-3 py-1">
          {stats.live > 0
            ? `<live> ${stats.live} scraped cards </live>`
            : "<demo> no live cards yet — run pipeline </demo>"}
        </span>
      </div>

      {/* Hero — keycap + neo-brutalist */}
      <header className="bg-white border-b-4 border-black">
        <div className="px-6 py-8 lg:py-10 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-8">
          <div className="flex-1">
            <p className="font-mono-label text-xs uppercase tracking-[0.3em] mb-3 text-[#1a1a4e]">
              This is
            </p>
            <h1 className="font-display text-5xl sm:text-6xl lg:text-7xl uppercase leading-[0.9] tracking-tight">
              <span className="text-black">Quest</span>
              <span className="text-[#1a1a4e]">Hub</span>
            </h1>
            <p className="font-bold text-sm mt-4 max-w-lg text-gray-700">
              Live hackathons, workshops &amp; tech quests — scraped from Instagram,
              cleaned by AI, and filtered to what&apos;s still upcoming.
            </p>
          </div>

          <div className="flex items-end gap-2 lg:gap-3">
            {HERO_KEYS.map((k) => (
              <Keycap key={k.char} char={k.char} bg={k.bg} side={k.side} />
            ))}
            <div
              className="w-16 h-20 bg-[#FFE566] neo-border rounded-lg font-display text-3xl flex items-center justify-center"
              style={{ boxShadow: "0 6px 0 #000, 6px 6px 0 #000" }}
            >
              ↵
            </div>
          </div>
        </div>

        <NavTabs
          categories={categories}
          selected={selectedCategory}
          onSelect={setSelectedCategory}
        />
      </header>

      {/* Stats strip — navy timeline section */}
      <section className="bg-[#1a1a4e] text-white border-b-4 border-black grid-panel">
        <div className="px-6 py-5 grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[
            { label: "Live Opportunities", value: stats.total, color: "bg-[#5BB8FF]" },
            { label: "Hackathons", value: stats.hackathons, color: "bg-[#FFE566]" },
            { label: "Workshops", value: stats.workshops, color: "bg-[#B8F55A]" },
          ].map((s) => (
            <div key={s.label} className="neo-border-2 border-white/30 p-4 flex items-center gap-4">
              <span className={`${s.color} neo-border-2 w-10 h-10 flex items-center justify-center font-display text-lg text-black`}>
                {s.value}
              </span>
              <span className="font-mono-label text-xs uppercase tracking-wider">{s.label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Body */}
      <div className="flex flex-1 flex-col lg:flex-row">
        <aside className="lg:w-80 shrink-0 p-6 border-b-4 lg:border-b-0 lg:border-r-4 border-black">
          <FilterWindow
            categories={categories}
            organizations={organizations}
            selectedCategory={selectedCategory}
            selectedOrg={selectedOrg}
            onCategoryChange={setSelectedCategory}
            onOrgChange={setSelectedOrg}
            onReset={handleReset}
            count={visibleOpportunities.length}
            nearbyEnabled={nearbyEnabled}
            radiusKm={radiusKm}
            geoError={geoError}
            onNearbyToggle={(v) => {
              setNearbyEnabled(v);
              if (v && !userLocation) locate();
            }}
            onRadiusChange={setRadiusKm}
            onLocate={locate}
            hideDemo={hideDemo}
            onHideDemoToggle={setHideDemo}
          />

          <div className="retro-window mt-6 overflow-hidden">
            <div className="retro-titlebar px-4 py-2 font-mono-label text-xs">SOURCES</div>
            <div className="p-4 flex flex-wrap gap-2 bg-[#fdf8e1]">
              {[
                "GDG Cloud",
                "Google Devs",
                "AWS NUST",
                "Imagine Art",
                "Change Mech",
                "LabLab.ai",
              ].map((src) => (
                  <span
                    key={src}
                    className="neo-border-2 bg-white text-[10px] font-bold px-2 py-1 uppercase font-mono-label"
                  >
                    {src}
                  </span>
                )
              )}
            </div>
          </div>

          <div className="mt-6 hidden lg:block">
            <div className="flex flex-wrap gap-2">
              {Object.entries(CATEGORY_COLORS).map(([cat, { bg, label }]) => (
                <span
                  key={cat}
                  className={`neo-border-2 ${bg} text-[10px] font-bold px-2 py-1 uppercase`}
                >
                  {label}
                </span>
              ))}
            </div>
          </div>
        </aside>

        <main className="flex-1 p-6">
          {hasFilters && (
            <div className="flex flex-wrap gap-3 mb-6">
              {selectedCategory && (
                <span
                  className={`tilt-tag neo-border neo-shadow-sm ${getCategoryStyle(selectedCategory).bg} px-4 py-2 text-sm font-display uppercase flex items-center gap-2`}
                >
                  {getCategoryStyle(selectedCategory).label}
                  <button onClick={() => setSelectedCategory("")} className="font-black">
                    ✕
                  </button>
                </span>
              )}
              {selectedOrg && (
                <span className="tilt-tag neo-border neo-shadow-sm bg-[#5BB8FF] px-4 py-2 text-sm font-display uppercase flex items-center gap-2">
                  {selectedOrg}
                  <button onClick={() => setSelectedOrg("")} className="font-black">
                    ✕
                  </button>
                </span>
              )}
              {nearbyEnabled && (
                <span className="tilt-tag neo-border neo-shadow-sm bg-[#FFE566] px-4 py-2 text-sm font-display uppercase flex items-center gap-2">
                  Near me · {radiusKm}km
                  <button onClick={() => setNearbyEnabled(false)} className="font-black">
                    ✕
                  </button>
                </span>
              )}
            </div>
          )}

          {error ? (
            <ErrorBanner message={error} />
          ) : loading ? (
            <LoadingGrid />
          ) : visibleOpportunities.length === 0 ? (
            <EmptyState hasFilters={hasFilters} onReset={handleReset} />
          ) : (
            <div className="flex flex-col gap-6">
              <EventsMap
                opportunities={visibleOpportunities}
                center={nearbyEnabled ? userLocation : null}
                radiusKm={radiusKm}
              />
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-6">
                {visibleOpportunities.map((opp) => (
                  <OpportunityCard key={opp.id} opp={opp} />
                ))}
              </div>
            </div>
          )}
        </main>
      </div>

      <footer className="border-t-4 border-black bg-[#1a1a4e] text-white px-6 py-5">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 font-mono-label text-xs">
          <p className="uppercase tracking-widest text-white/70">
            Playwright · OCR · Gemini · pgvector · FastAPI · Next.js
          </p>
          <p className="bg-[#FFE566] text-black neo-border-2 px-3 py-1 font-bold tilt-tag">
            CTRL+REFRESH TO UPDATE
          </p>
        </div>
      </footer>
    </div>
  );
}
