/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    // Admin SDK dimuat apa adanya dari node_modules, tidak dibundel webpack;
    // dependensi opsionalnya (mis. @opentelemetry/api) tidak ikut di-resolve saat build.
    serverComponentsExternalPackages: ["firebase-admin"],
  },
};

export default nextConfig;
