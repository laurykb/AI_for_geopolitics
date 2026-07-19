import type { Metadata } from "next";
import "./globals.css";

import { AuthGate } from "@/components/auth-gate";
import { AuthProvider } from "@/components/auth-provider";
import { SettingsProvider } from "@/components/settings-provider";
import { SiteHeader } from "@/components/site-header";
import { TourProvider } from "@/components/tour";

export const metadata: Metadata = {
  title: "Théâtre des super-intelligences",
  description:
    "Observatoire temps réel : des super-intelligences négocient pour leurs États, " +
    "le monde penche vers l'utopie ou la dystopie.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        {/* Décor spatial (lune + étoiles filantes) — derrière tout le contenu. */}
        <div className="space-backdrop" aria-hidden="true">
          <span className="moon" />
          <span className="shooting-star ss1" />
          <span className="shooting-star ss2" />
          <span className="shooting-star ss3" />
        </div>
        <AuthProvider>
          <SettingsProvider>
          <TourProvider>
            <a
              href="#contenu"
              className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:rounded-md focus:bg-surface-2 focus:px-3 focus:py-2 focus:text-sm"
            >
              Aller au contenu
            </a>
            <SiteHeader />
            <main id="contenu" className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
              <AuthGate>{children}</AuthGate>
            </main>
            <footer className="border-t border-edge py-4">
              <p className="mx-auto max-w-6xl px-6 text-xs text-fg-faint">
                Ceci est une simulation : les scores observent le jeu, ils ne le dirigent pas.
              </p>
            </footer>
          </TourProvider>
          </SettingsProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
