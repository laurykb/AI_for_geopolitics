import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Coquille unique : l'ancien hub /accueil et le hall parallèle /hall sont fondus
  // dans le point d'entrée unique `/` (redirections permanentes pour les favoris).
  async redirects() {
    return [
      { source: "/accueil", destination: "/", permanent: true },
      { source: "/hall", destination: "/", permanent: true },
    ];
  },
};

export default nextConfig;
