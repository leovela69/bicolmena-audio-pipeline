# -*- coding: utf-8 -*-
"""
AUDIO-001 · DSP QUALITY CONTROL
Verifica que la cadena DSP funciona correctamente
NO certifica calidad profesional - solo valida el pipeline
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import json
import time
import numpy as np
import soundfile as sf
from pathlib import Path
from scipy import signal as scipy_signal
import psutil
import os

# ============ ESTÁNDARES ============
ESTANDARES = {
    "loudness": "ITU-R BS.1770-4 via pyloudnorm",
    "true_peak_reference": "ITU-R BS.1770-5",
}

# ============ CONFIGURACIÓN ============
SAMPLE_RATE_OBJETIVO = 48000
CANALES_OBJETIVO = 2
BIT_DEPTH = "PCM_24"
DURACION_PRUEBA = 5  # segundos

class AudioQC:
    """Motor de Quality Control para audio"""
    
    def __init__(self):
        self.metricas = {}
        
    def medir_sample_peak(self, audio: np.ndarray) -> dict:
        """Sample peak - lo que np.max realmente da"""
        peak = float(np.max(np.abs(audio)))
        dbfs = 20 * np.log10(peak) if peak > 0 else -np.inf
        
        return {
            "value": peak,
            "value_dbfs": dbfs,
            "method": "numpy_max_abs",
            "quality": "MEASURED"
        }
    
    def medir_true_peak_estimate(self, audio: np.ndarray, oversample: int = 4) -> dict:
        """
        True peak ESTIMADO mediante interpolación
        NO es certificación BS.1770-5
        4x puede subestimar 0.55-0.69 dB en peor caso
        """
        # Oversampling por interpolación (espera eje temporal primero)
        audio_up = scipy_signal.resample_poly(audio, oversample, 1, axis=0)
        peak = float(np.max(np.abs(audio_up)))
        dbtp = 20 * np.log10(peak) if peak > 0 else -np.inf
        
        return {
            "value": peak,
            "value_dbtp": dbtp,
            "method": f"scipy_resample_poly_{oversample}x",
            "quality": "ESTIMATED",
            "standard_claim": "ESTIMATE_NOT_CERTIFIED",
            "nota": "4x puede subestimar 0.55-0.69 dB (BS.1770-5)",
        }
    
    def medir_lufs(self, audio: np.ndarray, sample_rate: int) -> dict:
        """LUFS-I con pyloudnorm (BS.1770-4)"""
        try:
            import pyloudnorm as pyln
            
            meter = pyln.Meter(sample_rate)
            # pyloudnorm espera forma (muestras, canales)
            lufs = meter.integrated_loudness(audio)
            
            return {
                "value": float(lufs),
                "method": "pyloudnorm",
                "quality": "MEASURED",
                "standard": "ITU-R BS.1770-4",
            }
        except ImportError:
            return {
                "value": None,
                "method": "pyloudnorm",
                "quality": "UNAVAILABLE",
                "error": "pyloudnorm no instalado",
            }
        except Exception as e:
            return {
                "value": None,
                "method": "pyloudnorm",
                "quality": "ERROR",
                "error": str(e),
            }
    
    def medir_dc_offset(self, audio: np.ndarray) -> dict:
        """DC Offset por canal"""
        if audio.ndim == 1:
            canales = [audio]
        else:
            canales = [audio[:, i] for i in range(audio.shape[1])]
        
        offsets = []
        for i, canal in enumerate(canales):
            dc = float(np.mean(canal))
            offsets.append({
                "canal": "L" if i == 0 else "R",
                "dc_offset": dc,
                "metodo": "numpy_mean",
            })
        
        return {
            "value": offsets,
            "method": "numpy_mean",
            "quality": "MEASURED",
        }
    
    def verificar_integridad(self, audio: np.ndarray) -> dict:
        """Verificar NaN e Inf"""
        nan_count = int(np.isnan(audio).sum())
        inf_count = int(np.isinf(audio).sum())
        
        return {
            "nan_count": nan_count,
            "inf_count": inf_count,
            "sin_nan": nan_count == 0,
            "sin_inf": inf_count == 0,
            "quality": "MEASURED",
        }
    
    def verificar_clipping(self, audio: np.ndarray) -> dict:
        """Verificar clipping con separación estricta de conceptos"""
        sample_peak = float(np.max(np.abs(audio)))
        true_peak_est = self.medir_true_peak_estimate(audio)
        
        sample_clipping = sample_peak >= 1.0
        tp_overload = true_peak_est["value_dbtp"] >= 0.0
        tp_safe_margin = true_peak_est["value_dbtp"] <= -1.0
        
        return {
            "digital_sample_clipping": { "value": sample_clipping, "quality": "MEASURED" },
            "true_peak_overload": { "value": bool(tp_overload), "quality": "DERIVED_FROM_ESTIMATE" },
            "distribution_headroom_ok": { "value": bool(tp_safe_margin), "quality": "DERIVED_FROM_ESTIMATE" }
        }

def generar_audio_prueba(sample_rate=48000, duracion=5):
    """Generar audio de prueba determinista"""
    t = np.linspace(0, duracion, int(sample_rate * duracion), False)
    
    # Señal estéreo: seno 440Hz L + seno 554.37Hz R (A4 + C#5)
    audio = np.zeros((len(t), 2), dtype=np.float32)
    audio[:, 0] = 0.3 * np.sin(2 * np.pi * 440 * t)  # L: A4
    audio[:, 1] = 0.3 * np.sin(2 * np.pi * 554.37 * t)  # R: C#5
    
    return audio

def aplicar_dsp(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """Aplicar cadena Pedalboard"""
    from pedalboard import Pedalboard, HighpassFilter, PeakFilter, Compressor, Limiter
    
    board = Pedalboard([
        HighpassFilter(cutoff_frequency_hz=30.0),
        PeakFilter(cutoff_frequency_hz=12000.0, gain_db=2.0, q=0.7),
        Compressor(threshold_db=-14.0, ratio=2.0),
        Limiter(threshold_db=-0.1),
    ])
    
    audio_t = audio.T
    processed = board(audio_t, sample_rate)
    return processed.T

def ejecutar_audio_001():
    """Ejecutar AUDIO-001 completo con time.perf_counter"""
    
    print("=" * 60)
    print("🧪 AUDIO-001 · DSP QUALITY CONTROL (BASELINE OFICIAL)")
    print("=" * 60)
    
    start_total = time.perf_counter()
    qc = AudioQC()
    
    # 1. Generar audio de prueba
    print("\n1. Generando audio de prueba...")
    audio_raw = generar_audio_prueba(SAMPLE_RATE_OBJETIVO, DURACION_PRUEBA)
    
    # 2. Aplicar DSP
    print("\n2. Aplicando cadena DSP...")
    start_dsp = time.perf_counter()
    audio_master = aplicar_dsp(audio_raw, SAMPLE_RATE_OBJETIVO)
    tiempo_dsp = time.perf_counter() - start_dsp
    print(f"   Tiempo DSP: {tiempo_dsp * 1000:.2f} ms (medido con time.perf_counter)")
    
    # 3. Verificaciones
    integridad = qc.verificar_integridad(audio_master)
    sample_peak = qc.medir_sample_peak(audio_master)
    true_peak = qc.medir_true_peak_estimate(audio_master)
    lufs = qc.medir_lufs(audio_master, SAMPLE_RATE_OBJETIVO)
    dc = qc.medir_dc_offset(audio_master)
    clipping = qc.verificar_clipping(audio_master)
    
    # 4. Guardar archivo
    output_path = "AUDIO-001_master.wav"
    sf.write(output_path, audio_master, SAMPLE_RATE_OBJETIVO, subtype='PCM_24')
    
    tiempo_total = time.perf_counter() - start_total
    rtf = tiempo_dsp / DURACION_PRUEBA
    
    metricas = {
        "test_id": "AUDIO-001",
        "description": "DSP Quality Control Baseline",
        "status": "PASS" if (integridad["sin_nan"] and integridad["sin_inf"] and not clipping["digital_sample_clipping"]["value"]) else "FAIL",
        "standards": ESTANDARES,
        "metrics": {
            "sample_peak_dbfs": sample_peak,
            "true_peak_dbtp": true_peak,
            "lufs_i": lufs,
            "dc_offset": dc,
            "clipping": clipping,
            "integridad": integridad,
        },
        "performance": {
            "dsp_wall_time_ms": round(tiempo_dsp * 1000, 3),
            "total_wall_time_ms": round(tiempo_total * 1000, 3),
            "rtf": round(rtf, 6),
            "measurement_clock": "time.perf_counter"
        },
        "evidence": {
            "archivo": output_path,
            "sample_rate": SAMPLE_RATE_OBJETIVO,
            "bit_depth": BIT_DEPTH,
            "canales": CANALES_OBJETIVO,
            "duracion": DURACION_PRUEBA,
        },
    }
    
    with open("AUDIO-001_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metricas, f, indent=2, default=str)
    
    print(f"\n{'=' * 60}")
    print(f"RESULTADO FINAL: {metricas['status']}")
    print(f"{'=' * 60}")
    print(f"📄 Métricas actualizadas: AUDIO-001_metrics.json")
    
    return metricas

if __name__ == "__main__":
    resultado = ejecutar_audio_001()
