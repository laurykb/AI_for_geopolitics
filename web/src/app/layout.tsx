import type { Metadata } from "next";
import "./globals.css";

import { AuthProvider } from "@/components/auth-provider";
import { SettingsProvider } from "@/components/settings-provider";
import { ShellMain } from "@/components/shell/shell-main";
import { StageProvider } from "@/components/shell/stage-provider";
import { StageShell } from "@/components/shell/stage-shell";
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
        {/* Voile scanlines du kit théâtre (S10) — décoratif, coupé en perf légère. */}
        <div className="thk-scanlines" aria-hidden="true" />
        <AuthProvider>
          <SettingsProvider>
          <StageProvider>
          <TourProvider>
            {/* La scène persistante de la coquille : le globe monté une fois,
                derrière tout le chrome (masqué sur /r/* et /games/*). */}
            <StageShell />
            <a
              href="#contenu"
              className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:rounded-md focus:bg-surface-2 focus:px-3 focus:py-2 focus:text-sm"
            >
              Aller au contenu
            </a>
            <SiteHeader />
            <ShellMain>{children}</ShellMain>
            <footer className="border-t border-edge py-4">
              <p className="mx-auto max-w-6xl px-6 text-xs text-fg-faint">
                Ceci est une simulation : les scores observent le jeu, ils ne le dirigent pas.
              </p>
            </footer>
          </TourProvider>
          </StageProvider>
          </SettingsProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
