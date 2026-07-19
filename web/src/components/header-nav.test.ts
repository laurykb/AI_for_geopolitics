import { describe, expect, it } from "vitest";

import { HEADER_LINKS } from "./header-nav";

describe("navigation des modes de jeu", () => {
  it("réserve le Laboratoire au parcours Nouvelle partie", () => {
    expect(HEADER_LINKS.some((link) => link.href === "/laboratoire")).toBe(false);
    expect(HEADER_LINKS.some((link) => link.href === "/accueil")).toBe(true);
  });
});
