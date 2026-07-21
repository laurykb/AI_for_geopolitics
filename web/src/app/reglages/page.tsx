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
import {
  Banner,
  ConfirmDialog,
  Eyebrow,
  Panel,
  PanelTitle,
  Segmented,
  Spinner,
  Switch,
} from "@/components/ui";
import { deletePlayer, humanizeError } from "@/lib/api";
import { getAuth } from "@/lib/auth";
import type { Lang } from "@/lib/i18n";
import type { Perf, StageView } from "@/lib/settings";

const INPUT_CLASS =
  "w-full rounded-md border border-edge bg-surface-2 px-3 py-2 text-sm " +
  "placeholder:text-fg-faint focus:border-accent focus:outline-none";

export default function ReglagesPage() {
  const { settings, setLang, setPerf, setNoAnim, setStageView, t } = useSettings();
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
  const STAGE_VIEWS: { value: StageView; label: string; desc: string }[] = [
    { value: "3d", label: t("reglages.vue-3d"), desc: t("reglages.vue-3d-desc") },
    { value: "2d", label: t("reglages.vue-2d"), desc: t("reglages.vue-2d-desc") },
  ];

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header>
        <Eyebrow>{t("reglages.kicker")}</Eyebrow>
        <h1 className="text-2xl font-semibold tracking-tight">{t("reglages.titre")}</h1>
      </header>

      {/* --- 1. Langue ------------------------------------------------------------ */}
      <Panel>
        <PanelTitle
          kicker={t("reglages.langue-titre")}
          title={t("reglages.langue-ui")}
          hint={t("reglages.langue-hint")}
        />
        <Segmented
          options={LANGS}
          value={settings.lang}
          onChange={setLang}
          ariaLabel={t("reglages.langue-ui")}
        />
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
            <Segmented
              options={PERFS}
              value={settings.perf}
              onChange={setPerf}
              ariaLabel={t("reglages.confort-titre")}
            />
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
          {/* Vue du théâtre (spec théâtre-globe §5) : un CHOIX du joueur, persisté
              par appareil — la touche V bascule aussi, en pleine partie. */}
          <div>
            <p className="mb-1.5 text-sm font-medium">{t("reglages.vue-titre")}</p>
            <Segmented
              options={STAGE_VIEWS}
              value={settings.stageView}
              onChange={setStageView}
              ariaLabel={t("reglages.vue-titre")}
            />
            <p className="mt-1.5 text-xs text-fg-faint">
              {STAGE_VIEWS.find((v) => v.value === settings.stageView)?.desc}
            </p>
          </div>
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
        className="thk-cta thk-cut-sm flex items-center gap-2 font-semibold"
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
