import type { MetadataRoute } from "next";

export const dynamic = "force-static";

// Installable on a phone home screen. No service worker and no offline mode.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Peak",
    short_name: "Peak",
    description: "Find the SAT points you're losing, fix them once, prove it.",
    start_url: "/today/",
    scope: "/",
    display: "standalone",
    background_color: "#FBFCFD",
    theme_color: "#2B69D6",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
