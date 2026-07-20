/** Pensée à découvert — habillage visuel des balises `<think>` dans la bulle de
 * transcript (rendu statique, sans DOM) : les segments de pensée sont stylés à part,
 * les balises disparaissent de l'affichage, le contenu et l'ordre restent intacts. */

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { SettingsProvider } from "@/components/settings-provider";
import { EntryBubble, TurnBubble } from "@/components/transcript";
import type { LiveTurn } from "@/hooks/useRoundStream";
import type { TranscriptEntry } from "@/lib/types";

function renderEntry(entry: TranscriptEntry): string {
  return renderToStaticMarkup(
    createElement(SettingsProvider, null, createElement(EntryBubble, { entry })),
  );
}

function renderTurn(
  turn: LiveTurn,
  props: { exposeThinking?: boolean; thinkingOpen?: boolean } = {},
): string {
  return renderToStaticMarkup(
    createElement(SettingsProvider, null, createElement(TurnBubble, { turn, ...props })),
  );
}

const baseEntry: TranscriptEntry = {
  id: "t1",
  round_id: "r1",
  seq: 0,
  speaker: "usa",
  model: "deepseek-r1:7b",
  content: "Nous proposons un compromis.",
  reasoning: "",
  thinking: "",
  ts: "",
};

describe("EntryBubble — habillage visuel de la pensée (relecture)", () => {
  it("retire les balises <think> de l'affichage sans toucher au contenu", () => {
    const html = renderEntry({
      ...baseEntry,
      reasoning: "<think>trace privée</think>Observation : le contexte est tendu.",
    });
    expect(html).not.toContain("<think>");
    expect(html).not.toContain("&lt;think&gt;");
    expect(html).not.toContain("</think>");
    expect(html).toContain("trace privée");
    expect(html).toContain("Observation : le contexte est tendu.");
  });

  it("préserve l'ordre réel du flux : la pensée précède la décision dans le HTML", () => {
    // Pas d'apostrophe dans les segments comparés : React échappe `'` en `&#x27;`
    // dans le HTML rendu (cf. event-card.test.ts), ce qui casserait l'indexOf ici.
    const html = renderEntry({
      ...baseEntry,
      reasoning: "<think>trace de pensée initiale</think>texte de décision final",
    });
    expect(html.indexOf("trace de pensée initiale")).toBeGreaterThan(-1);
    expect(html.indexOf("texte de décision final")).toBeGreaterThan(-1);
    expect(html.indexOf("trace de pensée initiale")).toBeLessThan(
      html.indexOf("texte de décision final"),
    );
  });

  it("sans balise <think>, le texte s'affiche tel quel (comportement inchangé)", () => {
    const html = renderEntry({ ...baseEntry, reasoning: "Observation : rien à signaler." });
    expect(html).toContain("Observation : rien à signaler.");
  });

  it("sans reasoning, aucune section pensée n'apparaît", () => {
    const html = renderEntry({ ...baseEntry, reasoning: "" });
    expect(html).not.toContain("journal");
  });
});

describe("TurnBubble — même habillage en direct (brouillon en cours)", () => {
  it("le brouillon en cours retire aussi les balises <think>", () => {
    const turn: LiveTurn = {
      country: "usa",
      model: "deepseek-r1:7b",
      passNo: 0,
      // Le marqueur MESSAGE: force `splitStreaming` à isoler un reasoning non vide
      // (reproduit la forme d'un brouillon en direct porteur d'une trace de pensée).
      raw: "<think>brouillon en cours</think>Analyse.\nMESSAGE: réponse publique",
      text: "",
      reasoning: "",
      done: false,
    };
    const html = renderTurn(turn);
    expect(html).not.toContain("<think>");
    expect(html).not.toContain("&lt;think&gt;");
    expect(html).toContain("brouillon en cours");
  });
});

describe("TurnBubble — fenêtre de pensée en direct (Pensée à découvert)", () => {
  const liveThinking = {
    country: "usa", model: "deepseek-r1:7b", passNo: 1,
    raw: "", text: "", reasoning: "<think>je soupçonne Téhéran</think>", done: false,
  } as LiveTurn;

  it("live avec reasoning rempli et raw vide → la pensée s'affiche, balises retirées", () => {
    const html = renderTurn(liveThinking, { exposeThinking: true, thinkingOpen: true });
    expect(html).toContain("je soupçonne Téhéran");
    expect(html).not.toContain("&lt;think&gt;");
  });

  it("fermée par défaut : le corps n'est pas rendu", () => {
    const html = renderTurn(liveThinking, { exposeThinking: true });
    expect(html).not.toContain("je soupçonne Téhéran"); // résumé seul, corps absent
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
