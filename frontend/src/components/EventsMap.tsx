"use client";

import { useEffect, useRef } from "react";
import type { Opportunity } from "@/types/opportunity";

type Props = {
  opportunities: Opportunity[];
  center?: { lat: number; lng: number } | null;
  radiusKm?: number;
};

export default function EventsMap({
  opportunities,
  center,
  radiusKm = 50,
}: Props) {
  const mapRef = useRef<HTMLDivElement | null>(null);
  const mapInstance = useRef<{ remove: () => void } | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      if (!mapRef.current) return;

      try {
        const leafletMod = await import("leaflet");
        const L = (leafletMod.default ?? leafletMod) as typeof import("leaflet");

        if (cancelled || !mapRef.current) return;

        if (mapInstance.current) {
          mapInstance.current.remove();
          mapInstance.current = null;
        }

        const withCoords = opportunities.filter(
          (o) => o.latitude != null && o.longitude != null
        );

        const start =
          center ??
          (withCoords.length
            ? { lat: withCoords[0].latitude!, lng: withCoords[0].longitude! }
            : { lat: 33.6844, lng: 73.0479 });

        const map = L.map(mapRef.current).setView([start.lat, start.lng], 11);
        mapInstance.current = map;

        // Esri World Street Map — English labels worldwide (OSM shows Urdu in PK)
        L.tileLayer(
          "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
          {
            attribution:
              "Tiles &copy; Esri &mdash; Source: Esri, OpenStreetMap",
            maxZoom: 19,
          }
        ).addTo(map);

        const icon = L.icon({
          iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
          iconRetinaUrl:
            "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
          shadowUrl:
            "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
          iconSize: [25, 41],
          iconAnchor: [12, 41],
          popupAnchor: [1, -34],
          shadowSize: [41, 41],
        });

        if (center) {
          L.circle([center.lat, center.lng], {
            radius: radiusKm * 1000,
            color: "#1a1a4e",
            weight: 2,
            fillColor: "#5BB8FF",
            fillOpacity: 0.15,
          }).addTo(map);
          L.marker([center.lat, center.lng], { icon })
            .addTo(map)
            .bindPopup("You are here");
        }

        for (const opp of withCoords) {
          const marker = L.marker([opp.latitude!, opp.longitude!], {
            icon,
          }).addTo(map);
          const place = [opp.city, opp.country].filter(Boolean).join(", ");
          marker.bindPopup(
            `<strong>${opp.title}</strong><br/>${opp.organization_name}${
              place ? `<br/>${place}` : ""
            }`
          );
        }

        if (withCoords.length > 1 && !center) {
          const bounds = L.latLngBounds(
            withCoords.map(
              (o) => [o.latitude!, o.longitude!] as [number, number]
            )
          );
          map.fitBounds(bounds.pad(0.2));
        }
      } catch (err) {
        console.error("Map failed to load:", err);
      }
    }

    boot();
    return () => {
      cancelled = true;
      if (mapInstance.current) {
        mapInstance.current.remove();
        mapInstance.current = null;
      }
    };
  }, [opportunities, center, radiusKm]);

  const mapped = opportunities.filter(
    (o) => o.latitude != null && o.longitude != null
  ).length;

  return (
    <div className="retro-window overflow-hidden">
      <div className="retro-titlebar px-4 py-2 flex items-center justify-between font-mono-label text-xs">
        <span>MAP.EXE — {mapped} PINNED</span>
        <div className="flex gap-1">
          <span className="w-3 h-3 border-2 border-white" />
          <span className="w-3 h-3 border-2 border-white" />
          <span className="w-3 h-3 border-2 border-white bg-white" />
        </div>
      </div>
      <div ref={mapRef} className="h-[360px] w-full bg-[#dce8f5]" />
    </div>
  );
}
