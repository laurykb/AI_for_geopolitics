import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

import { AuthGate } from "@/components/auth-gate";
import { AuthProvider } from "@/components/auth-provider";
import { SiteHeader } from "@/components/site-header";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const jetbrains = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
});

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
    <html lang="fr" className={`${inter.variable} ${jetbrains.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <AuthProvider>
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
              Simulation observable — les indices mesurent, ils n&apos;influencent pas les
              super-intelligences.
            </p>
          </footer>
        </AuthProvider>
      </body>
    </html>
  );
}
