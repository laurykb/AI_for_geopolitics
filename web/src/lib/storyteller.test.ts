import { describe, expect, it } from "vitest";

import { translate } from "./i18n";
import { gmShadowItems } from "./storyteller";

describe("l'ombre du GM (G19) — items de la section de révélation", () => {
  it("mappe chaque intervention sur sa clé i18n", () => {
    const items = gmShadowItems({
      gm_interventions: [
        { round_no: 2, kind: "cover", tension: 0.82, target: "france", label: "x" },
        { round_no: 4, kind: "hint", tension: 0.12, target: "iran", label: "y" },
      ],
    });
    expect(items).toEqual([
      { roundNo: 2, key: "drift.gm.couverture", target: "france", tension: 0.82 },
      { roundNo: 4, key: "drift.gm.indice", target: "iran", tension: 0.12 },
    ]);
  });

  it("un kind inconnu retombe sur la clé générique (compat futur backend)", () => {
    const items = gmShadowItems({
      gm_interventions: [{ round_no: 1, kind: "???", tension: 0.5, target: "", label: "" }],
    });
    expect(items[0].key).toBe("drift.gm.autre");
  });

  it("tolère les révélations d'avant G19 (champ absent)", () => {
    expect(gmShadowItems({})).toEqual([]);
  });

  it("les clés de la section existent en fr ET en en", () => {
    for (const key of [
      "drift.gm.titre",
      "drift.gm.aucune",
      "drift.gm.couverture",
      "drift.gm.indice",
      "drift.gm.autre",
      "drift.gm.tension",
      "drift.gm.explication",
    ]) {
      expect(translate("fr", key)).not.toBe(key);
      expect(translate("en", key)).not.toBe(key);
      expect(translate("en", key)).not.toBe(translate("fr", key)); // vraie traduction
    }
  });
});
