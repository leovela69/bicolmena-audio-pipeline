# -*- coding: utf-8 -*-
"""
consolidation/mem_audio_consolidate.py
Consolidador criptográfico nativo de CI para Bicolmena Audio Ledger.
Verifica 8/8 tests reales, 13/13 evidencias obligatorias, y encadena el hash del padre.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import os
import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime, timezone

TEST_FILES = {
    "AUDIO-001": Path("AUDIO-001_metrics.json"),
    "AUDIO-002": Path("AUDIO-002_metrics.json"),
    "AUDIO-003": Path("AUDIO-003_metrics.json"),
    "AUDIO-004A": Path("AUDIO-004A_v2_metrics.json"),
    "AUDIO-004Q": Path("AUDIO-004Q_metrics.json"),
    "AUDIO-004R": Path("AUDIO-004R_metrics.json"),
    "AUDIO-005": Path("AUDIO-005_metrics.json"),
    "AUDIO-005Q": Path("AUDIO-005Q_v2_metrics.json"),
}

EVIDENCE_FILES = {
    "raw_musicgen_32k.wav": Path("raw_musicgen_32k.wav"),
    "resampled_musicgen_48k.wav": Path("resampled_musicgen_48k.wav"),
    "neural_flamenco_bolero_master.wav": Path("neural_flamenco_bolero_master.wav"),
    "rvc_native.wav": Path("evidence/audio/AUDIO-004/rvc_native.wav"),
    "rvc_resampled_48k.wav": Path("evidence/audio/AUDIO-004/rvc_resampled_48k.wav"),
    "c8l_neural_master.wav": Path("evidence/audio/AUDIO-005/c8l_neural_master.wav"),
    "guide_F1_44k.wav": Path("evidence/audio/AUDIO-005Q/guide_F1_44k.wav"),
    "rvc_F1_40k.wav": Path("evidence/audio/AUDIO-005Q/rvc_F1_40k.wav"),
    "guide_F2_44k.wav": Path("evidence/audio/AUDIO-005Q/guide_F2_44k.wav"),
    "rvc_F2_40k.wav": Path("evidence/audio/AUDIO-005Q/rvc_F2_40k.wav"),
    "guide_F3_44k.wav": Path("evidence/audio/AUDIO-005Q/guide_F3_44k.wav"),
    "rvc_F3_40k.wav": Path("evidence/audio/AUDIO-005Q/rvc_F3_40k.wav"),
    "silence_test_3s.wav": Path("evidence/audio/AUDIO-005Q/silence_test_3s.wav"),
}

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
    parser = argparse.ArgumentParser(description="Bicolmena Ledger Consolidator")
    parser.add_argument("--parent-tag", default="GENESIS", help="Tag del snapshot padre")
    parser.add_argument("--parent-sha", default="none", help="SHA-256 del snapshot padre")
    parser.add_argument("--ci-run-id", default="local", help="ID del run de CI")
    parser.add_argument("--git-commit", default="local", help="Commit hash de Git")
    args = parser.parse_args()

    print("=" * 70)
    print("🏛️ BICOLMENA AUDIO LEDGER · CONSOLIDACIÓN CRIPTOGRÁFICA")
    print("=" * 70)
    print(f"Parent Tag: {args.parent_tag}")
    print(f"Parent SHA: {args.parent_sha}")
    print(f"CI Run ID:  {args.ci_run_id}")
    print(f"Commit:     {args.git_commit}")

    # 1. Verificar los 8 tests reales
    print("\n1. Verificando los 8 reportes de test...")
    passes = {}
    for test_id, json_path in TEST_FILES.items():
        if not json_path.exists():
            raise RuntimeError(f"Reporte de test ausente: {json_path}")
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        status = data.get("status")
        if status != "PASS":
            raise RuntimeError(f"Test {test_id} no pasó (status={status})")
        passes[test_id] = {
            "status": "PASS",
            "report_file": json_path.name,
            "report_sha256": sha256_file(json_path),
            "timestamp": data.get("timestamp", datetime.now(timezone.utc).isoformat())
        }
        print(f"  ✅ {test_id}: PASS ({json_path.name})")

    # 2. Verificar las 13 evidencias físicas obligatorias
    print("\n2. Verificando y recalculando SHA-256 de las 13 evidencias físicas...")
    evidence = {}
    for ev_name, ev_path in EVIDENCE_FILES.items():
        if not ev_path.exists():
            raise RuntimeError(f"❌ Evidencia obligatoria ausente: {ev_path}")
        ev_sha = sha256_file(ev_path)
        ev_size = ev_path.stat().st_size
        evidence[str(ev_path.as_posix())] = {
            "name": ev_name,
            "sha256": ev_sha,
            "size_bytes": ev_size
        }
        print(f"  ✅ {ev_name}: {ev_sha[:16]}... ({ev_size} bytes)")

    # 3. Construir Snapshot
    now_iso = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    
    snapshot_payload = {
        "ledger": "BICOLMENA_AUDIO_CHAIN",
        "protocol_version": "2.0.0",
        "timestamp_utc": now_iso,
        "ci_run_id": args.ci_run_id,
        "git_commit": args.git_commit,
        "parent_chain": {
            "parent_tag": args.parent_tag,
            "parent_sha256": args.parent_sha
        },
        "passes": passes,
        "evidence": evidence
    }

    snapshot_filename = f"snapshot_MEM-AUDIO_{stamp}.json"
    manifest_filename = f"manifest_MEM-AUDIO_{stamp}.json"

    with open(snapshot_filename, "w", encoding="utf-8") as f:
        json.dump(snapshot_payload, f, indent=2, ensure_ascii=False)

    snapshot_sha = sha256_file(Path(snapshot_filename))
    print(f"\n📦 Snapshot generado: {snapshot_filename}")
    print(f"   SHA-256: {snapshot_sha}")

    # 4. Construir Manifest
    manifest_payload = {
        "snapshot_file": snapshot_filename,
        "sha256": snapshot_sha,
        "parent_tag": args.parent_tag,
        "parent_sha256": args.parent_sha,
        "total_tests_passed": len(passes),
        "total_evidence_files": len(evidence),
        "created_utc": now_iso
    }

    with open(manifest_filename, "w", encoding="utf-8") as f:
        json.dump(manifest_payload, f, indent=2, ensure_ascii=False)

    print(f"📋 Manifest generado: {manifest_filename}")
    print("\n🏆 CONSOLIDACIÓN COMPLETADA (LEDGER BLOCK READY)")

if __name__ == "__main__":
    main()
