import type { NextConfig } from "next";

// Peak runs on her Mac: the UI is exported as static files and served by the local engine on 127.0.0.1.
const config: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  poweredByHeader: false,
};
export default config;
