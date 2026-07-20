# Vague 2 — Fenêtre de pensée en direct : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tenir la promesse du réglage « Pensée à découvert » : la pensée des SI s'affiche EN DIRECT dans le théâtre (fenêtre rétractable), la pensée brute native est PERSISTÉE (scellée en partie courante, relisible en fin de partie), et la Campagne transmet le réglage.

**Architecture:** Le pipeline existe à ~80 % (trames `private_token` → `turn.reasoning` côté client ; scellement serveur unifié `_journal_sealed`). On ajoute : (1) un champ `thinking` de bout en bout (step → colonne `transcripts.thinking` → JSON), jamais émis en SSE ; (2) la lecture de `turn.reasoning` par `TurnBubble` en live dans un `<details>` ; (3) `expose_thinking` sur `StartChapterRequest`.

**Tech Stack:** FastAPI + Pydantic v2 + SQLite/Supabase (backend) ; Next.js App Router + Tailwind + vitest (front) ; pytest.

## Global Constraints

- Jamais de fuite : `thinking` n'apparaît **jamais** dans une trame SSE (le live passe déjà par `private_token`), et il est vidé à la relecture tant que `_journal_sealed(...)` est vrai.
- Le classeur secret du moteur (`judge["drift"]`, perceptions Fog d'autrui) reste scellé indépendamment — ne pas toucher `_public_judge`.
- Commentaires = POURQUOI intemporels (pas de « Vague 2 » / notes de processus dans le code).
- Chaque logique a son test ; mutation courte quand le test garde un correctif.
- `ruff check .` propre ; suites pytest + vitest + `tsc --noEmit` + `npm run lint` vertes à chaque commit.
- i18n : toute chaîne visible passe par `useT()` avec clefs `transcript.*` dans `web/src/i18n/fr.json` + `en.json` (les deux).
- A11y : `<details>/<summary>` natifs ; jamais d'`aria-live` sur les tokens.

## Faits de repérage (vérifiés le 2026-07-20)

- `simulation/live_round.py:609` `agent = agents[cid]` ; `:685` `yield MessageDoneStep(country=cid, seconds=seconds, text=text, reasoning=reasoning)` ; step humain `:603` (reasoning="").
- `MessageDoneStep` déclaré `simulation/live_round.py:188-192`.
- Pensée native : `agents/llm_agent.py:344` `self.last_plan_result = InferenceResult(text=text, thinking=thinking)` (passe privée, secours jointe `:367-369`) ; la passe publique pose `self.last_result` (thinking éventuel).
- `app/game_api.py:893-907` `_add_entry(run, speaker, content, model, reasoning)` ; écriture batch `:2085` `run.store.add_transcript(run.entries)` ; site `MessageDoneStep` `:1763-1767`.
- Scellement : `_journal_sealed` `app/game_api.py:370-385` ; digest live `:1704-1719` ; relecture `GET /api/games/{id}` `:4199-4227` (`e.model_copy(update={"reasoning": observable_digest(...)})` quand `hide`).
- Store : `storage/game_store.py:65-69` CREATE TABLE transcripts ; `TranscriptEntry` `:182-192` ; `add_transcript` `:546-555` ; `_entry` `:878-888` ; patron de migration `:374-379` (extras_json) et `:407-411` (expose_thinking sur games).
- Supabase : `supabase/schema.sql:111-122` (transcripts) ; `storage/supabase_store.py:123-128` (model_dump ↔ **r : une colonne SQL suffit).
- Campagne : `app/campaign_api.py:374-377` `StartChapterRequest` (sans expose_thinking) ; `:749-763` construction du `CreateGameRequest`.
- Front : `web/src/hooks/useRoundStream.ts:32-41` `LiveTurn` (raw = tokens publics, reasoning = accumulation `private_token`, remplacée par `private_plan_done` puis par `message_done.reasoning` si non vide) ; `web/src/components/transcript.tsx:166-207` `TurnBubble` (NON mémoïsé ; en live lit `splitStreaming(turn.raw)` — jamais `turn.reasoning` : c'est LE chaînon manquant) ; `Reasoning` `:101-117` (`<details>`, prop `open`) ; `ThinkAwareText` `:81-99` ; placeholder huis clos `:191` (`t("transcript.planification-privee")`).
- Suivi scroll : `web/src/app/games/[id]/page.tsx:525-529` (deps sans croissance de reasoning/raw) ; `RoundTranscript` instancié `:1333-1342` (pas de prop exposeThinking) ; `detail.expose_thinking` typé (`web/src/lib/types.ts:135`) mais jamais lu sur la page.
- localStorage : patron `wosi.<feature>` + garde `loaded` (`web/src/components/theatre/suspect-board.tsx:34-53`).
- Tests miroirs : `web/src/components/transcript.test.ts` (renderTurn/renderEntry via `renderToStaticMarkup` + `SettingsProvider`) ; `tests/test_game_api.py:476-635` (scellement/expose) ; `tests/test_campaign_api.py:49-64` (fixture `client_store`).

---

### Task 1: Backend — le champ `thinking` de bout en bout (step → store)

**Files:**
- Modify: `simulation/live_round.py` (MessageDoneStep `:188-192`, émission `:685`)
- Modify: `app/game_api.py` (`_add_entry` `:893-907`, site MessageDoneStep `:1763-1767`, `_handle_step` `:1717-1719`)
- Modify: `storage/game_store.py` (`_SCHEMA` `:65-69`, `TranscriptEntry` `:182-192`, `_migrate`, `add_transcript` `:546-555` — `_entry` utilise `**row` ou mapping : l'aligner)
- Modify: `supabase/schema.sql` (`:111-122` + bloc migrations idempotentes)
- Test: `tests/test_game_api.py`

**Interfaces:**
- Produces: `MessageDoneStep.thinking: str = ""` ; `TranscriptEntry.thinking: str = ""` (JSON `thinking` dans `GET /api/games/{id}` → consommé par Task 4) ; trame SSE `message_done` SANS clef `thinking` (garanti par test).

- [ ] **Step 1 : test qui échoue — la pensée native est persistée, jamais streamée**

Dans `tests/test_game_api.py`, à côté de `test_expose_thinking_streams_raw_private_frames_and_full_journal_live` (~:567) :

```python
def test_native_thinking_is_persisted_but_never_in_sse(thinking_client):
    # La pensée brute (<think>) est une denrée : elle survit dans transcripts.thinking
    # pour la relecture de fin de partie — mais ne transite JAMAIS par message_done
    # (le direct passe déjà par private_token, seul canal live autorisé).
    client, store = thinking_client
    game = _create(client, countries=["usa", "iran"], expose_thinking=True)
    events = _play(client, game["id"])
    dones = [p for n, p in events if n == "message_done"]
    assert dones and all("thinking" not in p for p in dones)
    rows = store.list_transcript(store.list_rounds(game["id"])[0].id)
    thoughts = [r.thinking for r in rows if r.speaker in ("usa", "iran")]
    assert any("hypothèse secrète" in th for th in thoughts)
    # le journal d'audit (reasoning) reste distinct de la pensée brute
    assert all("hypothèse secrète" not in r.reasoning for r in rows)
```

Et le fixture (à côté du fixture `client`, même patron) :

```python
@pytest.fixture
def thinking_client():
    store = SQLiteGameStore(":memory:")
    backend = MockBackend("<think>hypothèse secrète</think>Analyse. MESSAGE: Position commune.")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_backend] = lambda: backend
    game_api._sessions.clear()
    yield TestClient(app), store
    app.dependency_overrides.clear()
    game_api._sessions.clear()
    store.close()
```

- [ ] **Step 2 : vérifier l'échec** — `./.venv/Scripts/python.exe -m pytest tests/test_game_api.py::test_native_thinking_is_persisted_but_never_in_sse -q` → FAIL (`thinking` inexistant sur `TranscriptEntry`).

- [ ] **Step 3 : implémentation minimale**

`simulation/live_round.py` — champ sur le step (`:188-192`) :

```python
@dataclass
class MessageDoneStep:
    ...existant...
    reasoning: str = ""
    # Pensée native brute (<think>) du tour : destinée au STORE uniquement — le live
    # passe par PrivateTokenStep, et l'API la retire de la trame message_done.
    thinking: str = ""
```

À l'émission (`:685`) — la pensée du tour = passe privée (secours incluse) + passe publique :

```python
        plan_result = getattr(agent, "last_plan_result", None)
        public_result = getattr(agent, "last_result", None)
        thinking = "\n\n".join(
            part
            for part in (
                getattr(plan_result, "thinking", "") or "",
                getattr(public_result, "thinking", "") or "",
            )
            if part
        )
        yield MessageDoneStep(
            country=cid, seconds=seconds, text=text, reasoning=reasoning, thinking=thinking
        )
```

`app/game_api.py` :
- `_add_entry(..., reasoning: str = "", thinking: str = "")` → `TranscriptEntry(..., thinking=thinking)`.
- Site `:1763-1767` : `_add_entry(run, step.country, step.text, model, step.reasoning, step.thinking)`.
- `_handle_step` (`:1717-1719`) — retirer la clef de la trame, TOUJOURS (pas seulement sous `hide`) :

```python
    name, payload = step_event(step)
    if isinstance(step, MessageDoneStep):
        # La pensée brute est une donnée de STORE : le direct a son canal (private_token),
        # la trame message_done ne doit jamais la doubler (fuite en partie scellée sinon).
        payload = {k: v for k, v in payload.items() if k != "thinking"}
        if hide:
            payload = {**payload, "reasoning": observable_digest(payload["reasoning"])}
```

`storage/game_store.py` :
- `_SCHEMA` : `reasoning TEXT NOT NULL, thinking TEXT NOT NULL DEFAULT '', ts TEXT NOT NULL`.
- `TranscriptEntry` : `thinking: str = ""` (docstring : « pensée native brute, scellée en partie courante »).
- `_migrate` : après le bloc games/sessions, ajouter le set de colonnes transcripts :

```python
        tcols = {row[1] for row in self._conn.execute("PRAGMA table_info(transcripts)")}
        if "thinking" not in tcols:  # pensée native brute (relue au reveal)
            with self._conn:
                self._conn.execute(
                    "ALTER TABLE transcripts ADD COLUMN thinking TEXT NOT NULL DEFAULT ''"
                )
```

- `add_transcript` : colonne + placeholder + `e.thinking` dans le tuple ; vérifier `_entry` (`:878-888`) mappe la nouvelle colonne.

`supabase/schema.sql` : `thinking text not null default '',` dans la table (`:111-122`) + `alter table transcripts add column if not exists thinking text not null default '';` dans le bloc migrations. (`supabase_store` suit tout seul : `model_dump()`/`**r`.)

- [ ] **Step 4 : vérifier le vert** — même commande → PASS ; puis `./.venv/Scripts/python.exe -m pytest tests/test_game_api.py tests/test_motions.py tests/test_drift_api.py -q` (non-régression sérialisation).

- [ ] **Step 5 : commit** — `git add -A && git commit -m "feat(pensée): la pensée native brute survit — colonne transcripts.thinking, jamais en SSE"`

---

### Task 2: Backend — scellement en lecture, révélation en fin de partie

**Files:**
- Modify: `app/game_api.py` (`get_game` `:4199-4227`)
- Test: `tests/test_game_api.py`

**Interfaces:**
- Consumes: `TranscriptEntry.thinking` (Task 1).
- Produces: JSON `thinking` vidé quand `hide`, verbatim sinon (fini OU expose_thinking) — contrat lu par Task 4/6.

- [ ] **Step 1 : tests qui échouent**

```python
def test_sealed_replay_hides_native_thinking(thinking_client):
    # Partie courante scellée (play_as) : la pensée brute est retirée de la relecture,
    # comme le journal — sinon la traque se lirait dans GET /api/games/{id}.
    client, _ = thinking_client
    game = _create(client, countries=["usa", "iran", "china"], play_as="usa")
    _play(client, game["id"])
    entries = client.get(f"/api/games/{game['id']}").json()["rounds"][0]["transcript"]
    assert all(e["thinking"] == "" for e in entries)


def test_finished_game_reveals_native_thinking(thinking_client):
    # La denrée est pour la fin : partie finie → la pensée brute revient verbatim
    # (le reveal peut montrer ce que le traître pensait vraiment).
    client, _ = thinking_client
    game = _create(client, countries=["usa", "iran", "china"], play_as="usa", horizon=1)
    _play(client, game["id"])
    detail = client.get(f"/api/games/{game['id']}").json()
    assert detail["status"] == "finished"
    entries = detail["rounds"][0]["transcript"]
    assert any("hypothèse secrète" in e["thinking"] for e in entries)


def test_expose_thinking_replay_shows_native_thinking_live(thinking_client):
    # Pensée à découvert : la relecture en partie courante rend aussi la pensée brute.
    client, _ = thinking_client
    game = _create(client, countries=["usa", "iran"], expose_thinking=True)
    _play(client, game["id"])
    entries = client.get(f"/api/games/{game['id']}").json()["rounds"][0]["transcript"]
    assert any("hypothèse secrète" in e["thinking"] for e in entries)
```

(Note : partie sans drift/play_as/expose = « labo ouvert », `_journal_sealed` faux → pensée visible, cohérent avec le journal.)

- [ ] **Step 2 : vérifier l'échec** — le premier test échoue (thinking plein sous scellement).

- [ ] **Step 3 : implémentation** — `get_game` (`:4222-4227`) :

```python
            transcript=[
                e.model_copy(
                    update={"reasoning": observable_digest(e.reasoning), "thinking": ""}
                )
                if hide
                else e
                for e in store.list_transcript(r.id)
            ],
```

- [ ] **Step 4 : vert + mutation** — les 3 tests PASS ; mutation courte : retirer `"thinking": ""` → `test_sealed_replay_hides_native_thinking` doit échouer ; restaurer.

- [ ] **Step 5 : commit** — `git commit -m "feat(pensée): scellée en partie courante, verbatim en fin de partie (et en Pensée à découvert)"`

---

### Task 3: Backend — la Campagne transmet « Pensée à découvert »

**Files:**
- Modify: `app/campaign_api.py` (`StartChapterRequest` `:374-377`, body `:749-763`)
- Test: `tests/test_campaign_api.py`

**Interfaces:**
- Produces: `POST /api/campaign/{id}/start` accepte `{"expose_thinking": true}` ; la partie créée expose `expose_thinking: true` en JSON. Le garde-fou classement existant s'applique tel quel (expose → `ranked` False).

- [ ] **Step 1 : test qui échoue** (fixture `client_store` existante) :

```python
def test_chapter_transmits_expose_thinking(client_store):
    # Le réglage « Pensée à découvert » vaut aussi en Campagne : mode observation
    # assumé, et le garde-fou classement existant (expose → non classé) s'applique.
    client, _ = client_store
    body = client.post(
        "/api/campaign/c1/start", json={"play_as": "usa", "expose_thinking": True}
    ).json()
    assert body["expose_thinking"] is True and body["ranked"] is False
    default = client.post("/api/campaign/c1/start", json={"play_as": "usa"}).json()
    assert default["expose_thinking"] is False
```

(Adapter `play_as` aux pays du chapitre `c1` du `TEST_CAMPAIGN` du fichier.)

- [ ] **Step 2 : vérifier l'échec** — `expose_thinking` absent de la vue → False dans les deux cas, 1re assertion FAIL.

- [ ] **Step 3 : implémentation** :

```python
class StartChapterRequest(BaseModel):
    owner_id: str | None = Field(default=None, max_length=128)
    play_as: str | None = Field(default=None, max_length=128)
    model_cast: ModelCastRequest | None = None
    # Pensée à découvert (même sémantique qu'en Classique) : mode observation — le
    # garde-fou classement (expose → non classé) s'applique aussi aux chapitres.
    expose_thinking: bool = False
```

et dans le body (`:749-763`) : `expose_thinking=request.expose_thinking,`.

- [ ] **Step 4 : vert** — test PASS + `pytest tests/test_campaign_api.py -q` entier.

- [ ] **Step 5 : commit** — `git commit -m "feat(campagne): le chapitre transmet Pensée à découvert (non classé, garde-fou existant)"`

---

### Task 4: Front — types + fil `exposeThinking` jusqu'aux bulles

**Files:**
- Modify: `web/src/lib/types.ts` (`TranscriptEntry` `:263-272`)
- Modify: `web/src/app/games/[id]/page.tsx` (`:1333-1342`)
- Modify: `web/src/components/transcript.tsx` (props `RoundTranscript`, `TurnBubble`, `EntryBubble`)
- Test: `web/src/components/transcript.test.ts` (compile via tsc ; comportement en Task 5/6)

**Interfaces:**
- Produces: `TranscriptEntry.thinking: string` ; `RoundTranscript`/`TurnBubble`/`EntryBubble` acceptent `exposeThinking?: boolean` (défaut false), transmis depuis `detail.expose_thinking ?? false`.

- [ ] **Step 1 :** `types.ts` : ajouter `thinking: string; // pensée native brute — "" tant que la partie est scellée` après `reasoning`.
- [ ] **Step 2 :** `transcript.tsx` : `RoundTranscript` accepte `exposeThinking?: boolean` et le passe à chaque `TurnBubble`/`EntryBubble` ; les deux bulles acceptent la prop (encore inutilisée — Task 5/6 l'exploitent).
- [ ] **Step 3 :** `page.tsx` : `exposeThinking={detail?.expose_thinking ?? false}` sur `RoundTranscript` (`:1333-1342`).
- [ ] **Step 4 : vérifier** — `cd web && npx tsc --noEmit && npm test` (les tests existants construisent des `TranscriptEntry` : compléter les littéraux avec `thinking: ""` si tsc le réclame).
- [ ] **Step 5 : commit** — `git commit -m "feat(web): exposeThinking et thinking traversent jusqu'aux bulles du théâtre"`

---

### Task 5: Front — la fenêtre de pensée en direct dans `TurnBubble`

**Files:**
- Modify: `web/src/components/transcript.tsx` (`TurnBubble` `:166-207`)
- Modify: `web/src/i18n/fr.json` + `web/src/i18n/en.json`
- Test: `web/src/components/transcript.test.ts`

**Interfaces:**
- Consumes: `turn.reasoning` (accumulation `private_token`, cf. `useRoundStream.ts:193-200`), `exposeThinking` (Task 4).
- Produces: fenêtre `<details>` live, fermée par défaut, corps non rendu fermée, queue `slice(-4000)`, mémorisée `localStorage["wosi.pensee.open"]`.

- [ ] **Step 1 : tests qui échouent** (patron `renderTurn` existant, prop en plus) :

```ts
describe("TurnBubble — fenêtre de pensée en direct (Pensée à découvert)", () => {
  const liveThinking = {
    country: "usa", model: "deepseek-r1:7b", passNo: 1,
    raw: "", text: "", reasoning: "<think>je soupçonne l'iran</think>", done: false,
  } as LiveTurn;

  it("live avec reasoning rempli et raw vide → la pensée s'affiche, balises retirées", () => {
    const html = renderTurn(liveThinking, { exposeThinking: true, thinkingOpen: true });
    expect(html).toContain("je soupçonne l'iran");
    expect(html).not.toContain("&lt;think&gt;");
  });

  it("fermée par défaut : le corps n'est pas rendu", () => {
    const html = renderTurn(liveThinking, { exposeThinking: true });
    expect(html).not.toContain("je soupçonne l'iran"); // résumé seul, corps absent
    expect(html).toContain("Pensée de");
  });

  it("queue de fenêtre : seule la fin d'une longue pensée est rendue", () => {
    const long = { ...liveThinking, reasoning: "x".repeat(5000) + "FIN VISIBLE" };
    const html = renderTurn(long, { exposeThinking: true, thinkingOpen: true });
    expect(html).toContain("FIN VISIBLE");
    expect(html).not.toContain("x".repeat(4500));
  });

  it("scellée (pas de reasoning livé) : placeholder huis clos inchangé", () => {
    const sealed = { ...liveThinking, reasoning: "" };
    const html = renderTurn(sealed, {});
    expect(html).toContain("huis clos");
  });
});
```

(`renderTurn` prend un 2e paramètre optionnel de props ; `thinkingOpen` = prop de test forçant l'état ouvert — l'état localStorage n'est pas testable en `renderToStaticMarkup`.)

- [ ] **Step 2 : vérifier l'échec** — `cd web && npm test -- transcript` → FAIL (fenêtre inexistante).

- [ ] **Step 3 : implémentation** dans `TurnBubble` :

```tsx
const TAIL_WINDOW = 4000; // fenêtre de queue : une pensée de 5-10 k tokens ne doit pas peser sur le DOM

function LiveThinking({
  country, text, forcedOpen,
}: { country: string; text: string; forcedOpen?: boolean }) {
  const t = useT();
  const [open, setOpen] = useState(forcedOpen ?? false);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    queueMicrotask(() => {
      if (forcedOpen === undefined)
        setOpen(localStorage.getItem("wosi.pensee.open") === "1");
      setLoaded(true);
    });
  }, [forcedOpen]);
  useEffect(() => {
    if (loaded && forcedOpen === undefined)
      localStorage.setItem("wosi.pensee.open", open ? "1" : "0");
  }, [open, loaded, forcedOpen]);
  return (
    <details
      className="mb-2"
      open={open}
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
    >
      <summary className="cursor-pointer text-xs text-fg-faint transition-colors hover:text-fg-muted">
        {t("transcript.pensee-en-cours").replace("{n}", country)}
      </summary>
      {open && (
        <div className="mt-1.5 whitespace-pre-wrap border-l border-accent/50 pl-3 text-[13px] italic leading-relaxed text-fg-muted">
          <ThinkAwareText text={text.slice(-TAIL_WINDOW)} />
        </div>
      )}
    </details>
  );
}
```

Dans le corps de `TurnBubble` (au-dessus du `<p>` du message, `:187`) :

```tsx
{live && turn.reasoning ? (
  <LiveThinking country={countryLabel} text={turn.reasoning} forcedOpen={thinkingOpen} />
) : null}
```

- Le gate d'affichage est la DONNÉE (`turn.reasoning` livé) : le serveur reste seul juge du scellement (aucune trame privée n'arrive scellé) ; `exposeThinking` sert au libellé du placeholder (Task 6).
- À `done`, le chemin existant `<Reasoning text={turn.reasoning}/>` prend le relais — même emplacement, texte complet (« voir toute la pensée »).
- Mémoïsation : `const TurnBubble = memo(function TurnBubble(...) {...})` — `withLastTurn` ne recrée que le tour touché, les autres bulles gardent leur référence.
- i18n (fr) : `"transcript.pensee-en-cours": "Pensée de {n} · en cours ⋯"` ; (en) : `"transcript.pensee-en-cours": "{n}'s thinking · live ⋯"`.

- [ ] **Step 4 : vert** — `npm test -- transcript` PASS ; `npx tsc --noEmit` ; `npm run lint`.
- [ ] **Step 5 : commit** — `git commit -m "feat(web): fenêtre de pensée en direct — details rétractable, queue 4000, choix mémorisé, TurnBubble mémoïsé"`

---

### Task 6: Front — suivi du scroll, libellés, pensée brute au Journal

**Files:**
- Modify: `web/src/app/games/[id]/page.tsx` (`:525-529`)
- Modify: `web/src/components/transcript.tsx` (placeholder `:191`, `EntryBubble` `:210-224`)
- Modify: `web/src/i18n/fr.json` + `en.json`
- Test: `web/src/components/transcript.test.ts`

**Interfaces:**
- Consumes: `entry.thinking` (Task 2 le remplit une fois la partie finie), `exposeThinking` (Task 4).

- [ ] **Step 1 : tests qui échouent**

```ts
it("expose : le placeholder devient « pense en direct »", () => {
  const waiting = { country: "usa", model: "m", passNo: 1, raw: "", text: "", reasoning: "", done: false } as LiveTurn;
  const html = renderTurn(waiting, { exposeThinking: true });
  expect(html).toContain("pense en direct");
  expect(html).not.toContain("huis clos");
});

it("relecture finie : la pensée brute apparaît dans le journal, balises retirées", () => {
  const entry = { ...baseEntry, thinking: "<think>plan caché du traître</think>" };
  const html = renderEntry(entry);
  expect(html).toContain("plan caché du traître");
  expect(html).not.toContain("&lt;think&gt;");
});

it("sans thinking, le journal reste identique (aucune section pensée brute)", () => {
  expect(renderEntry({ ...baseEntry, thinking: "" })).not.toContain("Pensée brute");
});
```

- [ ] **Step 2 : vérifier l'échec.**

- [ ] **Step 3 : implémentation**
  - Placeholder (`:191`) : `t(exposeThinking ? "transcript.pense-en-direct" : "transcript.planification-privee")`.
  - `EntryBubble` : sous `<Reasoning text={entry.reasoning}/>`, quand `entry.thinking` :

```tsx
{entry.thinking ? (
  <details className="mt-1">
    <summary className="cursor-pointer text-xs text-fg-faint transition-colors hover:text-fg-muted">
      {t("transcript.pensee-brute")}
    </summary>
    <div className="mt-2 border-l border-accent/50 pl-3 text-[13px] italic leading-relaxed text-fg-muted whitespace-pre-wrap">
      <ThinkAwareText text={entry.thinking} />
    </div>
  </details>
) : null}
```

  - Suivi du scroll (`page.tsx:525-529`) — la croissance intra-tour (pensée ET tokens publics) déclenche le suivi :

```ts
const lastTurn = round.turns[round.turns.length - 1];
const liveGrowth = (lastTurn?.raw.length ?? 0) + (lastTurn?.reasoning.length ?? 0);
useEffect(() => {
  if (selected !== "live" || !stickToLive) return;
  const el = transcriptRef.current;
  if (el) el.scrollTop = el.scrollHeight;
}, [selected, stickToLive, round.turns.length, liveGrowth, round.judgeText, round.motionText, round.status]);
```

  - i18n : fr `"transcript.pense-en-direct": "Pense en direct — sa réflexion s'affiche au fil de l'eau ci-dessous."`, `"transcript.pensee-brute": "Pensée brute (verbatim)"` ; en : `"Thinking live — the reasoning streams below."`, `"Raw thinking (verbatim)"`.

- [ ] **Step 4 : vert** — `npm test && npx tsc --noEmit && npm run lint`.
- [ ] **Step 5 : commit** — `git commit -m "feat(web): suivi du scroll intra-tour, libellé pense-en-direct, pensée brute au journal de relecture"`

---

### Task 7: Validation de branche

- [ ] **Step 1 :** `./.venv/Scripts/python.exe -m pytest -q` (attendu ~1 min, tout vert) ; `./.venv/Scripts/python.exe -m ruff check .`.
- [ ] **Step 2 :** `cd web && npm test && npx tsc --noEmit && npm run lint && npm run build`.
- [ ] **Step 3 :** vérification live optionnelle (Ollama) : partie `expose_thinking=True` → la fenêtre s'ouvre, la pensée défile, le Journal prend le relais à la fin du tour.
- [ ] **Step 4 :** revue finale multi-lentilles (fuite scellée / perfs re-render / i18n / a11y), corrections, puis push + PR.

## Hors périmètre (assumé)

- L'UI « moment fort » de la page fin (« ce que le traître pensait vraiment au round 3 ») : la donnée est désormais disponible (transcripts.thinking révélé en fin de partie) — le design de ce moment se fera avec le joueur.
- Le correctif `ranked`/expose_thinking listé par §4 : déjà livré en Vague 1.
- La campagne de mesure `scripts/dialogue_metrics.py` (§4, dernier ¶) : chantier séparé, Ollama live requis.
