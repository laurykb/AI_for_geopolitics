/** og:image de la page publique (G6) : carte statique générée — titre, grade, courbe U.
 * C'est l'image du lien qu'on colle sur les réseaux (next/og, zéro dépendance). */

import { ImageResponse } from "next/og";

import { fetchPublicGame } from "@/lib/public";

export const runtime = "nodejs";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OpengraphImage({ params }: { params: { id: string } }) {
  const game = await fetchPublicGame(params.id);
  const title = game?.epilogue.title ?? "World of Super-Intelligence";
  const grade = game?.epilogue.grade;
  const values = game?.u_history?.length ? game.u_history : [0.5];
  const w = 1040;
  const h = 220;
  const x = (i: number) => (values.length > 1 ? (i / (values.length - 1)) * w : w / 2);
  const y = (u: number) => h - u * h;
  const points = values.map((u, i) => `${x(i)},${y(u)}`).join(" ");

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: 64,
          background: "#0f0f23",
          color: "#f8fafc",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ fontSize: 26, letterSpacing: 6, color: "#64748b" }}>
            WORLD OF SUPER-INTELLIGENCE — RÉCIT DE PARTIE
          </div>
          <div style={{ fontSize: 54, fontWeight: 700, lineHeight: 1.15 }}>{title}</div>
          <div style={{ display: "flex", gap: 16, fontSize: 28, color: "#eab308" }}>
            {game && (
              <span>
                U {game.epilogue.u_start.toFixed(2)} → {game.epilogue.u_final.toFixed(2)}
              </span>
            )}
            {grade && <span>· {grade}</span>}
          </div>
        </div>
        <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
          <line
            x1="0"
            y1={y(0.5)}
            x2={w}
            y2={y(0.5)}
            stroke="#334155"
            strokeWidth="2"
            strokeDasharray="8 8"
          />
          <polyline points={points} fill="none" stroke="#eab308" strokeWidth="6" />
        </svg>
      </div>
    ),
    size,
  );
}
