/** Authentification du client WoSI (G11 §1 S0) — pseudo + mot de passe.
 *
 * Deux backends derrière une même interface :
 *  - **Supabase** quand `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY`
 *    sont présents. L'utilisateur ne voit jamais d'email : on en dérive un technique
 *    (`<pseudo>@wosi.local`). La fiche `players` (pseudo, is_admin) porte le compte.
 *  - **offline** (repli local, flag `offline`) quand ces variables manquent : mêmes
 *    gestes, session dans le `localStorage`. Pour le déploiement Supabase, penser à
 *    désactiver la confirmation d'email (les `@wosi.local` ne reçoivent rien).
 */

import type { SupabaseClient } from "@supabase/supabase-js";

export type Player = {
  id: string;
  pseudo: string;
  is_admin: boolean;
  guest?: boolean;
};

export type AuthResult = { ok: true; player: Player } | { ok: false; error: string };

export interface AuthApi {
  readonly offline: boolean;
  getPlayer(): Promise<Player | null>;
  signIn(pseudo: string, password: string): Promise<AuthResult>;
  signUp(pseudo: string, password: string): Promise<AuthResult>;
  continueAsGuest(): Promise<AuthResult>;
  signOut(): Promise<void>;
  /** G14 §3 — l'ancien mot de passe est vérifié avant de poser le nouveau. */
  changePassword(oldPassword: string, newPassword: string): Promise<AuthResult>;
  /** G14 §3 — oubli du compte côté client après la suppression backend
   * (retire le compte local en offline ; simple signOut côté Supabase). */
  forgetAccount(): Promise<void>;
  /** Abonnement aux changements de session ; renvoie une fonction de désabonnement. */
  onChange(cb: (player: Player | null) => void): () => void;
}

// --- fonctions pures (testables sans navigateur) --------------------------------

/** Pseudo → identifiant sûr : minuscules, sans accents, alphanumérique + tirets. */
export function slugify(pseudo: string): string {
  return pseudo
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "") // diacritiques combinants
    .replace(/[^a-z0-9]+/g, "-") // tout le reste → tiret
    .replace(/^-+|-+$/g, ""); // pas de tiret aux bords
}

/** Email technique dérivé du pseudo — jamais montré à l'utilisateur. */
export function emailForPseudo(pseudo: string): string {
  return `${slugify(pseudo)}@wosi.local`;
}

/** Garde de la vue admin (/admin) : true = renvoyer à l'accueil. Renvoie le
 * non-admin ET le visiteur sans session (sinon spinner infini) — jamais pendant
 * le chargement, tant que la session n'est pas connue. */
export function adminDenied(loading: boolean, player: Player | null): boolean {
  return !loading && !(player?.is_admin ?? false);
}

/** Validation partagée des identifiants ; message FR montrable, ou null si valide. */
export function validateCredentials(pseudo: string, password: string): string | null {
  if (slugify(pseudo).length < 3) return "Le pseudo fait au moins 3 caractères (lettres/chiffres).";
  if (password.length < 6) return "Le mot de passe fait au moins 6 caractères.";
  return null;
}

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_ANON = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

/** True si l'auth tourne en repli local (pas de projet Supabase configuré). */
export const IS_OFFLINE = !(SUPABASE_URL && SUPABASE_ANON);

// --- backend offline (localStorage) ---------------------------------------------

// Note : l'id offline est `offline_<slug>` (pas un UUID) — les parties créées en local
// ne sont PAS portables vers Supabase (games.owner_id y est un uuid FK sur auth.users).
type StoredAccount = Player & {
  hash?: number | string;
  salt?: string;
  hash_version?: 2;
};

const LS_ACCOUNTS = "wosi.accounts";
const LS_SESSION = "wosi.session";
// Repli dev : ces pseudos sont admin hors Supabase (pour tester la vue admin en local).
const OFFLINE_ADMINS = new Set(
  (process.env.NEXT_PUBLIC_OFFLINE_ADMINS ?? "admin")
    .split(",")
    .map((p) => slugify(p))
    .filter(Boolean),
);

