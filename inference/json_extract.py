"""Extraction tolérante d'un objet JSON depuis une sortie LLM.

Utilitaire **neutre** (aucune dépendance projet, juste la stdlib) : le point unique
partagé par tous les parseurs de sortie structurée (agents, juge, marché, forge de
pays, actes de dialogue, votes de motion). Il isole l'objet JSON de la prose et des
```fences``` que les modèles ajoutent souvent autour, et **ne lève jamais** : une
sortie inexploitable rend `None` (les appelants basculent alors sur leur repli
déterministe). Vit dans `inference/` pour rester importable sans cycle depuis
`agents/`, `market/` et `simulation/` (raison historique des copies factorisées ici).
"""

from __future__ import annotations

import json


def extract_json(text: str | None) -> dict | None:
    """Extrait un objet JSON d'une sortie LLM (gère fences et prose autour).

    Tente d'abord un parse direct ; à défaut, isole la première accolade ouvrante
    et la dernière fermante. Rend le dict trouvé, ou `None` si rien d'exploitable.
    """
    text = (text or "").strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except (json.JSONDecodeError, ValueError):
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except (json.JSONDecodeError, ValueError):
            return None
    return None
