# -*- coding: utf-8 -*-
"""
consolidation/verify_chain.py
Verifica la cadena de custodia con el snapshot padre.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import json
import hashlib
from pathlib import Path

def sha256_file(path: Path) -> str:
    with path.open("rb") as f:
        if hasattr(hashlib, "file_digest"):
            return hashlib.file_digest(f, "sha256").hexdigest()
        else:
            h = hashlib.sha256()
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
            return h.hexdigest()

def main():
    snapshot_files = list(Path(".").glob("snapshot_*.json"))
    if not snapshot_files:
        print("❌ No se encontró snapshot")
        sys.exit(1)
    
    snapshot_path = snapshot_files[0]
    
    with open(snapshot_path, "r", encoding="utf-8") as f:
        snapshot = json.load(f)
    
    parent_sha = snapshot.get("chain", {}).get("parent_sha256")
    
    if parent_sha is None or parent_sha == "none":
        print("ℹ️ Snapshot genesis (sin padre)")
        sys.exit(0)
    
    # Buscar padre en releases previos
    parent_files = [p for p in Path(".").glob("snapshot_*.json") if p != snapshot_path]
    
    for parent_file in parent_files:
        computed = sha256_file(parent_file)
        if computed == parent_sha:
            print(f"✅ Cadena verificada con padre: {parent_file.name} (SHA: {computed[:16]}...)")
            sys.exit(0)
    
    # Si se pasó parent manifest descargado de release
    parent_manifests = list(Path(".").glob("manifest_*.json"))
    for p_man in parent_manifests:
        with open(p_man, "r", encoding="utf-8") as f:
            m = json.load(f)
            if m.get("sha256") == parent_sha:
                print(f"✅ Cadena verificada con manifest del padre: {p_man.name} (SHA: {parent_sha[:16]}...)")
                sys.exit(0)
                
    print(f"❌ Snapshot padre no encontrado o hash mismatch")
    print(f"   Esperado: {parent_sha}")
    sys.exit(1)

if __name__ == "__main__":
    main()
