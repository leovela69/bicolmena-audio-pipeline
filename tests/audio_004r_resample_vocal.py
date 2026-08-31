# -*- coding: utf-8 -*-
"""
🧪 AUDIO-004R · VOCAL RESAMPLING QC (40.000 Hz -> 48.000 Hz)
Resampling polifásico racional exacto 6/5 para la pista vocal de RVC:
  - Input: rvc_native.wav (40.000 Hz)
  - Algoritmo: scipy.signal.resample_poly (up=6, down=5)
  - Output: rvc_resampled_48k.wav (48.000 Hz, PCM_24)
  - Verificación: muestras exactas, delta RMS, delta Peak, 0 NaN, 0 Inf, SHA-256
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import os
import json
import time
import math
import hashlib
import numpy as np
import soundfile as sf
from scipy import signal
from pathlib import Path

INPUT_WAV = r"evidence\audio\AUDIO-004\rvc_native.wav"
OUTPUT_WAV = r"evidence\audio\AUDIO-004\rvc_resampled_48k.wav"
TARGET_SR = 48000

def calcular_sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(8192), b""):
            h.update(bloque)
    return h.hexdigest()

def ejecutar_audio_004r():
    print("=" * 70)
    print("🧪 AUDIO-004R · VOCAL RESAMPLING QC (40 kHz -> 48 kHz)")
    print("=" * 70)
    
    t_start = time.perf_counter()
    reporte = {
        "test_id": "AUDIO-004R",
        "scope": "polyphase_vocal_resampling_exact_ratio",
        "status": None,
        "input": {},
        "resampling": {},
        "output": {},
        "qc": {},
        "evidence": {}
    }

    if not os.path.exists(INPUT_WAV):
        reporte["status"] = "BLOCKED"
        reporte["razon"] = f"Archivo de entrada no existe: {INPUT_WAV}"
        return reporte

    # 1. Leer audio físicamente
    audio_in, sr_in = sf.read(INPUT_WAV)
    channels = 1 if audio_in.ndim == 1 else audio_in.shape[1]
    samples_in = len(audio_in)
    dur_in = samples_in / sr_in
    sha_in = calcular_sha256(INPUT_WAV)

    print(f"\n1. Audio de Entrada:")
    print(f"   Archivo:     {INPUT_WAV}")
    print(f"   Sample Rate: {sr_in} Hz")
    print(f"   Muestras:    {samples_in} frames ({dur_in:.3f} s)")
    print(f"   SHA-256:     {sha_in}")

    # 2. Ratio racional exacto
    gcd_val = math.gcd(int(sr_in), TARGET_SR)
    up = TARGET_SR // gcd_val
    down = int(sr_in) // gcd_val
    expected_samples = math.ceil(samples_in * up / down)

    print(f"\n2. Cálculo de Factor Polifásico:")
    print(f"   MCD({sr_in}, {TARGET_SR}) = {gcd_val}")
    print(f"   Ratio Exacto: up={up}, down={down} ({up}/{down})")
    print(f"   Muestras Esperadas: {expected_samples}")

    # 3. Ejecutar Resampling Polifásico
    t_resample_0 = time.perf_counter()
    audio_out = signal.resample_poly(audio_in, up=up, down=down)
    t_resample_elapsed = time.perf_counter() - t_resample_0
    samples_out = len(audio_out)
    dur_out = samples_out / TARGET_SR
    rtf = t_resample_elapsed / dur_out if dur_out > 0 else 0.0

    print(f"\n3. Ejecución de Resampling:")
    print(f"   Tiempo de cómputo: {t_resample_elapsed*1000.0:.2f} ms")
    print(f"   RTF:               {rtf:.6f} (~{1.0/rtf:.0f}x tiempo real)")
    print(f"   Muestras Reales:   {samples_out} (Esperadas: {expected_samples})")

    # 4. Guardar WAV 48k PCM_24
    os.makedirs(os.path.dirname(OUTPUT_WAV), exist_ok=True)
    sf.write(OUTPUT_WAV, audio_out.astype(np.float32), TARGET_SR, subtype="PCM_24")
    sha_out = calcular_sha256(OUTPUT_WAV)

    # 5. Métricas de Fidelidad
    rms_in = float(np.sqrt(np.mean(audio_in**2)))
    rms_out = float(np.sqrt(np.mean(audio_out**2)))
    delta_rms_db = float(20 * np.log10(rms_out / rms_in)) if rms_in > 0 and rms_out > 0 else 0.0

    peak_in = float(np.max(np.abs(audio_in)))
    peak_out = float(np.max(np.abs(audio_out)))
    peak_in_dbfs = float(20 * np.log10(peak_in)) if peak_in > 0 else -np.inf
    peak_out_dbfs = float(20 * np.log10(peak_out)) if peak_out > 0 else -np.inf
    delta_peak_db = peak_out_dbfs - peak_in_dbfs

    nan_count = int(np.isnan(audio_out).sum())
    inf_count = int(np.isinf(audio_out).sum())
    dc_offset = float(np.mean(audio_out))

    print(f"\n4. Control de Calidad (QC):")
    print(f"   Delta RMS:         {delta_rms_db:+.4f} dB")
    print(f"   Delta Peak:        {delta_peak_db:+.4f} dB ({peak_in_dbfs:.2f} -> {peak_out_dbfs:.2f} dBFS)")
    print(f"   DC Offset:         {dc_offset:+.8f}")
    print(f"   NaN/Inf:           {nan_count}/{inf_count}")

    pass_criteria = (
        samples_out == expected_samples and
        nan_count == 0 and
        inf_count == 0 and
        abs(delta_rms_db) <= 0.1 and
        peak_out < 1.0
    )

    reporte["status"] = "PASS" if pass_criteria else "FAIL"
    reporte["input"] = {
        "file": INPUT_WAV,
        "sha256": sha_in,
        "sample_rate_hz": int(sr_in),
        "samples": samples_in,
        "duration_s": round(dur_in, 4),
        "peak_dbfs": round(peak_in_dbfs, 2)
    }
    reporte["resampling"] = {
        "source_hz": int(sr_in),
        "target_hz": TARGET_SR,
        "rational_ratio": f"{up}/{down}",
        "method": "scipy.signal.resample_poly (sinc polyphase FIR)",
        "wall_time_ms": round(t_resample_elapsed * 1000.0, 2),
        "rtf": round(rtf, 6),
        "clock": "time.perf_counter"
    }
    reporte["output"] = {
        "file": OUTPUT_WAV,
        "sha256": sha_out,
        "sample_rate_hz": TARGET_SR,
        "samples": samples_out,
        "duration_s": round(dur_out, 4),
        "subtype": "PCM_24",
        "peak_dbfs": round(peak_out_dbfs, 2)
    }
    reporte["qc"] = {
        "samples_exact": samples_out == expected_samples,
        "delta_rms_db": round(delta_rms_db, 4),
        "delta_peak_db": round(delta_peak_db, 4),
        "nan_count": nan_count,
        "inf_count": inf_count,
        "dc_offset": round(dc_offset, 8),
        "sample_clipping": peak_out >= 1.0
    }

    with open("AUDIO-004R_metrics.json", "w", encoding="utf-8") as f:
        json.dump(reporte, f, indent=2)

    print(f"\n{'=' * 70}")
    print(f"STATUS FINAL AUDIO-004R: {reporte['status']}")
    print(f"{'=' * 70}")
    print(f"📄 Reporte generado: AUDIO-004R_metrics.json")
    return reporte

if __name__ == "__main__":
    ejecutar_audio_004r()
