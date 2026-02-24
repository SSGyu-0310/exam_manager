import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  compress: true,
  poweredByHeader: false,
  async redirects() {
    return [
      {
        source: "/learn",
        destination: "/learn/practice",
        permanent: false,
      },
      {
        source: "/review",
        destination: "/review/notes",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
