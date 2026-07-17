#!/usr/bin/env python3
"""Lanceur une-ligne du Theatre des super-intelligences.

`python serve.py` demarre en une commande **l'API** (FastAPI/uvicorn, :8000) **et le
front** (Next.js, :3000). Il resout le Python du venv, installe `web/node_modules` au
besoin, avertit si Ollama est absent (les IA en dependent) sans jamais bloquer, prefixe
les logs des deux process et les arrete proprement au Ctrl+C.

Stdlib uniquement (aucune dependance a installer). Cross-plateforme (Windows / POSIX).

Exemples :
    python serve.py                          # API :8000 + front :3000
    python serve.py --api-only               # API seule
    python serve.py --api-port 8010 --web-port 3010   # ports alternatifs
    python serve.py --no-ollama-check        # saute l'avertissement Ollama
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
IS_WINDOWS = os.name == "nt"
OLLAMA_URL = "http://127.0.0.1:11434/api/tags"

# Serialise les ecritures des threads de log pour ne pas entrelacer les lignes.
_print_lock = threading.Lock()


def log(prefix: str, message: str) -> None:
    """Ecrit une ligne prefixee (`[api] ...`, `[web] ...`, `[serve] ...`)."""
    with _print_lock:
        print(f"[{prefix}] {message}", flush=True)


def _request_shutdown(_signum: int, _frame: object) -> None:
    """Traite Ctrl+Break (Windows) comme Ctrl+C : declenche l'arret propre."""
    raise KeyboardInterrupt


def venv_python() -> str:
    """Python du venv (`.venv`) si present, sinon l'interpreteur courant (repli)."""
    sub = "Scripts" if IS_WINDOWS else "bin"
    exe = "python.exe" if IS_WINDOWS else "python"
    candidate = ROOT / ".venv" / sub / exe
    if candidate.exists():
        return str(candidate)
    return sys.executable


def find_npm() -> str | None:
    """Chemin de npm (`npm.cmd` sur Windows) : via le PATH, puis emplacements usuels."""
    for name in ("npm", "npm.cmd"):
        found = shutil.which(name)
        if found:
            return found
    if IS_WINDOWS:  # Node hors PATH est frequent sur Windows -> essai de l'emplacement par defaut
        guess = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "nodejs" / "npm.cmd"
        if guess.exists():
            return str(guess)
    return None


def check_ollama() -> None:
    """Avertit si Ollama est injoignable (les SI en ont besoin) — jamais bloquant."""
    try:
        with urllib.request.urlopen(OLLAMA_URL, timeout=2) as resp:
            if resp.status == 200:
                log("serve", "Ollama detecte (127.0.0.1:11434).")
                return
    except (urllib.error.URLError, OSError, ValueError):
        pass
    log("serve", "ATTENTION : Ollama injoignable (127.0.0.1:11434) — sans lui les IA ne")
    log("serve", "            repondront pas. Lance `ollama serve` puis `ollama pull mistral`.")
    log("serve", "            L'interface se charge quand meme.")


def _spawn(cmd: list[str], *, cwd: str, env: dict[str, str] | None = None) -> subprocess.Popen:
    """Demarre un process enfant dans son PROPRE groupe (arret cible au shutdown),
    stdout+stderr fusionnes dans un tube lu ligne a ligne par un thread `_pump`."""
    kwargs: dict = {
        "cwd": cwd,
        "env": env,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "bufsize": 1,
    }
    if IS_WINDOWS:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(cmd, **kwargs)


def _pump(prefix: str, proc: subprocess.Popen) -> None:
    """Relaie la sortie d'un enfant, ligne a ligne, prefixee (thread daemon)."""
    if proc.stdout is None:
        return
    for line in proc.stdout:
        log(prefix, line.rstrip())


def ensure_node_modules(npm: str) -> None:
    """Installe les dependances front si `web/node_modules` manque (une fois)."""
    if (WEB_DIR / "node_modules").is_dir():
        return
    log("serve", "web/node_modules absent -> npm install (une fois, patiente)...")
    result = subprocess.run([npm, "install"], cwd=str(WEB_DIR))
    if result.returncode != 0:
        raise SystemExit(f"[serve] npm install a echoue (code {result.returncode}).")


def start_api(host: str, port: int) -> subprocess.Popen:
    """uvicorn app.main:app sur host:port (Python du venv)."""
    cmd = [venv_python(), "-m", "uvicorn", "app.main:app", "--host", host, "--port", str(port)]
    log("serve", f"API    -> http://{host}:{port}  (docs: /docs)")
    return _spawn(cmd, cwd=str(ROOT))


def start_web(npm: str, port: int) -> subprocess.Popen:
    """`npm run dev` dans web/ ; le port passe par la variable PORT (respectee par Next)."""
    env = dict(os.environ)
    env["PORT"] = str(port)
    log("serve", f"front  -> http://localhost:{port}")
    return _spawn([npm, "run", "dev"], cwd=str(WEB_DIR), env=env)


