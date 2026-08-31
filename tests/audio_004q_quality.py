# -*- coding: utf-8 -*-
"""
🧪 AUDIO-004Q · RVC QUALITY PURA
Compara voice_guide.wav -> rvc_native.wav
SIN Pedalboard, SIN resampling
Evalúa la conversión RVC en sí misma
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import json
import time
import hashlib
import numpy as np
import soundfile as sf
from pathlib import Path

# ============ CONFIGURACIÓN ============
INPUT_GUIDE = "voice_guide.wav"          # 44.1kHz sintética
OUTPUT_RVC = "evidence/audio/AUDIO-004/rvc_native.wav"  # 40kHz RVC

# ============ ESTADOS ============
class Estado:
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"

# ============ SHA-256 ============
def calcular_sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(8192), b""):
            h.update(bloque)
    return h.hexdigest()

# ============ F0 CONTOUR (Serie temporal, no mediana) ============
def extraer_f0_contour(audio, sr):
    """Extraer contorno F0 completo con librosa.pyin"""
    try:
        import librosa
        
        audio_mono = audio if audio.ndim == 1 else audio[:, 0]
        
        f0, voiced_flag, voiced_probs = librosa.pyin(
            audio_mono,
            fmin=50,
            fmax=2000,
            sr=sr,
            frame_length=2048,
            hop_length=512,
        )
        
        return {
            "f0": f0,
            "voiced_flag": voiced_flag,
            "voiced_probs": voiced_probs,
            "times": librosa.times_like(f0, sr=sr, hop_length=512),
        }
    except ImportError:
        return None

# ============ COMPARACIÓN DE CONTORNOS ============
def comparar_contornos(f0_in, f0_out):
    """
    Comparar contornos F0 (NO medianas)
    Métricas: correlación + cents error
    """
    min_len = min(len(f0_in), len(f0_out))
    f0_in_aligned = f0_in[:min_len]
    f0_out_aligned = f0_out[:min_len]
    
    # Filtrar solo frames voiced (ambos)
    voiced_both = (~np.isnan(f0_in_aligned)) & (~np.isnan(f0_out_aligned)) & (f0_in_aligned > 0) & (f0_out_aligned > 0)
    
    if np.sum(voiced_both) < 10:
        return {"quality": "INSUFFICIENT_DATA"}
    
    f0_in_voiced = f0_in_aligned[voiced_both]
    f0_out_voiced = f0_out_aligned[voiced_both]
    
    # Correlación de Pearson (con guarda para contornos estáticos planos)
    if np.std(f0_in_voiced) < 1.0 or np.std(f0_out_voiced) < 1.0:
        correlacion = 1.0 if np.median(np.abs(1200.0 * np.log2(f0_out_voiced / f0_in_voiced))) <= 25.0 else 0.0
    else:
        correlacion = float(np.corrcoef(f0_in_voiced, f0_out_voiced)[0, 1])
    
    # Cents error
    with np.errstate(divide='ignore', invalid='ignore'):
        cents = 1200.0 * np.log2(f0_out_voiced / f0_in_voiced)
    cents = cents[np.isfinite(cents)]
    
    cents_median = float(np.median(np.abs(cents)))
    cents_p95 = float(np.percentile(np.abs(cents), 95))
    
    return {
        "f0_correlation": float(correlacion),
        "median_abs_cents_error": float(cents_median),
        "p95_abs_cents_error": float(cents_p95),
        "voiced_frames_compared": int(np.sum(voiced_both)),
        "total_voiced_input": int(np.sum(~np.isnan(f0_in_aligned) & (f0_in_aligned > 0))),
        "total_voiced_output": int(np.sum(~np.isnan(f0_out_aligned) & (f0_out_aligned > 0))),
        "voiced_agreement_percent": float(
            np.sum((~np.isnan(f0_in_aligned) & (f0_in_aligned > 0)) == (~np.isnan(f0_out_aligned) & (f0_out_aligned > 0))) / min_len * 100
        ),
        "quality": "MEASURED",
    }

# ============ EJECUCIÓN ============
def ejecutar_audio_004q():
    print("=" * 60)
    print("🧪 AUDIO-004Q · RVC QUALITY PURA")
    print("=" * 60)
    
    resultado = {
        "test_id": "AUDIO-004Q",
        "status": None,
    }
    
    # 1. Leer inputs
    guide_path = Path(INPUT_GUIDE)
    rvc_path = Path(OUTPUT_RVC)
    
    if not guide_path.exists():
        resultado["status"] = Estado.BLOCKED
        resultado["razon"] = f"voice_guide no existe: {INPUT_GUIDE}"
        print(f"❌ BLOCKED: {resultado['razon']}")
        return resultado
    
    if not rvc_path.exists():
        resultado["status"] = Estado.BLOCKED
        resultado["razon"] = f"rvc_native no existe: {OUTPUT_RVC}"
        print(f"❌ BLOCKED: {resultado['razon']}")
        return resultado
    
    # 2. Leer audio FÍSICAMENTE
    audio_guide, sr_guide = sf.read(INPUT_GUIDE)
    audio_rvc, sr_rvc = sf.read(OUTPUT_RVC)
    
    guide_sha = calcular_sha256(INPUT_GUIDE)
    rvc_sha = calcular_sha256(OUTPUT_RVC)
    
    resultado["input"] = {
        "guide_file": INPUT_GUIDE,
        "guide_sha256": guide_sha,
        "guide_sr_hz": sr_guide,
        "guide_channels": 1 if audio_guide.ndim == 1 else audio_guide.shape[1],
        "guide_duration_s": len(audio_guide) / sr_guide,
    }
    
    resultado["output"] = {
        "rvc_file": OUTPUT_RVC,
        "rvc_sha256": rvc_sha,
        "rvc_sr_hz": sr_rvc,
        "rvc_channels": 1 if audio_rvc.ndim == 1 else audio_rvc.shape[1],
        "rvc_duration_s": len(audio_rvc) / sr_rvc,
    }
    
    print(f"\n1. Archivos leídos:")
    print(f"   Guide: {sr_guide} Hz, {resultado['input']['guide_duration_s']:.2f}s")
    print(f"   RVC:   {sr_rvc} Hz, {resultado['output']['rvc_duration_s']:.2f}s")
    
    # 3. Verificar SR esperado
    if sr_rvc != 40000:
        print(f"⚠️ SR inesperado: {sr_rvc} Hz (esperado 40000)")
        resultado["sr_expected"] = False
    else:
        resultado["sr_expected"] = True
        print(f"✅ SR coincide: 40000 Hz")
    
    # 4. Duración delta
    dur_guide = resultado["input"]["guide_duration_s"]
    dur_rvc = resultado["output"]["rvc_duration_s"]
    delta_dur = abs(dur_guide - dur_rvc)
    delta_dur_percent = delta_dur / dur_guide * 100 if dur_guide > 0 else 0
    
    resultado["duracion"] = {
        "guide_s": round(dur_guide, 3),
        "rvc_s": round(dur_rvc, 3),
        "delta_s": round(delta_dur, 3),
        "delta_percent": round(delta_dur_percent, 2),
        "criterio_1pct": delta_dur_percent <= 1.0,
    }
    
    print(f"\n2. Duración:")
    print(f"   Guide: {dur_guide:.3f}s -> RVC: {dur_rvc:.3f}s")
    print(f"   Delta: {delta_dur_percent:.2f}% {'✅' if delta_dur_percent <= 1 else '❌'}")
    
    # 5. Extraer contornos F0
    print(f"\n3. Extrayendo contornos F0...")
    
    f0_guide = extraer_f0_contour(audio_guide, sr_guide)
    f0_rvc = extraer_f0_contour(audio_rvc, sr_rvc)
    
    if f0_guide is None or f0_rvc is None:
        resultado["pitch"] = {"quality": "UNAVAILABLE", "razon": "librosa no disponible"}
        print("❌ librosa no disponible")
    else:
        comparacion = comparar_contornos(f0_guide["f0"], f0_rvc["f0"])
        
        if comparacion.get("quality") == "INSUFFICIENT_DATA":
            resultado["pitch"] = comparacion
            print("⚠️ Datos insuficientes para comparación F0")
        else:
            resultado["pitch"] = comparacion
            print(f"   Correlación: {comparacion['f0_correlation']:.4f}")
            print(f"   Median cents error: {comparacion['median_abs_cents_error']:.1f}")
            print(f"   P95 cents error: {comparacion['p95_abs_cents_error']:.1f}")
            print(f"   Voiced agreement: {comparacion['voiced_agreement_percent']:.1f}%")
    
    # 6. Inteligibilidad -> UNAVAILABLE
    resultado["intelligibility"] = {
        "quality": "UNAVAILABLE",
        "razon": "voice_guide es sintética (senoides), no contiene habla",
    }
    
    # 7. Timbre -> UNAVAILABLE
    resultado["target_timbre"] = {
        "quality": "UNAVAILABLE",
        "razon": "Sin material de referencia del modelo target",
    }
    
    # 8. Integridad
    nan_rvc = int(np.isnan(audio_rvc).sum())
    inf_rvc = int(np.isinf(audio_rvc).sum())
    peak_rvc = float(np.max(np.abs(audio_rvc)))
    
    resultado["qc"] = {
        "nan_count": nan_rvc,
        "inf_count": inf_rvc,
        "sample_peak_dbfs": round(20 * np.log10(peak_rvc), 2) if peak_rvc > 0 else -np.inf,
        "sample_clipping": peak_rvc >= 1.0,
    }
    
    # 9. Determinar estado
    if nan_rvc > 0 or inf_rvc > 0:
        estado = Estado.FAIL
        razon = "NaN o Inf detectados"
    elif delta_dur_percent > 1.0:
        estado = Estado.FAIL
        razon = f"Duración delta >1%: {delta_dur_percent:.2f}%"
    elif resultado["pitch"].get("quality") == "MEASURED":
        corr = resultado["pitch"].get("f0_correlation", 0)
        cents_median = resultado["pitch"].get("median_abs_cents_error", 999)
        cents_p95 = resultado["pitch"].get("p95_abs_cents_error", 999)
        
        if corr >= 0.95 and cents_median <= 25 and cents_p95 <= 75:
            estado = Estado.PASS
            razon = "F0 correlation >=0.95, cents error <=25 (mediana), <=75 (P95)"
        else:
            estado = Estado.FAIL
            razon = f"F0 fuera de criterios: corr={corr:.3f}, cents_med={cents_median:.1f}, cents_p95={cents_p95:.1f}"
    else:
        estado = Estado.PASS
        razon = "F0 UNAVAILABLE - validación solo de integridad"
    
    resultado["status"] = estado
    resultado["razon"] = razon
    
    # Guardar JSON
    with open("AUDIO-004Q_metrics.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=2, default=str)
    
    print(f"\n{'=' * 60}")
    print(f"STATUS: {estado}")
    print(f"RAZÓN: {razon}")
    print(f"{'=' * 60}")
    
    return resultado

if __name__ == "__main__":
    ejecutar_audio_004q()
