# -*- coding: utf-8 -*-
"""
🧪 AUDIO-003 · NEURAL GENERATION & TRACEABILITY PROTOCOL
Ejecuta la inferencia real de MusicGen Small sobre CPU:
  - Guarda 3 etapas: RAW (32kHz mono) -> Resampled (48kHz mono) -> Master (48kHz dual-mono PCM_24).
  - Mide tiempos con time.perf_counter() y memoria RSS con psutil.
  - Genera SHA256 de los archivos y emite audio_003_evidence.json / AUDIO-003_metrics.json.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import os
import time
import json
import torch
import numpy as np
import psutil
import soundfile as sf
import hashlib
from scipy import signal as scipy_signal
from transformers import AutoProcessor, MusicgenForConditionalGeneration

# ==========================================
# CONFIGURACIÓN AUDIO-003
# ==========================================
MODEL_ID = "facebook/musicgen-small"
PROMPT = "acoustic flamenco guitar with warm bolero house beat and upright bass"
SEED = 20260831
NATIVE_SR = 32000
TARGET_SR = 48000
DEVICE = "cpu"
MAX_NEW_TOKENS = 256 # ~5.12 segundos

print("🧪 INICIANDO PROTOCOLO AUDIO-003: NEURAL GENERATION TRACEABLE")
print("=" * 70)

# 1. Carga del Modelo
print(f"🔍 Cargando {MODEL_ID} en {DEVICE.upper()} (FP32)...")
start_load = time.perf_counter()
process = psutil.Process(os.getpid())
ram_before_load = process.memory_info().rss / (1024 * 1024)

try:
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    model = MusicgenForConditionalGeneration.from_pretrained(
        MODEL_ID, 
        torch_dtype=torch.float32
    )
    model.to(DEVICE)
    model.generation_config.do_sample = True
    model.generation_config.top_k = 250
    
    ram_after_load = process.memory_info().rss / (1024 * 1024)
    load_time = time.perf_counter() - start_load
    print(f"   ✅ Modelo cargado. RAM usada: {ram_after_load - ram_before_load:.1f} MB | Tiempo: {load_time:.2f}s")
except Exception as e:
    print(f"   🚫 ERROR: Fallo al cargar el modelo: {e}")
    sys.exit(1)

# 2. Preparación de la Inferencia
print("\n🎹 Preparando inferencia...")
torch.manual_seed(SEED)
np.random.seed(SEED)

inputs = processor(
    text=[PROMPT],
    padding=True,
    return_tensors="pt"
).to(DEVICE)

# 3. Ejecución de la Inferencia
print("⚙️ Ejecutando generación neuronal (autoregressive audio-token LM)...")
start_gen = time.perf_counter()
ram_before_gen = process.memory_info().rss / (1024 * 1024)

with torch.no_grad():
    audio_values = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS)

gen_time = time.perf_counter() - start_gen
ram_max = process.memory_info().rss / (1024 * 1024)

# 4. Decodificación y Guardado del RAW (Evidencia Crítica)
print("💾 Decodificando y guardando stem crudo (NATIVO)...")
raw_audio = audio_values[0, 0].cpu().numpy()
generated_samples = len(raw_audio)
duration_gen = generated_samples / NATIVE_SR
rtf = gen_time / duration_gen

raw_filename = "raw_musicgen_32k.wav"
sf.write(raw_filename, raw_audio, NATIVE_SR, subtype='PCM_16')
print(f"   ✅ Guardado: {raw_filename} ({NATIVE_SR} Hz, Mono, {duration_gen:.2f}s)")

# 5. Resampling Explícito (32k -> 48k: ratio 3/2)
print("🔄 Resampling explícito (32 kHz → 48 kHz: up=3, down=2) con scipy.signal.resample_poly...")
audio_48k = scipy_signal.resample_poly(raw_audio, 3, 2)

resampled_filename = "resampled_musicgen_48k.wav"
sf.write(resampled_filename, audio_48k, TARGET_SR, subtype='PCM_24')
print(f"   ✅ Guardado: {resampled_filename} ({TARGET_SR} Hz, Mono)")

# 6. Conversión a Estéreo (Dual Mono - Transparencia total)
print("🔀 Expandiendo a estéreo (DUAL MONO: L=R)...")
audio_48k_stereo = np.vstack((audio_48k, audio_48k)) # [2, samples]

# 7. Procesamiento DSP C8L (Spotify Pedalboard)
print("🎛️ Aplicando cadena DSP C8L (Spotify Pedalboard)...")
from pedalboard import Pedalboard, HighpassFilter, PeakFilter, Compressor, Limiter

board_instrumental = Pedalboard([
    HighpassFilter(cutoff_frequency_hz=30.0),
    PeakFilter(cutoff_frequency_hz=12000.0, gain_db=2.0, q=0.7),
    Compressor(threshold_db=-14.0, ratio=2.0),
    Limiter(threshold_db=-0.1)
])

master_audio = board_instrumental(audio_48k_stereo, TARGET_SR)

master_filename = "neural_flamenco_bolero_master.wav"
sf.write(master_filename, master_audio.T, TARGET_SR, subtype='PCM_24')
print(f"   ✅ Guardado: {master_filename} ({TARGET_SR} Hz, Estéreo Dual, PCM_24)")

# 8. QC y Métricas
print("📊 Ejecutando QC (Quality Control)...")
sample_peak_linear = float(np.max(np.abs(master_audio)))
sample_peak_dbfs = 20 * np.log10(sample_peak_linear) if sample_peak_linear > 0 else -96.0

# True Peak Estimate (4x oversampling)
audio_192k = scipy_signal.resample_poly(master_audio, 4, 1, axis=1)
true_peak_linear = float(np.max(np.abs(audio_192k)))
true_peak_dbtp = 20 * np.log10(true_peak_linear) if true_peak_linear > 0 else -96.0

# LUFS con pyloudnorm
try:
    import pyloudnorm as pyln
    meter = pyln.Meter(TARGET_SR)
    lufs_val = float(meter.integrated_loudness(master_audio.T))
except Exception:
    lufs_val = None

nan_count = int(np.isnan(master_audio).sum())
inf_count = int(np.isinf(master_audio).sum())

# SHA256 de los archivos
def calcular_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()

raw_sha256 = calcular_sha256(raw_filename)
resampled_sha256 = calcular_sha256(resampled_filename)
master_sha256 = calcular_sha256(master_filename)

# 9. Generación del JSON de Evidencia (AUDIO-003)
evidence_report = {
    "test_id": "AUDIO-003",
    "status": "PASS" if (nan_count == 0 and inf_count == 0 and sample_peak_linear < 1.0) else "FAIL",
    "generation": {
        "model_id": MODEL_ID,
        "model_class": "MusicgenForConditionalGeneration",
        "architecture": "autoregressive audio-token LM over EnCodec",
        "prompt": PROMPT,
        "seed": SEED,
        "device": DEVICE,
        "native_sample_rate_hz": NATIVE_SR,
        "native_channels": 1,
        "generated_samples": generated_samples,
        "duration_sec": round(duration_gen, 3),
        "generation_time_sec": round(gen_time, 3),
        "rtf": round(rtf, 3),
        "ram_load_mb": round(ram_after_load - ram_before_load, 1),
        "ram_peak_mb": round(ram_max, 1),
        "measurement_clock": "time.perf_counter"
    },
    "resampling": {
        "source_hz": NATIVE_SR,
        "target_hz": TARGET_SR,
        "rational_ratio": "3/2",
        "method": "scipy.signal.resample_poly (sinc polyphase)"
    },
    "stereo": {
        "input_channels": 1,
        "output_channels": 2,
        "method": "dual_mono (L=R duplication)"
    },
    "mastering": {
        "engine": "spotify/pedalboard",
        "sample_rate_hz": TARGET_SR,
        "subtype": "PCM_24"
    },
    "qc": {
        "sample_peak_dbfs": round(sample_peak_dbfs, 3),
        "true_peak_estimate_dbtp": round(true_peak_dbtp, 3),
        "true_peak_quality": "ESTIMATED",
        "true_peak_method": "scipy.signal.resample_poly_4x",
        "lufs_i": round(lufs_val, 3) if lufs_val is not None else None,
        "nan_count": nan_count,
        "inf_count": inf_count,
        "sample_clipping": sample_peak_linear >= 1.0
    },
    "evidence": {
        "raw_musicgen_wav": raw_filename,
        "raw_sha256": raw_sha256,
        "resampled_wav": resampled_filename,
        "resampled_sha256": resampled_sha256,
        "master_wav": master_filename,
        "master_sha256": master_sha256
    }
}

print("\n" + "=" * 70)
print("📄 REPORTE DE EVIDENCIA AUDIO-003 (JSON)")
print("=" * 70)
print(json.dumps(evidence_report, indent=2))

with open("AUDIO-003_metrics.json", "w", encoding="utf-8") as f:
    json.dump(evidence_report, f, indent=2)

with open("audio_003_evidence.json", "w", encoding="utf-8") as f:
    json.dump(evidence_report, f, indent=2)

print("\n💾 Reportes guardados: AUDIO-003_metrics.json y audio_003_evidence.json")
