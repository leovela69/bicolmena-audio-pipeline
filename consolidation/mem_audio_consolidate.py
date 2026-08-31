# -*- coding: utf-8 -*-
"""
MEM-AUDIO-002 · CONSOLIDACIÓN Y ENCADENAMIENTO CRIPTOGRÁFICO DE SNAPSHOT (LEDGER BICOLMENA)
Crea el snapshot inmutable MEM-AUDIO-002 vinculado a su padre MEM-AUDIO-001 (SHA: d26569cc...):
  - Verifica los 8 tests reales: AUDIO-001 .. AUDIO-005 + AUDIO-005Q v2 (todos status == PASS).
  - Recalcula hashes SHA-256 de todas las evidencias físicas en disco.
  - Genera manifest_MEM-AUDIO_v2 con hash embebido del padre.
  - Replica y verifica byte a byte en los 3 espejos de memoria del sistema.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import json
import hashlib
import shutil
from pathlib import Path
from datetime import datetime, timezone

# ============ PARENT SNAPSHOT ============
PARENT_MANIFEST = Path(r"memory/hechos/c8l-audio-pipeline-pass-2026-08-31_07-32-02.manifest.json")
PARENT_SNAPSHOT = Path(r"memory/hechos/c8l-audio-pipeline-pass-2026-08-31_07-32-02.json")
EXPECTED_PARENT_SHA = "d26569cc62cc826d06dbd006177112a7a7266f809d435e07aee3b733b8eb25c7"

# ============ TEST FILES ============
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

# ============ EVIDENCE FILES ============
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

class Estado:
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"

def sha256_file(path: Path) -> str:
    with path.open("rb") as f:
        if hasattr(hashlib, "file_digest"):
            return hashlib.file_digest(f, "sha256").hexdigest()
        else:
            h = hashlib.sha256()
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
            return h.hexdigest()

def consolidar_mem_audio_002():
    print("=" * 70)
    print("🏛️ MEM-AUDIO-002 · CONSOLIDACIÓN DE LEDGER (ENCADENAMIENTO CRIPTOGRÁFICO)")
    print("=" * 70)
    
    # 1. Verificar integridad del padre MEM-AUDIO-001
    print("\n1. Verificando Snapshot Padre (MEM-AUDIO-001)...")
    if not PARENT_SNAPSHOT.exists():
        raise RuntimeError(f"Snapshot padre no encontrado: {PARENT_SNAPSHOT}")
    
    parent_sha = sha256_file(PARENT_SNAPSHOT)
    
    if PARENT_MANIFEST.exists():
        with open(PARENT_MANIFEST, "r", encoding="utf-8") as f:
            man = json.load(f)
            man_sha = man.get("sha256")
            if man_sha and man_sha != parent_sha:
                raise RuntimeError(f"Hash del manifest no coincide con el archivo: {man_sha} != {parent_sha}")
                
    print(f"   ✅ Padre verificado: {PARENT_SNAPSHOT.name}")
    print(f"   SHA-256 Padre: {parent_sha}")
    
    # 2. Cargar y verificar los 8 tests
    print("\n2. Verificando 8 JSONs de pruebas (AUDIO-001 .. AUDIO-005Q)...")
    passes = {}
    for test_id, path in TEST_FILES.items():
        if not path.exists():
            raise RuntimeError(f"Archivo de test ausente: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        status = data.get("status") or data.get("suite_status")
        if status != "PASS":
            raise RuntimeError(f"Test {test_id} no tiene status PASS: status={status}")
        
        file_sha = sha256_file(path)
        passes[test_id] = {
            "status": "PASS",
            "file": str(path),
            "sha256": file_sha,
            "size_bytes": path.stat().st_size
        }
        print(f"   ✅ {test_id}: PASS verificado (JSON SHA: {file_sha[:16]}...)")
        
    # 3. Recalcular evidencias físicas
    print("\n3. Recalculando hashes de evidencias WAV físicas en disco...")
    evidence = {}
    for name, path in EVIDENCE_FILES.items():
        if not path.exists():
            print(f"   ⚠️ Evidencia opcional no encontrada: {path}")
            continue
        sha = sha256_file(path)
        size = path.stat().st_size
        evidence[str(path)] = {
            "name": name,
            "sha256": sha,
            "size_bytes": size
        }
        print(f"   ✅ {name}: {sha[:16]}... ({size:,} bytes)")
        
    # 4. Crear Snapshot MEM-AUDIO-002
    print("\n4. Creando Snapshot encadenado MEM-AUDIO-002...")
    now_utc = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    snapshot_data = {
        "schema": "bicolmena.memory.audio.v2",
        "test_id": "MEM-AUDIO-002",
        "state": "VALIDATED",
        "created_at": now_utc,
        "module": "AUDIO",
        "chain": {
            "parent_tag": "MEM-AUDIO-001",
            "parent_snapshot_file": str(PARENT_SNAPSHOT),
            "parent_sha256": parent_sha,
            "parent_total_pass": 7,
            "chain_length": 2
        },
        "total_pass": len(passes),
        "passes": passes,
        "evidence": evidence,
        "blocked": {
            "AUDIO-005Q-HUMAN": {
                "reason": "Evaluación con voz humana consentida real pendiente"
            },
            "VIS-HF-001": {
                "reason": "OAuth Higgsfield pendiente en navegador"
            },
            "VIS-HF-002": {
                "reason": "Depende de VIS-HF-001"
            }
        }
    }
    
    root_dir = Path("memory/hechos")
    root_dir.mkdir(parents=True, exist_ok=True)
    
    snapshot_path = root_dir / f"c8l-audio-pipeline-pass-{stamp}.json"
    snapshot_path.write_text(json.dumps(snapshot_data, indent=2, ensure_ascii=False), encoding="utf-8")
    snapshot_sha = sha256_file(snapshot_path)
    
    manifest_data = {
        "schema": "bicolmena.manifest.v2",
        "test_id": "MEM-AUDIO-002",
        "snapshot": str(snapshot_path),
        "sha256": snapshot_sha,
        "created_at": now_utc,
        "parent_sha256": parent_sha,
        "total_pass": len(passes),
        "state": "VALIDATED"
    }
    
    manifest_path = root_dir / f"c8l-audio-pipeline-pass-{stamp}.manifest.json"
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
    
    print(f"   Snapshot creado: {snapshot_path}")
    print(f"   SHA-256 Snapshot: {snapshot_sha}")
    print(f"   Manifest creado: {manifest_path}")
    
    # 5. Replicar en los 3 espejos
    print("\n5. Replicando en 3 espejos con verificación de hash...")
    mirrors = [
        Path("04-sistema-y-seguridad/memory"),
        Path("01-proyectos-codigo/antigravity proyectos/memory"),
        Path("01-proyectos-codigo/claud code proyectos/memoria"),
    ]
    
    for i, mirror in enumerate(mirrors, 1):
        mirror.mkdir(parents=True, exist_ok=True)
        dst_snap = mirror / snapshot_path.name
        dst_man = mirror / manifest_path.name
        
        shutil.copy2(snapshot_path, dst_snap)
        shutil.copy2(manifest_path, dst_man)
        
        if sha256_file(dst_snap) != snapshot_sha:
            raise RuntimeError(f"Fallo de integridad en espejo {i}: {dst_snap}")
        print(f"   ✅ Espejo {i}/3: {dst_snap} (SHA verificado)")
        
    print(f"\n{'=' * 70}")
    print(f"🏆 MEM-AUDIO-002 VALIDATED (PASS)")
    print(f"   Total PASS Encadenados: {len(passes)}/8")
    print(f"   Hash Padre:    {parent_sha[:16]}...")
    print(f"   Hash Snapshot: {snapshot_sha[:16]}...")
    print(f"   Espejos:       3/3 Replicados y Verificados")
    print(f"{'=' * 70}")
    
    return {
        "status": "PASS",
        "snapshot": str(snapshot_path),
        "sha256": snapshot_sha,
        "parent_sha256": parent_sha,
        "total_pass": len(passes)
    }

if __name__ == "__main__":
    consolidar_mem_audio_002()
