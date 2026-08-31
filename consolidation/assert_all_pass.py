# -*- coding: utf-8 -*-
"""
consolidation/assert_all_pass.py
Verifica de forma estricta que los 8 JSONs de prueba existen y declaran status == "PASS".
Falla con exit code 1 si falta algún archivo o algún test no pasó.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import json
from pathlib import Path

REQUIRED_TESTS = {
    "AUDIO-001": Path("AUDIO-001_metrics.json"),
    "AUDIO-002": Path("AUDIO-002_metrics.json"),
    "AUDIO-003": Path("AUDIO-003_metrics.json"),
    "AUDIO-004A": Path("AUDIO-004A_v2_metrics.json"),
    "AUDIO-004Q": Path("AUDIO-004Q_metrics.json"),
    "AUDIO-004R": Path("AUDIO-004R_metrics.json"),
    "AUDIO-005": Path("AUDIO-005_metrics.json"),
    "AUDIO-005Q": Path("AUDIO-005Q_v2_metrics.json"),
}

def main():
    print("=" * 60)
    print("🔍 ASSERT ALL PASS: Verificación estricta previa a la firma")
    print("=" * 60)
    
    missing = []
    failed = []
    
    for test_id, path in REQUIRED_TESTS.items():
        if not path.exists():
            missing.append(f"{test_id} ({path})")
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            status = data.get("status") or data.get("suite_status")
            if status != "PASS":
                failed.append(f"{test_id}: status={status}")
            else:
                print(f"  ✅ {test_id}: PASS verificado")
        except Exception as e:
            failed.append(f"{test_id}: error al parsear ({e})")
            
    if missing:
        print(f"\n❌ Archivos de prueba faltantes:\n  " + "\n  ".join(missing))
    if failed:
        print(f"\n❌ Pruebas que NO pasaron:\n  " + "\n  ".join(failed))
        
    if missing or failed:
        print("\n🚫 ASSERTION FAILED: No se permite la firma ni consolidación.")
        sys.exit(1)
        
    print("\n🏆 TODOS LOS 8 TESTS VERIFICADOS (STATUS == PASS)")
    sys.exit(0)

if __name__ == "__main__":
    main()
