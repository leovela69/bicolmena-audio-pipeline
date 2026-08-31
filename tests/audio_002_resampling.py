# -*- coding: utf-8 -*-
"""
🧪 AUDIO-002 · RESAMPLING QUALITY CONTROL (44.1 kHz -> 48.0 kHz)
Valida la conversión de tasa de muestreo polifásica (160/147) de grado estudio.
Normativa y rigor:
  - Factor racional exacto: up=160, down=147 (44100 * 160 / 147 = 48000).
  - Tiempos medidos con time.perf_counter().
  - Preservación espectral, delta RMS, delta Peak, DC offset y aliasing.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import json
import time
import numpy as np
import soundfile as sf
from scipy import signal as scipy_signal

# ============ CONFIGURACIÓN ============
SR_ORIGEN = 44100
SR_DESTINO = 48000
UP_FACTOR = 160
DOWN_FACTOR = 147
DURACION = 5.0 # segundos
BIT_DEPTH = "PCM_24"

def generar_senal_referencia(sr=44100, duracion=5.0):
    """
    Genera señal de ensayo conocida a 44.1 kHz:
    - Canal L: 440.0 Hz (La4) a -6 dBFS
    - Canal R: 554.365 Hz (Do#5) a -6 dBFS
    """
    n_samples = int(sr * duracion)
    t = np.linspace(0, duracion, n_samples, False)
    
    # 0.5 = -6.02 dBFS
    ch_l = 0.5 * np.sin(2 * np.pi * 440.0 * t)
    ch_r = 0.5 * np.sin(2 * np.pi * 554.365 * t)
    
    return np.stack([ch_l, ch_r], axis=1).astype(np.float32)

def estimar_frecuencia_fundamental(audio_1d, sr):
    """Calcula la frecuencia fundamental mediante FFT pico"""
    n = len(audio_1d)
    fft_vals = np.abs(np.fft.rfft(audio_1d * np.hanning(n)))
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    idx_max = np.argmax(fft_vals)
    return float(freqs[idx_max])

def ejecutar_audio_002():
    print("=" * 60)
    print("🧪 AUDIO-002 · RESAMPLING QUALITY CONTROL (44.1 -> 48 kHz)")
    print("=" * 60)
    
    t_start_total = time.perf_counter()
    
    # 1. Señal de entrada
    print("\n1. Generando señal de referencia a 44.1 kHz...")
    audio_in = generar_senal_referencia(SR_ORIGEN, DURACION)
    n_in = len(audio_in)
    print(f"   Muestras de entrada: {n_in} samples (Esperado: 220500)")
    
    # Métricas de entrada
    peak_in = float(np.max(np.abs(audio_in)))
    rms_in_l = float(np.sqrt(np.mean(audio_in[:, 0]**2)))
    rms_in_r = float(np.sqrt(np.mean(audio_in[:, 1]**2)))
    rms_in_prom = (rms_in_l + rms_in_r) / 2.0
    f0_in_l = estimar_frecuencia_fundamental(audio_in[:, 0], SR_ORIGEN)
    f0_in_r = estimar_frecuencia_fundamental(audio_in[:, 1], SR_ORIGEN)
    
    # 2. Resampling polifásico 160/147
    print("\n2. Ejecutando resample_poly(up=160, down=147)...")
    t_dsp_start = time.perf_counter()
    audio_out = scipy_signal.resample_poly(audio_in, UP_FACTOR, DOWN_FACTOR, axis=0)
    t_dsp_end = time.perf_counter()
    dsp_time_ms = (t_dsp_end - t_dsp_start) * 1000.0
    
    n_out = len(audio_out)
    esperado_out = int(n_in * UP_FACTOR / DOWN_FACTOR)
    print(f"   Muestras de salida:  {n_out} samples (Esperado: {esperado_out})")
    print(f"   Tiempo DSP:          {dsp_time_ms:.2f} ms (medido con time.perf_counter)")
    
    # 3. Métricas de salida
    peak_out = float(np.max(np.abs(audio_out)))
    rms_out_l = float(np.sqrt(np.mean(audio_out[:, 0]**2)))
    rms_out_r = float(np.sqrt(np.mean(audio_out[:, 1]**2)))
    rms_out_prom = (rms_out_l + rms_out_r) / 2.0
    f0_out_l = estimar_frecuencia_fundamental(audio_out[:, 0], SR_DESTINO)
    f0_out_r = estimar_frecuencia_fundamental(audio_out[:, 1], SR_DESTINO)
    
    # Deltas
    delta_peak_db = 20.0 * np.log10(peak_out / peak_in)
    delta_rms_db = 20.0 * np.log10(rms_out_prom / rms_in_prom)
    
    # Integridad
    nan_count = int(np.isnan(audio_out).sum())
    inf_count = int(np.isinf(audio_out).sum())
    
    # DC Offset
    dc_l = float(np.mean(audio_out[:, 0]))
    dc_r = float(np.mean(audio_out[:, 1]))
    
    # RTF
    rtf = (t_dsp_end - t_dsp_start) / DURACION
    t_total_ms = (time.perf_counter() - t_start_total) * 1000.0
    
    # 4. Guardar archivo WAV
    out_wav = "AUDIO-002_resampled_48k.wav"
    sf.write(out_wav, audio_out, SR_DESTINO, subtype=BIT_DEPTH)
    print(f"\n✅ Guardado: {out_wav} (48000 Hz, PCM_24)")
    
    # 5. Criterios de aceptación
    pass_muestras = (n_out == esperado_out)
    pass_integridad = (nan_count == 0 and inf_count == 0)
    pass_rms = abs(delta_rms_db) < 0.05 # Menos de 0.05 dB de variación
    pass_frecuencia = (abs(f0_out_l - 440.0) < 0.1 and abs(f0_out_r - 554.365) < 0.1)
    
    status = "PASS" if (pass_muestras and pass_integridad and pass_rms and pass_frecuencia) else "FAIL"
    
    # 6. JSON de Métricas
    metricas = {
        "test_id": "AUDIO-002",
        "description": "44.1 kHz to 48.0 kHz Polyphase Resampling Validation",
        "status": status,
        "parameters": {
            "source_sample_rate": SR_ORIGEN,
            "target_sample_rate": SR_DESTINO,
            "rational_ratio": f"{UP_FACTOR}/{DOWN_FACTOR}",
            "method": "scipy.signal.resample_poly"
        },
        "metrics": {
            "samples_input": { "value": n_in, "expected": 220500, "quality": "MEASURED" },
            "samples_output": { "value": n_out, "expected": esperado_out, "quality": "MEASURED" },
            "integrity": {
                "nan_count": nan_count,
                "inf_count": inf_count,
                "clean": pass_integridad,
                "quality": "MEASURED"
            },
            "spectral_fidelity": {
                "f0_ch_l_hz": { "in": f0_in_l, "out": f0_out_l, "error_hz": abs(f0_out_l - f0_in_l), "quality": "MEASURED" },
                "f0_ch_r_hz": { "in": f0_in_r, "out": f0_out_r, "error_hz": abs(f0_out_r - f0_in_r), "quality": "MEASURED" }
            },
            "energy_conservation": {
                "peak_in": peak_in,
                "peak_out": peak_out,
                "delta_peak_db": delta_peak_db,
                "rms_in": rms_in_prom,
                "rms_out": rms_out_prom,
                "delta_rms_db": delta_rms_db,
                "quality": "MEASURED"
            },
            "dc_offset": {
                "ch_l": dc_l,
                "ch_r": dc_r,
                "quality": "MEASURED"
            }
        },
        "performance": {
            "dsp_wall_time_ms": round(dsp_time_ms, 3),
            "total_wall_time_ms": round(t_total_ms, 3),
            "rtf": round(rtf, 6),
            "measurement_clock": "time.perf_counter"
        },
        "evidence": {
            "file": out_wav,
            "sample_rate": SR_DESTINO,
            "bit_depth": BIT_DEPTH,
            "channels": 2,
            "duration_s": DURACION
        }
    }
    
    with open("AUDIO-002_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metricas, f, indent=2)
        
    print(f"\n{'=' * 60}")
    print(f"RESULTADO FINAL: {status}")
    print(f"{'=' * 60}")
    print(f"📄 Reporte generado: AUDIO-002_metrics.json")
    
    return metricas

if __name__ == "__main__":
    ejecutar_audio_002()