/** Hash non cryptographique (djb2) — repli local uniquement, pas un secret réseau. */
function cheapHash(s: string): number {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  return h;
}

function randomSalt(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return btoa(String.fromCharCode(...bytes));
}

async function secureHash(password: string, salt: string): Promise<string> {
  const material = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveBits"],
  );
  const bits = await crypto.subtle.deriveBits(
    {
      name: "PBKDF2",
      hash: "SHA-256",
      salt: Uint8Array.from(atob(salt), (character) => character.charCodeAt(0)),
      iterations: 210_000,
    },
    material,
    256,
  );
  return btoa(String.fromCharCode(...new Uint8Array(bits)));
}

async function passwordMatches(account: StoredAccount, password: string): Promise<boolean> {
  if (account.guest || account.hash == null) return false;
  if (typeof account.hash === "number") return account.hash === cheapHash(password);
  if (!account.salt) return false;
  return account.hash === (await secureHash(password, account.salt));
}

async function secureAccount(account: StoredAccount, password: string): Promise<StoredAccount> {
  const salt = randomSalt();
  return {
    ...account,
    salt,
    hash: await secureHash(password, salt),
    hash_version: 2,
  };
}

function readAccounts(): Record<string, StoredAccount> {
  try {
    return JSON.parse(localStorage.getItem(LS_ACCOUNTS) ?? "{}") as Record<string, StoredAccount>;
  } catch {
    return {};
  }
}

function writeAccounts(accounts: Record<string, StoredAccount>): void {
  localStorage.setItem(LS_ACCOUNTS, JSON.stringify(accounts));
}

function stripHash(account: StoredAccount): Player {
  return {
    id: account.id,
    pseudo: account.pseudo,
    is_admin: account.is_admin,
  };
}

class OfflineAuth implements AuthApi {
  readonly offline = true;
  private listeners = new Set<(p: Player | null) => void>();

  private emit(player: Player | null): void {
    for (const cb of this.listeners) cb(player);
  }

  async getPlayer(): Promise<Player | null> {
    if (typeof window === "undefined") return null;
    const id = localStorage.getItem(LS_SESSION);
    if (!id) return null;
    const account = Object.values(readAccounts()).find((a) => a.id === id);
    return account ? stripHash(account) : null;
  }

  async signUp(pseudo: string, password: string): Promise<AuthResult> {
    const err = validateCredentials(pseudo, password);
    if (err) return { ok: false, error: err };
    const key = slugify(pseudo);
    const accounts = readAccounts();
    if (accounts[key]) return { ok: false, error: "Ce pseudo est déjà pris." };
    const account = await secureAccount({
      id: `offline_${key}`,
      pseudo: pseudo.trim(),
      is_admin: OFFLINE_ADMINS.has(key),
    }, password);
    accounts[key] = account;
    writeAccounts(accounts);
    localStorage.setItem(LS_SESSION, account.id);
    const player = stripHash(account);
    this.emit(player);
    return { ok: true, player };
  }

  async signIn(pseudo: string, password: string): Promise<AuthResult> {
    const key = slugify(pseudo);
    let account = readAccounts()[key];
    if (!account || !(await passwordMatches(account, password))) {
      return { ok: false, error: "Pseudo ou mot de passe incorrect." };
    }
    if (typeof account.hash === "number") {
      account = await secureAccount(account, password);
      const accounts = readAccounts();
      accounts[key] = account;
      writeAccounts(accounts);
    }
    localStorage.setItem(LS_SESSION, account.id);
    const player = stripHash(account);
    this.emit(player);
    return { ok: true, player };
  }

  async signOut(): Promise<void> {
    const id = localStorage.getItem(LS_SESSION);
    if (id?.startsWith("guest_")) {
      const accounts = readAccounts();
      const key = Object.keys(accounts).find((candidate) => accounts[candidate].id === id);
      if (key) {
        delete accounts[key];
        writeAccounts(accounts);
      }
    }
    localStorage.removeItem(LS_SESSION);
    this.emit(null);
  }

