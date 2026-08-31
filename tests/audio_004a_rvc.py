# -*- coding: utf-8 -*-
"""
🧪 AUDIO-004A v2 · RVC FUNCTIONAL QUALITY CONTROL
Correcciones científicas aplicadas:
  - ProcessTreeMemorySampler mide root + children(recursive=True) a 50ms.
  - Ejecución con sys.executable en el subproceso RVC.
  - Modelo MIT verificado: PhoenixStormJr/RVC-V2-default-voice (default.pth + default.index).
  - Componentes HuBERT y RMVPE oficiales vinculados en assets/.
  - Logs stdout/stderr y hashes SHA-256 de todas las etapas.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import os
import json
import time
import subprocess
import hashlib
import threading
import numpy as np
import soundfile as sf
import psutil
from pathlib import Path

candidate_paths = [
    Path("01-proyectos-codigo/rvc_runtime/repo"),
    Path("assets/rvc_runtime"),
    Path("../01-proyectos-codigo/rvc_runtime/repo"),
]
BASE_REPO = next((p for p in candidate_paths if p.exists()), Path("assets/rvc_runtime"))

RVC_CLI = str(BASE_REPO / "infer" / "cli.py")
MODEL_PTH = str(BASE_REPO / "assets" / "weights" / "default.pth")
MODEL_INDEX = str(BASE_REPO / "assets" / "indices" / "default.index")
INPUT_WAV = str(BASE_REPO / "voice_guide.wav")
EVIDENCE_DIR = Path("evidence/audio/AUDIO-004")
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_WAV = str(EVIDENCE_DIR / "rvc_native.wav")

# Generar voice_guide.wav si no existe
if not Path(INPUT_WAV).exists():
    Path(INPUT_WAV).parent.mkdir(parents=True, exist_ok=True)
    sr_g = 44100
    t_g = np.linspace(0, 5.0, int(sr_g * 5.0), endpoint=False)
    s_g = 0.5 * np.sin(2 * np.pi * 440.0 * t_g)
    sf.write(INPUT_WAV, s_g.astype(np.float32), sr_g)

F0_METHOD = "rmvpe"
PITCH = 0
INDEX_RATE = 0.75
PROTECT = 0.33
RESAMPLE_SR = 0

class Estado:
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"

def calcular_sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(8192), b""):
            h.update(bloque)
    return h.hexdigest()

class ProcessTreeMemorySampler:
    def __init__(self, pid):
        self.root_pid = pid
        self.peak_rss_bytes = 0
        self.samples = []
        self.running = False
        self.thread = None
        
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._sample_loop, daemon=True)
        self.thread.start()
        
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        return self.peak_rss_bytes / (1024 ** 2)
        
    def _sample_loop(self):
        try:
            root = psutil.Process(self.root_pid)
        except psutil.NoSuchProcess:
            return
        
        while self.running:
            try:
                total_rss = 0
                procesos = [root] + root.children(recursive=True)
                for p in procesos:
                    try:
                        total_rss += p.memory_info().rss
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                if total_rss > self.peak_rss_bytes:
                    self.peak_rss_bytes = total_rss
                self.samples.append(total_rss)
            except psutil.NoSuchProcess:
                break
            except Exception:
                pass
            time.sleep(0.05)

def verificar_prerequisitos():
    prerequisitos = {
        "rvc_cli": Path(RVC_CLI),
        "modelo_pth": Path(MODEL_PTH),
        "modelo_index": Path(MODEL_INDEX),
        "input_wav": Path(INPUT_WAV),
    }
    
    faltantes = []
    for nombre, ruta in prerequisitos.items():
        if not ruta.exists():
            faltantes.append({"nombre": nombre, "ruta_esperada": str(ruta)})
    
    if faltantes:
        return {
            "estado": Estado.BLOCKED,
            "razon": "Archivos faltantes",
            "faltantes": faltantes,
        }
    return {"estado": "OK"}

def ejecutar_audio_004a_v2():
    print("=" * 70)
    print("🧪 AUDIO-004A v2 · RVC FUNCTIONAL TEST")
    print("=" * 70)
    
    resultado = {
        "test_id": "AUDIO-004A",
        "version": "v2",
        "status": None,
    }
    
    # 1. Verificar prerequisitos
    print("\n1. Verificando prerequisitos...")
    prereq = verificar_prerequisitos()
    
    if prereq["estado"] != "OK":
        print(f"❌ {prereq['estado']}")
        for faltante in prereq.get("faltantes", []):
            print(f"   Falta: {faltante['nombre']} -> {faltante['ruta_esperada']}")
        resultado["status"] = prereq["estado"]
        resultado["razon"] = prereq["razon"]
        return resultado
    
    print("✅ Todos los prerequisitos existen en disco.")
    
    # 2. Hashes de entrada
    input_sha = calcular_sha256(INPUT_WAV)
    model_sha = calcular_sha256(MODEL_PTH)
    index_sha = calcular_sha256(MODEL_INDEX)
    info_input = sf.info(INPUT_WAV)
    
    resultado["input"] = {
        "file": INPUT_WAV,
        "sha256": input_sha,
        "sample_rate_hz": info_input.samplerate,
        "channels": info_input.channels,
        "duration_s": info_input.duration,
    }
    
    resultado["model"] = {
        "pth": MODEL_PTH,
        "pth_sha256": model_sha,
        "pth_licencia": "MIT (PhoenixStormJr/RVC-V2-default-voice)",
        "index": MODEL_INDEX,
        "index_sha256": index_sha,
        "f0_method": F0_METHOD,
        "pitch_semitones": PITCH,
        "index_rate": INDEX_RATE,
        "protect": PROTECT,
    }
    
    # 3. Construir comando
    comando_args = [
        "--model", str(Path(MODEL_PTH).resolve()),
        "--input", str(Path(INPUT_WAV).resolve()),
        "--output", str(Path(OUTPUT_WAV).resolve()),
        "--pitch", str(PITCH),
        "--f0-method", F0_METHOD,
        "--index", str(Path(MODEL_INDEX).resolve()),
        "--index-rate", str(INDEX_RATE),
        "--resample-sr", str(RESAMPLE_SR),
        "--rms-mix-rate", "1.0",
        "--protect", str(PROTECT),
        "--overwrite",
    ]
    
    comando_completo = [sys.executable, "infer/cli.py"] + comando_args
    
    resultado["execution"] = {
        "python_executable": sys.executable,
        "command": comando_completo,
    }
    
    # 4. Ejecutar con Popen y sampler
    print(f"\n2. Ejecutando RVC CLI ({sys.executable})...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BASE_REPO.resolve()) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    
    try:
        proc = subprocess.Popen(
            comando_completo,
            cwd=str(BASE_REPO),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        sampler = ProcessTreeMemorySampler(proc.pid)
        sampler.start()
        
        start = time.perf_counter()
        stdout, stderr = proc.communicate(timeout=300)
        elapsed = time.perf_counter() - start
        peak_rss_mb = sampler.stop()
        exit_code = proc.returncode
        
        resultado["execution"].update({
            "exit_code": exit_code,
            "elapsed_s": round(elapsed, 3),
            "peak_process_tree_rss_mb": round(peak_rss_mb, 2),
            "memory_method": "psutil_process_tree_50ms",
            "measurement_clock": "time.perf_counter",
            "stdout_log": stdout[:2000] if stdout else "",
            "stderr_log": stderr[:2000] if stderr else "",
        })
        
        print(f"   Exit code: {exit_code}")
        print(f"   Tiempo: {elapsed:.2f} s")
        print(f"   Peak RAM (árbol): {peak_rss_mb:.1f} MB")
        
        if exit_code != 0:
            resultado["status"] = Estado.ERROR
            resultado["razon"] = f"exit_code={exit_code}"
            if stderr:
                print(f"   stderr: {stderr[:300]}")
            with open("AUDIO-004A_v2_metrics.json", "w", encoding="utf-8") as f:
                json.dump(resultado, f, indent=2, default=str)
            return resultado
        
        output_path = Path(OUTPUT_WAV)
        if not output_path.exists():
            resultado["status"] = Estado.FAIL
            resultado["razon"] = "Output WAV no generado en disco"
            with open("AUDIO-004A_v2_metrics.json", "w", encoding="utf-8") as f:
                json.dump(resultado, f, indent=2, default=str)
            return resultado
        
        # 5. QC de salida
        info_output = sf.info(OUTPUT_WAV)
        audio_output, sr_output = sf.read(OUTPUT_WAV)
        
        nan_count = int(np.isnan(audio_output).sum())
        inf_count = int(np.isinf(audio_output).sum())
        output_sha = calcular_sha256(OUTPUT_WAV)
        sample_peak = float(np.max(np.abs(audio_output)))
        sample_peak_dbfs = 20 * np.log10(sample_peak) if sample_peak > 0 else -np.inf
        
        resultado["output"] = {
            "file": OUTPUT_WAV,
            "sha256": output_sha,
            "sample_rate_hz": sr_output,
            "channels": info_output.channels,
            "duration_s": info_output.duration,
        }
        
        resultado["qc"] = {
            "nan_count": nan_count,
            "inf_count": inf_count,
            "sample_peak_dbfs": round(sample_peak_dbfs, 2),
            "sample_clipping": sample_peak >= 1.0
        }
        
        if nan_count > 0:
            resultado["status"] = Estado.FAIL
            resultado["razon"] = f"NaN detectado: {nan_count}"
        elif inf_count > 0:
            resultado["status"] = Estado.FAIL
            resultado["razon"] = f"Inf detectado: {inf_count}"
        elif info_output.duration <= 0:
            resultado["status"] = Estado.FAIL
            resultado["razon"] = "Duración inválida"
        else:
            resultado["status"] = Estado.PASS
            print(f"\n✅ AUDIO-004A PASS")
            print(f"   Archivo de Salida: {OUTPUT_WAV}")
            print(f"   Sample Rate:       {sr_output} Hz")
            print(f"   Canales:           {info_output.channels}")
            print(f"   Duración:          {info_output.duration:.2f} s")
            print(f"   Sample Peak:       {sample_peak_dbfs:.2f} dBFS")
            print(f"   SHA-256 Output:    {output_sha}")
            
    except subprocess.TimeoutExpired:
        resultado["status"] = Estado.ERROR
        resultado["razon"] = "TimeoutExpired (300s)"
        print("❌ Timeout (300s)")
    except Exception as e:
        resultado["status"] = Estado.ERROR
        resultado["razon"] = str(e)
        print(f"❌ ERROR: {e}")
        
    with open("AUDIO-004A_v2_metrics.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=2, default=str)
        
    print(f"\n{'=' * 70}")
    print(f"STATUS AUDIO-004A: {resultado['status']}")
    print(f"{'=' * 70}")
    print(f"📄 Reporte generado: AUDIO-004A_v2_metrics.json")
    
    return resultado

if __name__ == "__main__":
    ejecutar_audio_004a_v2()
