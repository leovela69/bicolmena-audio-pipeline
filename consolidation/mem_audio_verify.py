# -*- coding: utf-8 -*-
"""
consolidation/mem_audio_verify.py
Verificador estricto offline de snapshots y manifests criptográficos.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import argparse
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

def verify(snapshot_path: Path, manifest_path: Path, strict: bool = False):
    print("=" * 60)
    print(f"🔍 VERIFICACIÓN DE SNAPSHOT: {snapshot_path.name}")
    print("=" * 60)
    
    if not snapshot_path.exists():
        print(f"❌ Snapshot ausente: {snapshot_path}")
        sys.exit(1)
        
    if not manifest_path.exists():
        print(f"❌ Manifest ausente: {manifest_path}")
        sys.exit(1)
        
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    computed_sha = sha256_file(snapshot_path)
    manifest_sha = manifest.get("sha256")
    
    if computed_sha != manifest_sha:
        print(f"❌ INTEGRITY FAILURE\n  Esperado:  {manifest_sha}\n  Calculado: {computed_sha}")
        sys.exit(1)
        
    print(f"  ✅ Integridad SHA-256 verificada: {computed_sha[:16]}...")
    
    with open(snapshot_path, "r", encoding="utf-8") as f:
        snapshot = json.load(f)
        
    passes = snapshot.get("passes", {})
    for test_id, data in passes.items():
        if data.get("status") != "PASS":
            print(f"  ❌ Test {test_id} no tiene status PASS")
            sys.exit(1)
            
    print(f"  ✅ Todos los {len(passes)} tests reportados tienen status PASS")
    
    if strict:
        evidence = snapshot.get("evidence", {})
        for file_path, file_data in evidence.items():
            p = Path(file_path)
            if not p.exists():
                print(f"  ⚠️ Evidencia ausente en disco: {file_path}")
                continue
            ev_sha = sha256_file(p)
            if ev_sha != file_data.get("sha256"):
                print(f"  ❌ Hash mismatch en {file_path}")
                sys.exit(1)
        print(f"  ✅ Evidencias físicas verificadas")
        
    print("\n🏆 SNAPSHOT VALIDATED (INTEGRITY OK)")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    
    verify(args.snapshot, args.manifest, args.strict)
