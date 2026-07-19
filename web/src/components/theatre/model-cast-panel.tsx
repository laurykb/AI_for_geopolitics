import { speakerMeta } from "@/lib/countries";
import type { ModelCastView } from "@/lib/types";

export function ModelCastPanel({ cast }: { cast?: ModelCastView | null }) {
  if (!cast) return null;
  return (
    <details className="mt-2 rounded-md border border-edge bg-surface-2/35 px-3 py-2">
      <summary className="cursor-pointer text-xs font-medium text-fg-muted hover:text-foreground">
        Casting multi-modèle · {cast.models.length} super-intelligences locales
      </summary>
      <div className="mt-2 space-y-2 border-t border-edge pt-2 text-[11px] text-fg-muted">
        <p>
          Game Master : <span className="font-mono text-foreground">{cast.game_master_model}</span> · juge :{" "}
          <span className="font-mono text-foreground">{cast.judge_model}</span>
        </p>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(cast.assignments).map(([country, model]) => (
            <span key={country} className="rounded-full border border-edge px-2 py-0.5">
              {speakerMeta(country).label} · <span className="font-mono">{model}</span>
            </span>
          ))}
        </div>
        <p className="text-fg-faint">
          Versions figées par digest · un seul modèle en mémoire à la fois · partie hors classement
        </p>
      </div>
    </details>
  );
}