  async continueAsGuest(): Promise<AuthResult> {
    const suffix = crypto.getRandomValues(new Uint32Array(1))[0].toString(36).slice(-4);
    const pseudo = `Invité-${suffix.toUpperCase()}`;
    const key = `guest-${suffix}-${Date.now().toString(36)}`;
    const account: StoredAccount = {
      id: `guest_${crypto.randomUUID()}`,
      pseudo,
      is_admin: false,
      guest: true,
    };
    const accounts = readAccounts();
    accounts[key] = account;
    writeAccounts(accounts);
    localStorage.setItem(LS_SESSION, account.id);
    const player = stripHash(account);
    this.emit(player);
    return { ok: true, player };
  }

  async changePassword(oldPassword: string, newPassword: string): Promise<AuthResult> {
    if (newPassword.length < 6) {
      return { ok: false, error: "Le mot de passe fait au moins 6 caractères." };
    }
    const id = localStorage.getItem(LS_SESSION);
    const accounts = readAccounts();
    const key = Object.keys(accounts).find((k) => accounts[k].id === id);
    if (!key) return { ok: false, error: "Session expirée — reconnecte-toi." };
    if (!(await passwordMatches(accounts[key], oldPassword))) {
      return { ok: false, error: "Mot de passe actuel incorrect." };
    }
    accounts[key] = await secureAccount(accounts[key], newPassword);
    writeAccounts(accounts);
    return { ok: true, player: stripHash(accounts[key]) };
  }

  async forgetAccount(): Promise<void> {
    const id = localStorage.getItem(LS_SESSION);
    const accounts = readAccounts();
    const key = Object.keys(accounts).find((k) => accounts[k].id === id);
    if (key) {
      delete accounts[key];
      writeAccounts(accounts);
    }
    localStorage.removeItem(LS_SESSION);
    this.emit(null);
  }

  onChange(cb: (player: Player | null) => void): () => void {
    this.listeners.add(cb);
    return () => this.listeners.delete(cb);
  }
}

// --- backend Supabase -----------------------------------------------------------

class SupabaseAuth implements AuthApi {
  readonly offline = false;
  private clientPromise: Promise<SupabaseClient> | null = null;

  private async client(): Promise<SupabaseClient> {
    if (!this.clientPromise) {
      this.clientPromise = import("@supabase/supabase-js").then(({ createClient }) =>
        createClient(SUPABASE_URL!, SUPABASE_ANON!, {
          auth: { persistSession: true, autoRefreshToken: true, storageKey: "wosi-auth" },
        }),
      );
    }
    return this.clientPromise;
  }

  private async playerFromSession(sb: SupabaseClient): Promise<Player | null> {
    const { data } = await sb.auth.getUser();
    const user = data.user;
    if (!user) return null;
    const { data: rows } = await sb
      .from("players")
      .select("id,pseudo,is_admin")
      .eq("id", user.id)
      .limit(1);
    const row = rows?.[0] as Player | undefined;
    // Fiche absente (compte créé hors flux) : repli minimal sur les métadonnées.
    return row
      ? { ...row, guest: (user as { is_anonymous?: boolean }).is_anonymous ?? false }
      : {
        id: user.id,
        pseudo: (user.user_metadata?.pseudo as string) ?? user.email ?? "joueur",
        is_admin: false,
        guest: (user as { is_anonymous?: boolean }).is_anonymous ?? false,
      };
  }

  async getPlayer(): Promise<Player | null> {
    const sb = await this.client();
    return this.playerFromSession(sb);
  }

