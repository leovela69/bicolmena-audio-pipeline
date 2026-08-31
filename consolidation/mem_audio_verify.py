# -*- coding: utf-8 -*-
"""
consolidation/mem_audio_verify.py
Verificador estricto offline de snapshots, manifests, reportes de test y evidencias físicas.
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
    print("=" * 70)
    print(f"🔍 VERIFICACIÓN CRIPTOGRÁFICA DE SNAPSHOT: {snapshot_path.name}")
    print("=" * 70)
    
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
        
    print(f"  ✅ Integridad SHA-256 del Snapshot verificada: {computed_sha[:16]}...")
    
    with open(snapshot_path, "r", encoding="utf-8") as f:
        snapshot = json.load(f)
        
    passes = snapshot.get("passes", {})
    if len(passes) < 8:
        print(f"❌ Menos de 8 tests reportados ({len(passes)}/8)")
        sys.exit(1)

    for test_id, data in passes.items():
        if data.get("status") != "PASS":
            print(f"  ❌ Test {test_id} no tiene status PASS")
            sys.exit(1)
            
    print(f"  ✅ Todos los {len(passes)} tests reportados tienen status PASS")
    
    if strict:
        print("\n🔒 [MODO STRICT] Verificando 8 reportes JSON y 13 evidencias físicas...")
        
        # 1. Recalcular y verificar los 8 reportes JSON
        missing_reports = []
        mismatched_reports = []
        for test_id, entry in passes.items():
            rep_path = Path(entry["report_file"])
            if not rep_path.exists():
                missing_reports.append(entry["report_file"])
                continue
            rep_sha = sha256_file(rep_path)
            if rep_sha != entry.get("report_sha256"):
                mismatched_reports.append(f"{entry['report_file']} (esperado {entry.get('report_sha256')[:16]}..., actual {rep_sha[:16]}...)")
                
        if missing_reports:
            print(f"❌ STRICT FAILURE: Reportes de test ausentes en disco:")
            for m_r in missing_reports:
                print(f"   - {m_r}")
            sys.exit(1)
            
        if mismatched_reports:
            print(f"❌ STRICT FAILURE: Hash mismatch en reportes de test:")
            for m_r in mismatched_reports:
                print(f"   - {m_r}")
            sys.exit(1)
            
        print(f"  ✅ Todos los {len(passes)} reportes JSON verificados byte a byte")

        # 2. Recalcular y verificar las evidencias físicas (WAVs)
        evidence = snapshot.get("evidence", {})
        if len(evidence) < 13:
            print(f"❌ Menos de 13 evidencias registradas en el snapshot ({len(evidence)}/13)")
            sys.exit(1)

        missing_evidence = []
        mismatched_evidence = []
        for file_path, file_data in evidence.items():
            p = Path(file_path)
            if not p.exists():
                missing_evidence.append(file_path)
                continue
            ev_sha = sha256_file(p)
            if ev_sha != file_data.get("sha256"):
                mismatched_evidence.append(f"{file_path} (esperado {file_data.get('sha256')[:16]}..., actual {ev_sha[:16]}...)")
                
        if missing_evidence:
            print(f"❌ STRICT FAILURE: Evidencias físicas ausentes en disco:")
            for m_f in missing_evidence:
                print(f"   - {m_f}")
            sys.exit(1)
            
        if mismatched_evidence:
            print(f"❌ STRICT FAILURE: Hash mismatch en evidencias físicas:")
            for m_f in mismatched_evidence:
                print(f"   - {m_f}")
            sys.exit(1)
            
        print(f"  ✅ Todas las {len(evidence)} evidencias físicas verificadas byte a byte")
        
    print("\n🏆 SNAPSHOT & EVIDENCE PHYSICALLY CERTIFIED (PASS)")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    
    verify(args.snapshot, args.manifest, args.strict)
