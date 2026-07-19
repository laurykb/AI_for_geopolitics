export type SuspicionLevel = 0 | 1 | 2;

export type SuspectEntry = {
  level: SuspicionLevel;
  note: string;
};

export type SuspectNotebook = Record<string, SuspectEntry>;

export function nextSuspicion(level: SuspicionLevel): SuspicionLevel {
  return ((level + 1) % 3) as SuspicionLevel;
}

export function parseSuspectNotebook(raw: string | null): SuspectNotebook {
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw) as Record<string, Partial<SuspectEntry>>;
    return Object.fromEntries(
      Object.entries(parsed).map(([country, entry]) => [
        country,
        {
          level: entry.level === 1 || entry.level === 2 ? entry.level : 0,
          note: typeof entry.note === "string" ? entry.note.slice(0, 600) : "",
        },
      ]),
    );
  } catch {
    return {};
  }
}

