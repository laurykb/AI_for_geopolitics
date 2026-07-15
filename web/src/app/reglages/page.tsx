"use client";

/** Réglages utilisateur (G14) — trois panneaux : Langue, Confort & performances,
 * Compte. Chaque réglage s'applique immédiatement (classe sur <html>, langue en
 * contexte) et se persiste (localStorage ; profil backend en CC-3). La mascotte G13
 * y prend ses ordres : compagnon on/off, relancer la visite. */

import { useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { useSettings } from "@/components/settings-provider";
import { useTour } from "@/components/tour";
import { Banner, ConfirmDialog, Panel, PanelTitle, Spinner, Switch } from "@/components/ui";
import { deletePlayer, humanizeError } from "@/lib/api";
import { getAuth } from "@/lib/auth";
import type { Lang } from "@/lib/i18n";
import type { Perf } from "@/lib/settings";

const INPUT_CLASS =
  "w-full rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm " +
  "placeholder:text-fg-faint focus:border-accent focus:outline-none";

export default function ReglagesPage() {
  const { settings, setLang, setPerf, setNoAnim, t } = useSettings();
  const { player } = useAuth();
  const { mascotHidden, setMascotVisible, restart } = useTour();

  if (!player) return null; // la garde d'auth gère la redirection

  const LANGS: { value: Lang; label: string }[] = [
    { value: "fr", label: t("reglages.langue-fr") },
    { value: "en", label: t("reglages.langue-en") },
  ];
  const PERFS: { value: Perf; label: string; desc: string }[] = [
    { value: "plein", label: t("reglages.perf-plein"), desc: t("reglages.perf-plein-desc") },
    { value: "confort", label: t("reglages.perf-confort"), desc: t("reglages.perf-confort-desc") },
    { value: "leger", label: t("reglages.perf-leger"), desc: t("reglages.perf-leger-desc") },
  ];

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header>
        <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-fg-faint">
          {t("reglages.kicker")}
        </p>
        <h1 className="text-2xl font-semibold tracking-tight">{t("reglages.titre")}</h1>
      </header>

      {/* --- 1. Langue ------------------------------------------------------------ */}
      <Panel>
        <PanelTitle
          kicker={t("reglages.langue-titre")}
          title={t("reglages.langue-ui")}
          hint={t("reglages.langue-hint")}
        />
        <div className="flex gap-1 rounded-lg border border-edge bg-surface-2 p-1 text-sm">
          {LANGS.map((l) => (
            <button
              key={l.value}
              onClick={() => setLang(l.value)}
              aria-pressed={settings.lang === l.value}
              className={`flex-1 cursor-pointer rounded-md px-3 py-1.5 font-medium transition-colors ${
                settings.lang === l.value
                  ? "bg-accent text-background"
                  : "text-fg-muted hover:text-foreground"
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>
      </Panel>

      {/* --- 2. Confort & performances --------------------------------------------- */}
      <Panel>
        <PanelTitle
          kicker={t("reglages.confort-titre")}
          title={t("reglages.confort-titre")}
          hint={t("reglages.confort-hint")}
        />
        <div className="space-y-4">
          <div>
            <div className="flex gap-1 rounded-lg border border-edge bg-surface-2 p-1 text-sm">
              {PERFS.map((p) => (
                <button
                  key={p.value}
                  onClick={() => setPerf(p.value)}
                  aria-pressed={settings.perf === p.value}
                  className={`flex-1 cursor-pointer rounded-md px-3 py-1.5 font-medium transition-colors ${
                    settings.perf === p.value
                      ? "bg-accent text-background"
                      : "text-fg-muted hover:text-foreground"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <p className="mt-1.5 text-xs text-fg-faint">
              {PERFS.find((p) => p.value === settings.perf)?.desc}
            </p>
          </div>
          <Switch
            label={t("reglages.noanim")}
            desc={t("reglages.noanim-desc")}
            checked={settings.noAnim}
            onChange={setNoAnim}
          />
        </div>

        <div className="mt-5 border-t border-edge pt-4">
          <p className="mb-3 text-sm font-medium">{t("reglages.mascotte-titre")}</p>
          <div className="space-y-4">
            <Switch
              label={t("reglages.mascotte-compagnon")}
              desc={t("reglages.mascotte-compagnon-desc")}
              checked={!mascotHidden}
              onChange={setMascotVisible}
            />
            <button
              onClick={restart}
              className="cursor-pointer rounded-md border border-edge px-3 py-1.5 text-sm text-fg-muted transition-colors hover:border-accent hover:text-accent-bright"
            >
              {t("reglages.mascotte-visite")}
            </button>
          </div>
        </div>
      </Panel>

      {/* --- 3. Compte -------------------------------------------------------------- */}
      <Panel>
        <PanelTitle
          kicker={t("reglages.compte-titre")}
          title={player.pseudo}
          hint={t("reglages.compte-hint")}
        />
        <PasswordForm t={t} />
        <DeleteAccount t={t} pseudo={player.pseudo} playerId={player.id} />
      </Panel>
    </div>
  );
}

/** Changement de mot de passe : ancien + nouveau ×2, via l'API d'auth (jamais de mot
 * de passe dans un state persisté — uniquement le state local du formulaire). */
function PasswordForm({ t }: { t: (key: string) => string }) {
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "good" | "bad"; text: string } | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPw !== confirmPw) {
      setMsg({ tone: "bad", text: t("reglages.mdp-mismatch") });
      return;
    }
    setBusy(true);
    setMsg(null);
    const res = await getAuth().changePassword(oldPw, newPw);
    setBusy(false);
    if (res.ok) {
      setMsg({ tone: "good", text: t("reglages.mdp-succes") });
      setOldPw("");
      setNewPw("");
      setConfirmPw("");
    } else {
      setMsg({ tone: "bad", text: res.error });
    }
  };

  return (
    <form onSubmit={submit} className="space-y-3">
      <p className="text-sm font-medium">{t("reglages.mdp-titre")}</p>
      <input
        type="password"
        value={oldPw}
        onChange={(e) => setOldPw(e.target.value)}
        placeholder={t("reglages.mdp-ancien")}
        autoComplete="current-password"
        required
        className={INPUT_CLASS}
      />
      <div className="grid gap-3 sm:grid-cols-2">
        <input
          type="password"
          value={newPw}
          onChange={(e) => setNewPw(e.target.value)}
          placeholder={t("reglages.mdp-nouveau")}
          autoComplete="new-password"
          required
          className={INPUT_CLASS}
        />
        <input
          type="password"
          value={confirmPw}
          onChange={(e) => setConfirmPw(e.target.value)}
          placeholder={t("reglages.mdp-confirme")}
          autoComplete="new-password"
          required
          className={INPUT_CLASS}
        />
      </div>
      {msg && <Banner tone={msg.tone}>{msg.text}</Banner>}
      <button
        type="submit"
        disabled={busy || !oldPw || !newPw || !confirmPw}
        className="flex cursor-pointer items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-background transition-colors hover:bg-accent-bright disabled:cursor-not-allowed disabled:opacity-50"
      >
        {busy && <Spinner />}
        {t("reglages.mdp-bouton")}
      </button>
    </form>
  );
}

/** Suppression du compte : pseudo à retaper pour armer le bouton, ConfirmDialog du
 * kit, puis DELETE backend → oubli local → déconnexion → retour à l'accueil (/). */
function DeleteAccount({
  t,
  pseudo,
  playerId,
}: {
  t: (key: string) => string;
  pseudo: string;
  playerId: string;
}) {
  const router = useRouter();
  const { signOut } = useAuth();
  const [confirmPseudo, setConfirmPseudo] = useState("");
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const armed = confirmPseudo.trim() === pseudo;

  const doDelete = async () => {
    setBusy(true);
    setError(null);
    try {
      await deletePlayer(playerId); // le backend anonymise/purge (CC-3)
      await getAuth().forgetAccount();
      await signOut();
      router.replace("/");
    } catch (err) {
      setError(humanizeError(err));
      setOpen(false);
      setBusy(false);
    }
  };

  // CC-15c — la zone dangereuse est repliée : on ne montre pas un bouton de
  // suppression à qui vient changer sa langue.
  return (
    <details className="mt-6">
      <summary className="cursor-pointer select-none text-sm font-medium text-bad transition-colors hover:text-bad/80">
        {t("reglages.suppr-titre")}
      </summary>
      <div className="mt-3 space-y-3 rounded-lg border border-bad/40 p-4">
      <p className="text-xs text-fg-muted">{t("reglages.suppr-desc")}</p>
      <input
        value={confirmPseudo}
        onChange={(e) => setConfirmPseudo(e.target.value)}
        placeholder={t("reglages.suppr-pseudo")}
        className={INPUT_CLASS}
      />
      {error && <Banner tone="bad">{error}</Banner>}
      <button
        onClick={() => setOpen(true)}
        disabled={!armed}
        className="cursor-pointer rounded-md border border-bad/60 px-4 py-2 text-sm font-semibold text-bad transition-colors hover:bg-bad/10 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {t("reglages.suppr-bouton")}
      </button>
      <ConfirmDialog
        open={open}
        title={t("reglages.suppr-confirme-titre")}
        message={t("reglages.suppr-confirme-message")}
        confirmLabel={t("reglages.suppr-confirme-bouton")}
        cancelLabel={t("reglages.annuler")}
        danger
        busy={busy}
        onCancel={() => setOpen(false)}
        onConfirm={doDelete}
      />
      </div>
    </details>
  );
}
