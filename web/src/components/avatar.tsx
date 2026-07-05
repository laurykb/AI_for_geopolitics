/** Avatar d'intervenant : sigle sur disque teinté (fiable partout, pas d'emoji). */

import { speakerMeta } from "@/lib/countries";

export function SpeakerAvatar({ id, size = 32 }: { id: string; size?: number }) {
  const meta = speakerMeta(id);
  return (
    <span
      aria-hidden
      className="flex shrink-0 items-center justify-center rounded-full font-mono font-semibold"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.34,
        color: meta.hue,
        background: `color-mix(in srgb, ${meta.hue} 14%, transparent)`,
        border: `1px solid color-mix(in srgb, ${meta.hue} 45%, transparent)`,
      }}
    >
      {meta.code}
    </span>
  );
}
