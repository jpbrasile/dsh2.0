#!/usr/bin/env python3
"""Imprime la clef unifiee de FreeLLMAPI, lue dans la base de l'app Desktop.

Pourquoi un fichier plutot qu'un `python -c` dans dsh.ps1 : la version en ligne
exige des guillemets imbriques (PowerShell -> python -> SQL), et PowerShell les
mange en silence. Mesure du 2026-08-22 : le one-liner rendait
`SyntaxError: unterminated string literal` et la variable restait VIDE, ce qui
se manifeste plus tard en `PI_AI_ERROR: No API key for provider` -- une erreur
qui envoie chercher au mauvais endroit.

Usage :
    python scripts/freellm_key.py            # base par defaut (app Desktop)
    python scripts/freellm_key.py <chemin>   # base explicite

Sortie : la clef sur stdout, rien d'autre. Code 1 et message sur stderr si la
base est absente ou si la clef n'a pas encore ete generee.
"""

import os
import sqlite3
import sys
from pathlib import Path


def default_db() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "FreeLLMAPI" / "freeapi.db"
    # Serveur / docker : la base vit a cote du code.
    return Path.home() / ".freellmapi" / "server" / "data" / "freeapi.db"


def read_key(db: Path) -> str:
    if not db.is_file():
        raise SystemExit(f"freellm_key: base introuvable: {db}")
    # mode=ro : l'app Desktop tient le WAL en ecriture pendant qu'elle tourne.
    uri = "file:" + db.as_posix() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as con:
        row = con.execute(
            "SELECT value FROM settings WHERE key = 'unified_api_key'"
        ).fetchone()
    if not row or not row[0]:
        raise SystemExit(
            "freellm_key: aucune clef unifiee en base. "
            "Ouvrir le tableau de bord (relancer FreeLLMAPI.exe) au moins une fois."
        )
    return row[0]


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_db()
    sys.stdout.write(read_key(path))
