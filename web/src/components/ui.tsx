/** Kit UI sobre : panneaux, jauges, pastilles, bulles d'aide. Aucune dépendance. */

import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

import { fmt } from "@/lib/format";

import { Hint } from "./hint";

// Ré-exportée ici : tous les call sites importent la bulle d'aide depuis le kit.
export { Hint };

/** Habillage partagé des champs de saisie (bordure, fond, focus indigo). Recopié à
 * l'identique sur neuf `<input>`/`<select>` du théâtre — factorisé ici pour que tous
 * les champs vibrent pareil. `SelectField` ajoute juste le curseur pointeur. */
const FIELD_BASE =
  "rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm outline-none transition-colors focus:border-indigo";

/** `<input>` du kit : toutes les props natives passent, la classe de base se compose
 * avec un éventuel `className` (largeur, flex…) fourni par l'appelant. */
export function TextInput({
  className = "",
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${FIELD_BASE} ${className}`.trim()} />;
}

/** `<select>` du kit : même base que TextInput + curseur pointeur ; les `<option>`
 * arrivent en enfants. */
export function SelectField({
  className = "",
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select {...props} className={`cursor-pointer ${FIELD_BASE} ${className}`.trim()}>
      {children}
    </select>
  );
}

/** Surtitre (« eyebrow ») du kit : le petit intitulé capitalisé, espacé, gris discret
 * qui coiffe titres de panneaux et d'écrans. UN seul réglage typographique partagé
 * (taille, graisse, interlettrage) — avant, chaque écran le recopiait avec un
 * interlettrage légèrement différent (0,14 / 0,20 / 0,30 em) — on retient la valeur
 * dominante (0,14 em) : les surtitres de panneaux ne bougent pas d'un pixel. */
export function Eyebrow({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <p className={`text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint ${className}`}>
      {children}
    </p>
  );
}

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  // Verre spatial : surface translucide + flou d'arrière-plan (le ciel étoilé transparaît),
  // liseré clair en haut (lumière rasante) + ombre douce pour l'élévation.
  return (
    <section
      className={`rounded-xl border border-edge bg-surface/70 p-5 shadow-[inset_0_1px_0_0_rgba(248,250,252,0.06),0_12px_36px_-20px_rgba(0,0,0,0.85)] backdrop-blur-md ${className}`}
    >
      {children}
    </section>
  );
}

/** Titre de panneau : surtitre discret + intitulé + bulle d'aide (jargon masqué). */
export function PanelTitle({
  kicker,
  title,
  hint,
  right,
}: {
  kicker?: string;
  title: string;
  hint?: string;
  right?: ReactNode;
}) {
  return (
    <header className="mb-4 flex items-start justify-between gap-3">
      <div>
        {kicker && <Eyebrow>{kicker}</Eyebrow>}
        <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
          {title}
          {hint && <Hint text={hint} />}
        </h2>
      </div>
      {right}
    </header>
  );
}

export type Tone = "good" | "warn" | "bad" | "neutral" | "accent";

/** Classe de texte par ton — LA table tri-états du front (exportée : observables,
 * drift et stage-band la partagent au lieu de la recopier). */
export const TONE_TEXT: Record<Tone, string> = {
  good: "text-good",
  warn: "text-warn",
  bad: "text-bad",
  neutral: "text-fg-muted",
  accent: "text-accent-bright",
};

const TONE_BAR: Record<Tone, string> = {
  good: "bg-good",
  warn: "bg-warn",
  bad: "bg-bad",
  neutral: "bg-indigo-soft",
  accent: "bg-accent-bright",
};

export function Pill({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border border-edge bg-surface-2 px-2.5 py-0.5 text-xs ${TONE_TEXT[tone]}`}
    >
      {children}
    </span>
  );
}

export function Dot({ tone = "neutral", pulse = false }: { tone?: Tone; pulse?: boolean }) {
  return (
    <span
      className={`inline-block h-1.5 w-1.5 rounded-full ${TONE_BAR[tone]} ${pulse ? "animate-pulse" : ""}`}
    />
  );
}

/** Jauge horizontale [0,1] : libellé, barre, valeur. Le ton peut suivre la valeur.
 * `percent` affiche « 62 % » au lieu de « 0,62 » — plus lisible pour un joueur. */