  async signUp(pseudo: string, password: string): Promise<AuthResult> {
    const err = validateCredentials(pseudo, password);
    if (err) return { ok: false, error: err };
    const sb = await this.client();
    const { data, error } = await sb.auth.signUp({
      email: emailForPseudo(pseudo),
      password,
      options: { data: { pseudo: pseudo.trim() } },
    });
    if (error) return { ok: false, error: friendly(error.message) };
    const user = data.user;
    if (!user) return { ok: false, error: "Compte créé — connectez-vous." };
    const player: Player = { id: user.id, pseudo: pseudo.trim(), is_admin: false };
    // La fiche joueur : le client n'écrit QUE id + pseudo — is_admin prend son défaut DB
    // (false) et reste réservé au service_role (cf. supabase/schema.sql, sinon
    // auto-promotion admin). RLS insert : auth.uid() = id.
    await sb
      .from("players")
      .upsert({ id: user.id, pseudo: pseudo.trim() }, { onConflict: "id" });
    return { ok: true, player };
  }

  async signIn(pseudo: string, password: string): Promise<AuthResult> {
    const sb = await this.client();
    const { error } = await sb.auth.signInWithPassword({
      email: emailForPseudo(pseudo),
      password,
    });
    if (error) return { ok: false, error: friendly(error.message) };
    const player = await this.playerFromSession(sb);
    return player
      ? { ok: true, player }
      : { ok: false, error: "Connexion impossible — réessayez." };
  }

  async continueAsGuest(): Promise<AuthResult> {
    const sb = await this.client();
    const suffix = crypto.getRandomValues(new Uint32Array(1))[0].toString(36).slice(-4);
    const pseudo = `Invité-${suffix.toUpperCase()}`;
    const { data, error } = await sb.auth.signInAnonymously({
      options: { data: { pseudo } },
    });
    if (error || !data.user) {
      return {
        ok: false,
        error: "Le mode invité n'est pas activé sur ce serveur. Crée un compte pour continuer.",
      };
    }
    const player: Player = {
      id: data.user.id,
      pseudo,
      is_admin: false,
      guest: true,
    };
    await sb.from("players").upsert({ id: player.id, pseudo }, { onConflict: "id" });
    return { ok: true, player };
  }

  async signOut(): Promise<void> {
    const sb = await this.client();
    await sb.auth.signOut();
  }

  async changePassword(oldPassword: string, newPassword: string): Promise<AuthResult> {
    if (newPassword.length < 6) {
      return { ok: false, error: "Le mot de passe fait au moins 6 caractères." };
    }
    const sb = await this.client();
    const player = await this.playerFromSession(sb);
    if (!player) return { ok: false, error: "Session expirée — reconnecte-toi." };
    // Vérifie l'ancien mot de passe par une reconnexion silencieuse (Supabase ne
    // propose pas de « verify password » dédié côté client).
    const { error: signErr } = await sb.auth.signInWithPassword({
      email: emailForPseudo(player.pseudo),
      password: oldPassword,
    });
    if (signErr) return { ok: false, error: "Mot de passe actuel incorrect." };
    const { error } = await sb.auth.updateUser({ password: newPassword });
    if (error) return { ok: false, error: friendly(error.message) };
    return { ok: true, player };
  }

  async forgetAccount(): Promise<void> {
    // La suppression de l'utilisateur auth se fait côté backend (service_role) ;
    // ici on ferme simplement la session locale.
    await this.signOut();
  }

  onChange(cb: (player: Player | null) => void): () => void {
    let unsub = () => {};
    void this.client().then((sb) => {
      const { data } = sb.auth.onAuthStateChange(async () => {
        cb(await this.playerFromSession(sb));
      });
      unsub = () => data.subscription.unsubscribe();
    });
    return () => unsub();
  }
}

/** Traduit les messages Supabase courants en FR montrable. */
function friendly(message: string): string {
  const m = message.toLowerCase();
  if (m.includes("invalid login")) return "Pseudo ou mot de passe incorrect.";
  if (m.includes("already registered")) return "Ce pseudo est déjà pris.";
  if (m.includes("email not confirmed")) return "Compte à confirmer (config Supabase).";
  return message;
}

// --- singleton ------------------------------------------------------------------

let instance: AuthApi | null = null;

/** Le client d'auth du process (Supabase si configuré, sinon repli offline). */
export function getAuth(): AuthApi {
  if (!instance) instance = IS_OFFLINE ? new OfflineAuth() : new SupabaseAuth();
  return instance;
}
