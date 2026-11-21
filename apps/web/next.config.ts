import type { NextConfig } from "next";

/**
 * The public site ships as a static export: no server runtime, no API route, no credential.
 *
 * The reason is written in `specs/001-r1-public-replay/spec.md` and in ADR-040. The replay reads
 * published JSON artifacts and nothing else, so the whole site can be a folder of files served by
 * a content delivery network. The live mode of the demo does not change that: the browser talks
 * to the backend on the origin of the backend, and no route of this site holds a credential.
 */
const nextConfig: NextConfig = {
  output: "export",
  // The export has no image optimizer at runtime, so every image is served as it is stored.
  images: {
    unoptimized: true,
  },
  // The site carries no secret and calls no third party, so the strict mode of React is enough.
  reactStrictMode: true,
  poweredByHeader: false,
};

export default nextConfig;