def _listener_pids(ports: list[int]) -> set[int]:
    """PIDs qui ECOUTENT encore sur nos ports (Windows, via `netstat -ano`).

    Filet anti-orphelin : `next dev` boote un `node` en profondeur alors que le
    `npm.cmd`/`cmd.exe` intermediaire sort — l'arbre depuis le PID enregistre casse,
    et un `taskkill /T` classique rate le serveur. On retrouve le coupable par le port."""
    suffixes = tuple(f":{p}" for p in ports)
    pids: set[int] = set()
    try:  # bytes + decode tolerant : netstat sort dans la code page OEM, pas en UTF-8
        out = subprocess.run(["netstat", "-ano"], capture_output=True)
    except OSError:
        return pids
    text = out.stdout.decode("utf-8", "replace") if out.stdout else ""
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[3].upper() == "LISTENING":
            if parts[1].endswith(suffixes) and parts[-1].isdigit():
                pids.add(int(parts[-1]))
    return pids


def _taskkill_tree(pid: int) -> None:
    subprocess.run(
        ["taskkill", "/F", "/T", "/PID", str(pid)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def stop(children: list[tuple[str, subprocess.Popen]], ports: list[int]) -> None:
    """Arrete les deux enfants ET tout leur arbre — aucun orphelin ne survit.

    Windows : `taskkill /T` sur les PID enregistres, PUIS sur qui ecoute encore nos
    ports (le serveur `next dev` se re-parente hors de l'arbre). POSIX : SIGTERM au
    groupe (grace) puis SIGKILL ; `start_new_session` garantit qu'aucun descendant
    n'echappe, donc pas besoin du filet par port."""
    log("serve", "arret en cours...")
    if IS_WINDOWS:
        for _name, proc in children:
            if proc.poll() is None:
                _taskkill_tree(proc.pid)
        for pid in _listener_pids(ports):
            _taskkill_tree(pid)
        for _name, proc in children:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        return

    for _name, proc in children:  # POSIX : arret doux du groupe entier
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except (OSError, ValueError):
                pass
    deadline = time.time() + 6.0
    for _name, proc in children:
        try:
            proc.wait(timeout=max(0.0, deadline - time.time()))
        except subprocess.TimeoutExpired:
            pass
    for name, proc in children:  # forcer le reliquat
        if proc.poll() is None:
            log("serve", f"{name} recalcitrant -> arret force")
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (OSError, ValueError):
                proc.kill()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Demarre l'API (:8000) et le front (:3000) en une commande.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--api-port", type=int, default=8000, help="port de l'API")
    p.add_argument("--web-port", type=int, default=3000, help="port du front")
    p.add_argument("--api-host", default="127.0.0.1", help="hote de l'API")
    p.add_argument("--api-only", action="store_true", help="ne lancer que l'API")
    p.add_argument("--web-only", action="store_true", help="ne lancer que le front")
    p.add_argument("--no-ollama-check", action="store_true", help="sauter la verif Ollama")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.api_only and args.web_only:
        raise SystemExit("[serve] --api-only et --web-only sont exclusifs.")

    run_api = not args.web_only
    run_web = not args.api_only

    # Ctrl+C (SIGINT) leve deja KeyboardInterrupt ; sous Windows, traiter aussi Ctrl+Break.
    if IS_WINDOWS and hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _request_shutdown)

    if run_api and not args.no_ollama_check:
        check_ollama()

    children: list[tuple[str, subprocess.Popen]] = []
    ports: list[int] = []  # ports reellement ouverts (filet anti-orphelin du stop Windows)
    try:
        if run_api:
            children.append(("api", start_api(args.api_host, args.api_port)))
            ports.append(args.api_port)
        if run_web:
            npm = find_npm()
            if npm is None:
                msg = "npm introuvable : installe Node.js (https://nodejs.org)."
                if run_api:
                    log("serve", f"{msg} -> front non lance, API seule.")
                else:
                    raise SystemExit(f"[serve] {msg}")
            else:
                ensure_node_modules(npm)
                children.append(("web", start_web(npm, args.web_port)))
                ports.append(args.web_port)

        if not children:
            raise SystemExit("[serve] rien a lancer.")

        for name, proc in children:
            threading.Thread(target=_pump, args=(name, proc), daemon=True).start()

        log("serve", "en marche. Ctrl+C pour tout arreter.")
        while True:  # si un enfant meurt, on arrete les autres et on sort
            for name, proc in children:
                rc = proc.poll()
                if rc is not None:
                    log("serve", f"{name} s'est arrete (code {rc}) — arret des autres.")
                    raise KeyboardInterrupt
            time.sleep(0.5)
    except KeyboardInterrupt:
        with _print_lock:
            print(flush=True)  # saut de ligne apres le ^C du terminal
        stop(children, ports)
    log("serve", "termine.")


if __name__ == "__main__":
    main()
