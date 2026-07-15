/** Pastilles des alliances représentées au sommet — ce qui pèse sur le moteur.
 *
 * Adaptées au casting (calcul serveur : `GameDetail.alliances_at_table`). Une pastille
 * pleine = l'accord pèse (solidarité d'engagement / cohésion au communiqué) ; atténuée
 * = forum ou bloc d'affinité, sans effet moteur. L'infobulle détaille membres, effet
 * et source ; cliquer ouvre la source officielle. */

import { speakerMeta } from "@/lib/countries";
import type { AllianceAtTable } from "@/lib/types";

import { useT } from "./settings-provider";

export function AlliancePills({ alliances }: { alliances: AllianceAtTable[] }) {
  const t = useT();
  if (alliances.length === 0) return null;
  // Les accords qui pèsent d'abord, puis les forums sans effet (atténués).
  const ordered = [...alliances].sort(
    (a, b) => Number(Boolean(b.effect)) - Number(Boolean(a.effect)) || a.tag.localeCompare(b.tag),
  );
  return (
    <div
      aria-label={t("alliances.aria")}
      className="mt-2 flex flex-wrap items-center gap-1.5 border-t border-edge pt-2"
    >
      <span className="text-[10px] uppercase tracking-wide text-fg-faint">
        {t("alliances.label")}
      </span>
      {ordered.map((a) => {
        const label = a.name.split(" — ")[0];
        const codes = a.members.map((m) => speakerMeta(m).code).join(" ");
        const hint =
          `${a.members.map((m) => speakerMeta(m).label).join(", ")} — ` +
          (a.effect ?? t("alliances.sans-effet")) +
          (a.url ? ` · ${t("alliances.verifier")}` : "");
        const chip = (
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs transition-colors ${
              a.effect
                ? "border-edge-strong text-foreground hover:border-accent-bright"
                : "border-edge text-fg-faint"
            }`}
          >
            {label}
            <span className="font-mono text-[10px] tabular-nums text-fg-faint">{codes}</span>
          </span>
        );
        return a.url ? (
          <a key={a.tag} href={a.url} target="_blank" rel="noopener noreferrer" title={hint}>
            {chip}
          </a>
        ) : (
          <span key={a.tag} title={hint} className="cursor-help">
            {chip}
          </span>
        );
      })}
    </div>
  );
}
