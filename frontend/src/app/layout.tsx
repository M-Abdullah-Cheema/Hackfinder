import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "QuestHub — Upcoming Tech Opportunities",
  description:
    "QuestHub aggregates upcoming hackathons, workshops, and tech quests from Instagram — scraped, structured by AI, and ready to apply.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link
          rel="stylesheet"
          href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
          crossOrigin=""
        />
      </head>
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
