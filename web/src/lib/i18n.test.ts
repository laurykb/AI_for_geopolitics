import { describe, expect, it } from "vitest";

import { translate, translateWith } from "./i18n";

const dicts = {
  fr: { "a.titre": "Bonjour", "a.seul-fr": "Seulement en français" },
  en: { "a.titre": "Hello" },
};

describe("traduction (le français est la langue source)", () => {
  it("sert la chaîne de la langue demandée", () => {
    expect(translateWith(dicts, "en", "a.titre")).toBe("Hello");
    expect(translateWith(dicts, "fr", "a.titre")).toBe("Bonjour");
  });

  it("retombe sur le français quand l'anglais manque", () => {
    expect(translateWith(dicts, "en", "a.seul-fr")).toBe("Seulement en français");
  });

  it("une clé inconnue partout ressort telle quelle (repérable en dev)", () => {
    expect(translateWith(dicts, "en", "z.inconnue")).toBe("z.inconnue");
  });

  it("les vrais dictionnaires portent les pages pilotes (header)", () => {
    expect(translate("fr", "header.accueil")).toBe("Accueil");
    expect(translate("en", "header.accueil")).toBe("Home");
  });
});
