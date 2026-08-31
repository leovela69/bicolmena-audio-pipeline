# -*- coding: utf-8 -*-
"""
scripts/setup_rvc_ci.py
Descarga y configura el runtime RVC v2 y sus pesos congelados para CI (Linux/Windows).
Verifica criptográficamente los hashes SHA-256 de los pesos descargados contra los valores exactos certificados.
Falla de forma inmediata (RuntimeError / sys.exit(1)) si algún hash no coincide.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import os
import hashlib
import urllib.request
import subprocess
from pathlib import Path

RVC_DIR = Path("assets/rvc_runtime")
RVC_REPO_URL = "https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI.git"
RVC_PINNED_COMMIT = "81eed5e8f68b6bed1789f682fe78cdd324495afc"

def sha256_file(path: Path) -> str:
    with path.open("rb") as f:
        if hasattr(hashlib, "file_digest"):
            return hashlib.file_digest(f, "sha256").hexdigest()
        else:
            h = hashlib.sha256()
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
            return h.hexdigest()

def descargar_con_progreso(url: str, dest: Path):
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  ℹ️ Archivo ya presente en disco: {dest.name}")
        return
    print(f"  📥 Descargando {dest.name} desde {url}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Bicolmena-CI-Engine)"})
    with urllib.request.urlopen(req) as resp, open(dest, "wb") as out_f:
        shutil_copy = out_f.write(resp.read())

def main():
    print("=" * 70)
    print("🚀 SETUP RVC CI · HARDENED ARTIFACT & REPO VERIFICATION")
    print("=" * 70)
    
    # 1. Asegurar directorio padre
    RVC_DIR.parent.mkdir(parents=True, exist_ok=True)
    
    # 2. Clonar y fijar commit inmutable de RVC ANTES de crear subcarpetas
    if not (RVC_DIR / ".git").exists():
        print(f"\n1. Clonando RVC runtime pinned al commit {RVC_PINNED_COMMIT[:10]}...")
        subprocess.run(["git", "clone", RVC_REPO_URL, str(RVC_DIR)], check=True)
        subprocess.run(["git", "checkout", "--detach", RVC_PINNED_COMMIT], cwd=str(RVC_DIR), check=True)
    else:
        print(f"\n1. RVC runtime presente. Verificando commit...")
        subprocess.run(["git", "checkout", "--detach", RVC_PINNED_COMMIT], cwd=str(RVC_DIR), check=True)
    
    res_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(RVC_DIR), capture_output=True, text=True, check=True)
    current_commit = res_commit.stdout.strip()
    if current_commit != RVC_PINNED_COMMIT:
        raise RuntimeError(f"RVC commit mismatch: esperado {RVC_PINNED_COMMIT}, actual {current_commit}")
    print(f"  ✅ RVC Runtime pinned commit: {current_commit[:16]}...")
    
    # 3. Crear subcarpetas de assets DENTRO del runtime ya clonado
    WEIGHTS_DIR = RVC_DIR / "assets/weights"
    INDICES_DIR = RVC_DIR / "assets/indices"
    HUBERT_DIR = RVC_DIR / "assets/hubert"
    RMVPE_DIR = RVC_DIR / "assets/rmvpe"
    
    for d in [WEIGHTS_DIR, INDICES_DIR, HUBERT_DIR, RMVPE_DIR]:
        d.mkdir(parents=True, exist_ok=True)
        
    models = [
        {
            "name": "default.pth",
            "url": "https://huggingface.co/PhoenixStormJr/RVC-V2-default-voice/resolve/main/default.pth",
            "dest": WEIGHTS_DIR / "default.pth",
            "sha256": "c9d6b0ac7aa8df91917757894561cd690e5c4b66e97a9f92630c0a7257fbfccc"
        },
        {
            "name": "default.index",
            "url": "https://huggingface.co/PhoenixStormJr/RVC-V2-default-voice/resolve/main/added_IVF511_Flat_nprobe_1_default_v2.index",
            "dest": INDICES_DIR / "default.index",
            "sha256": "93e0fbf723992b5ff6a1af3cae4e15f3bbb1dd860880fbd76565be23549aa1b7"
        },
        {
            "name": "hubert_base.pt",
            "url": "https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/hubert_base.pt",
            "dest": HUBERT_DIR / "hubert_base.pt",
            "sha256": "f54b40fd2802423a5643779c4861af1e9ee9c1564dc9d32f54f20b5ffba7db96"
        },
        {
            "name": "rmvpe.pt",
            "url": "https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/rmvpe.pt",
            "dest": RMVPE_DIR / "rmvpe.pt",
            "sha256": "6d62215f4306e3ca278246188607209f09af3dc77ed4232efdd069798c4ec193"
        }
    ]
        
    # 4. Descargar y verificar criptográficamente cada modelo
    print("\n2. Descargando y verificando SHA-256 estricto de pesos...")
    for m in models:
        descargar_con_progreso(m["url"], m["dest"])
        
        computed_sha = sha256_file(m["dest"]).lower()
        expected_sha = m["sha256"].lower()
        
        if computed_sha != expected_sha:
            raise RuntimeError(
                f"\n❌ SHA-256 MISMATCH para {m['name']}:\n"
                f"   Esperado: {expected_sha}\n"
                f"   Calculado: {computed_sha}\n"
                f"   La descarga está corrupta o el artefacto fue modificado."
            )
            
        print(f"  ✅ {m['name']}: SHA-256 verificado ({computed_sha[:16]}...)")
            
    print("\n🏆 RVC CI ENVIRONMENT HARDENED & READY")

if __name__ == "__main__":
    main()