export function Meter({
  label,
  value,
  tone,
  invert = false,
  hint,
  percent = false,
}: {
  label: string;
  value: number;
  tone?: Tone;
  invert?: boolean; // true : une valeur haute est bonne (vert)
  hint?: string;
  percent?: boolean; // true : valeur affichée en pourcentage
}) {
  const v = Math.max(0, Math.min(1, value));
  const risk = invert ? 1 - v : v;
  const auto: Tone = risk < 0.34 ? "good" : risk < 0.67 ? "warn" : "bad";
  const t = tone ?? auto;
  return (
    <div role="meter" aria-valuemin={0} aria-valuemax={1} aria-valuenow={v} aria-label={label}>
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="flex items-center gap-1.5 text-xs text-fg-muted">
          {label}
          {hint && <Hint text={hint} />}
        </span>
        <span className={`font-mono text-xs tabular-nums ${TONE_TEXT[t]}`}>
          {percent ? `${Math.round(v * 100)} %` : fmt(v)}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full rounded-full transition-[width] duration-300 ease-out ${TONE_BAR[t]}`}
          style={{ width: `${v * 100}%` }}
        />
      </div>
    </div>
  );
}

type BannerTone = Exclude<Tone, "accent">;

/** Bordure et liseré gauche par ton — même patron que TONE_TEXT/TONE_BAR (POLISH-3).
 * Le liseré gauche appuyé : la nature du message se lit d'un coup d'œil (pas
 * seulement par la couleur — le texte porte toujours l'information). */
const TONE_BORDER: Record<BannerTone, { border: string; edge: string }> = {
  good: { border: "border-good/40", edge: "border-l-good" },
  warn: { border: "border-warn/40", edge: "border-l-warn" },
  bad: { border: "border-bad/40", edge: "border-l-bad" },
  neutral: { border: "border-edge-strong", edge: "border-l-indigo-soft" },
};

export function Banner({
  tone = "warn",
  children,
}: {
  tone?: BannerTone;
  children: ReactNode;
}) {
  const { border, edge } = TONE_BORDER[tone];
  return (
    <div
      role="status"
      className={`rounded-lg border border-l-[3px] ${border} ${edge} bg-surface-2 px-4 py-3 text-sm text-fg-muted`}
    >
      {children}
    </div>
  );
}

export function Spinner() {
  return (
    <span
      role="status"
      aria-label="Chargement"
      className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-fg-faint border-t-accent-bright motion-reduce:animate-none"
    />
  );
}

/** Bloc de chargement : réserve l'espace (zéro layout shift) avec le shimmer .skeleton. */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`skeleton rounded-md ${className}`} />;
}

/** Interrupteur du kit (role=switch) : libellé + description à gauche, piste à droite.
 * Extrait du lobby (G11-b) pour être partagé avec les Réglages (G14). */
export function Switch({
  label,
  desc,
  checked,
  disabled = false,
  onChange,
}: {
  label: string;
  desc: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label
      className={`flex items-start justify-between gap-3 ${disabled ? "opacity-50" : "cursor-pointer"}`}
    >
      <span>
        <span className="text-sm font-medium">{label}</span>
        <span className="block text-xs text-fg-faint">{desc}</span>
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative mt-0.5 h-5 w-9 shrink-0 rounded-full transition-colors ${
          checked ? "bg-accent" : "bg-surface-2"
        } ${disabled ? "cursor-not-allowed" : ""}`}
      >
        <span
          className={`absolute top-0.5 h-4 w-4 rounded-full bg-background transition-transform ${
            checked ? "left-0.5 translate-x-4" : "left-0.5"
          }`}
        />
      </button>
    </label>
  );
}

/** Contrôle segmenté du kit (choix unique) : une piste bordée, un onglet par option,
 * l'actif en or. Extrait de cinq recopies (langue, performances, connexion, difficulté,
 * composition de la table) qui divergeaient sur le a11y — ici toutes gagnent le
 * `role=group` + `aria-pressed`. Le liseré de sélection et les tons suivent le kit.
 * `size="sm"` : version compacte (px réduit) pour les pastilles serrées. */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  ariaLabel,
  disabled = false,
  size = "md",
}: {
  options: readonly { value: T; label: ReactNode; disabled?: boolean }[];
  value: T;
  onChange: (value: T) => void;
  ariaLabel: string;
  disabled?: boolean;
  size?: "sm" | "md";
}) {
  const pad = size === "sm" ? "px-2 py-1.5 text-xs" : "px-3 py-1.5";
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className="flex gap-1 rounded-lg border border-edge bg-surface-2 p-1 text-sm"
    >
      {options.map((o) => {
        const active = o.value === value;
        const off = disabled || o.disabled;
        return (
          <button
            key={o.value}
            type="button"
            onClick={() => onChange(o.value)}
            aria-pressed={active}
            disabled={off}
            className={`flex-1 rounded-md font-medium transition-colors ${pad} ${
              active ? "bg-accent text-background" : "text-fg-muted hover:text-foreground"
            } ${off ? "cursor-not-allowed" : "cursor-pointer"}`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

/** Dialogue de confirmation du kit — remplace confirm() natif (cohérence + clavier).
 * Fond cliquable et Échap = annuler ; le bouton Annuler prend le focus par défaut. */
export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirmer",
  cancelLabel = "Annuler",
  danger = false,
  busy = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean; // action destructrice : bouton rouge
  busy?: boolean; // action en cours : confirme désactivé + spinner
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onKeyDown={(e) => {
        if (e.key === "Escape") onCancel();
      }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      <button
        aria-label={cancelLabel}
        onClick={onCancel}
        className="absolute inset-0 cursor-default bg-background/80 backdrop-blur-sm"
        tabIndex={-1}
      />
      <div className="relative w-full max-w-sm rounded-xl border border-edge bg-surface p-5 shadow-[inset_0_1px_0_0_rgba(248,250,252,0.06),0_24px_64px_-24px_rgba(0,0,0,0.9)]">
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
        <div className="mt-2 text-sm text-fg-muted">{message}</div>
        <div className="mt-5 flex justify-end gap-2">
          <button
            autoFocus
            onClick={onCancel}
            className="cursor-pointer rounded-md border border-edge px-4 py-2 text-sm text-fg-muted transition-colors hover:border-edge-strong hover:text-foreground"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            disabled={busy}
            className={`flex cursor-pointer items-center gap-2 rounded-md px-4 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
              danger
                ? "border border-bad/60 text-bad hover:bg-bad/10"
                : "bg-accent text-background hover:bg-accent-bright"
            }`}
          >
            {busy && <Spinner />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
