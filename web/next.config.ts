import type { NextConfig } from "next";

const BACKEND = process.env.SUTRADHAR_BACKEND_URL ?? "http://localhost:8000";

const config: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND}/api/:path*` },
      { source: "/health", destination: `${BACKEND}/health` },
    ];
  },
};

export default config;
