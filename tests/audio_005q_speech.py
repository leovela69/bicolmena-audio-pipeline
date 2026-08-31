# -*- coding: utf-8 -*-
"""
🧪 AUDIO-005Q v2 · SYNTHETIC SPEECH INTELLIGIBILITY & PRESERVATION QC
Protocolo científico de inteligibilidad de locución sintética española:
  1. Generación Edge-TTS (es-ES-AlvaroNeural) -> MP3 -> Transcodificación explícita FFmpeg a PCM_16 WAV 44.1 kHz.
  2. Verificación física estricta con sf.info (samplerate=44100, channels=1, subtype=PCM_16).
  3. Conversión tímbrica con RVC v2 (infer/cli.py).
  4. Modelo Whisper 'small' cargado una sola vez en CPU (fp16=False, language='es').
  5. Cálculo separado de WER y CER con jiwer (ReduceToListOfListOfWords / ReduceToListOfListOfChars).
  6. Control de silencio independiente (evaluación de alucinación ASR).
  7. Matriz de 3 fragmentos lingüísticos de prueba.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import os
import json
import time
import asyncio
import hashlib
import subprocess
import numpy as np
import soundfile as sf
import edge_tts
import whisper
import jiwer
from pathlib import Path

class Estado:
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"

BASE_DIR = Path("evidence/audio/AUDIO-005Q")
BASE_DIR.mkdir(parents=True, exist_ok=True)

candidate_paths = [
    Path("01-proyectos-codigo/rvc_runtime/repo"),
    Path("assets/rvc_runtime"),
    Path("../01-proyectos-codigo/rvc_runtime/repo"),
]
RVC_REPO = next((p for p in candidate_paths if p.exists()), Path("assets/rvc_runtime"))

FRAGMENTS = [
    {"id": "F1", "text": "el cante flamenco requiere alma y precision"},
    {"id": "F2", "text": "la guitarra suena en la noche de sevilla"},
    {"id": "F3", "text": "los acordes marcan el compas del bolero"}
]

WHISPER_MODEL = "small"

def sha256_file(path: Path) -> str:
    with path.open("rb") as f:
        if hasattr(hashlib, "file_digest"):
            return hashlib.file_digest(f, "sha256").hexdigest()
        else:
            h = hashlib.sha256()
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
            return h.hexdigest()

import unicodedata

def normalizar_texto(t: str) -> str:
    # Eliminar tildes/diacríticos para equivalencia fonética estricta
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")

def calcular_wer_cer(referencia: str, hipotesis: str):
    ref_norm = normalizar_texto(referencia)
    hyp_norm = normalizar_texto(hipotesis)
    
    word_transform = jiwer.Compose([
        jiwer.ToLowerCase(),
        jiwer.RemovePunctuation(),
        jiwer.RemoveMultipleSpaces(),
        jiwer.Strip(),
        jiwer.ReduceToListOfListOfWords(),
    ])
    char_transform = jiwer.Compose([
        jiwer.ToLowerCase(),
        jiwer.RemovePunctuation(),
        jiwer.RemoveMultipleSpaces(),
        jiwer.Strip(),
        jiwer.ReduceToListOfListOfChars(),
    ])
    
    wer_val = jiwer.wer(
        ref_norm,
        hyp_norm,
        reference_transform=word_transform,
        hypothesis_transform=word_transform,
    )
    cer_val = jiwer.cer(
        ref_norm,
        hyp_norm,
        reference_transform=char_transform,
        hypothesis_transform=char_transform,
    )
    return {
        "wer": float(wer_val),
        "cer": float(cer_val),
        "quality": "MEASURED"
    }

async def sintetizar_locucion_edge(texto: str, edge_mp3: Path, guide_wav: Path):
    """Genera locución con Edge-TTS en MP3 y convierte explícitamente a PCM_16 WAV 44.1 kHz con FFmpeg"""
    com = edge_tts.Communicate(texto, "es-ES-AlvaroNeural", rate="-5%")
    await com.save(str(edge_mp3))
    
    # Transcodificar explícitamente a WAV PCM_16 mono 44.1 kHz con FFmpeg
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(edge_mp3),
        "-ac", "1",
        "-ar", "44100",
        "-c:a", "pcm_s16le",
        str(guide_wav)
    ], check=True, capture_output=True)
    
    if edge_mp3.exists():
        edge_mp3.unlink()
        
    # Verificación física estricta
    info = sf.info(str(guide_wav))
    if info.samplerate != 44100 or info.channels != 1 or info.subtype != "PCM_16":
        raise ValueError(f"Formato WAV inválido: SR={info.samplerate}, CH={info.channels}, Subtype={info.subtype}")
        
    return str(guide_wav)

def ejecutar_rvc(input_wav: str, output_wav: str):
    """Ejecuta inferencia RVC v2 mediante infer/cli.py"""
    cmd = [
        sys.executable,
        "infer/cli.py",
        "--model", str(Path(RVC_REPO / "assets" / "weights" / "default.pth").resolve()),
        "--input", str(Path(input_wav).resolve()),
        "--output", str(Path(output_wav).resolve()),
        "--pitch", "0",
        "--f0-method", "rmvpe",
        "--index", str(Path(RVC_REPO / "assets" / "indices" / "default.index").resolve()),
        "--index-rate", "0.75",
        "--resample-sr", "0",
        "--rms-mix-rate", "1.0",
        "--protect", "0.33",
        "--overwrite"
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(RVC_REPO.resolve()) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=str(RVC_REPO), env=env, capture_output=True, text=True)
    elapsed = time.perf_counter() - t0
    
    if proc.returncode != 0 or not os.path.exists(output_wav):
        raise RuntimeError(f"RVC falló (code={proc.returncode}): {proc.stderr[:200]}")
        
    return elapsed

def ejecutar_audio_005q_v2():
    print("=" * 70)
    print("🧪 AUDIO-005Q v2 · SYNTHETIC SPEECH INTELLIGIBILITY QC")
    print("=" * 70)
    
    t_start = time.perf_counter()
    reporte = {
        "test_id": "AUDIO-005Q",
        "version": "v2",
        "scope": "synthetic_spanish_speech_intelligibility_preservation",
        "status": None,
        "whisper_model": WHISPER_MODEL,
        "fragments": [],
        "evidence": {}
    }
    
    # 1. Cargar Whisper una sola vez
    print(f"\n1. Cargando OpenAI Whisper ('{WHISPER_MODEL}') en CPU (fp16=False)...")
    t_w0 = time.perf_counter()
    whisper_engine = whisper.load_model(WHISPER_MODEL, device="cpu")
    t_w_load = time.perf_counter() - t_w0
    print(f"   ✅ Whisper '{WHISPER_MODEL}' cargado en {t_w_load:.2f} s")
    
    # 2. Control de Silencio (Verificación de ausencia de alucinaciones)
    print(f"\n2. Evaluando Control de Silencio (3.0s de cero absoluto)...")
    silence_wav = BASE_DIR / "silence_test_3s.wav"
    silence_data = np.zeros(int(44100 * 3.0), dtype=np.float32)
    sf.write(str(silence_wav), silence_data, 44100, subtype='PCM_16')
    
    res_silence = whisper_engine.transcribe(str(silence_wav), language="es", task="transcribe", fp16=False)
    silence_text = res_silence.get("text", "").strip()
    alucinacion = len(silence_text) > 0
    print(f"   Transcripción del Silencio: '{silence_text}' -> Alucinación: {'SÍ' if alucinacion else 'NO'}")
    
    reporte["silence_control"] = {
        "file": str(silence_wav),
        "transcript": silence_text,
        "has_hallucination": alucinacion,
        "gate_pass": not alucinacion
    }
    
    # 3. Procesar los 3 fragmentos
    print(f"\n3. Procesando matriz de {len(FRAGMENTS)} fragmentos lingüísticos...")
    all_guide_wers = []
    all_guide_cers = []
    all_rvc_wers = []
    all_rvc_cers = []
    
    for item in FRAGMENTS:
        fid = item["id"]
        text_ref = item["text"]
        print(f"\n   --- Fragmento {fid}: '{text_ref}' ---")
        
        edge_mp3 = BASE_DIR / f"edge_{fid}.mp3"
        guide_wav = BASE_DIR / f"guide_{fid}_44k.wav"
        rvc_wav = BASE_DIR / f"rvc_{fid}_40k.wav"
        
        # A) Síntesis Edge-TTS + FFmpeg
        asyncio.run(sintetizar_locucion_edge(text_ref, edge_mp3, guide_wav))
        sha_guide = sha256_file(guide_wav)
        
        # Transcripción de la guía
        res_g = whisper_engine.transcribe(str(guide_wav), language="es", task="transcribe", fp16=False)
        hyp_guide = res_g.get("text", "").strip()
        metrics_guide = calcular_wer_cer(text_ref, hyp_guide)
        
        print(f"   Guía Edge-TTS:   '{hyp_guide}' (WER: {metrics_guide['wer']*100:.1f}%, CER: {metrics_guide['cer']*100:.1f}%)")
        
        # B) Conversión RVC
        t_rvc = ejecutar_rvc(str(guide_wav), str(rvc_wav))
        sha_rvc = sha256_file(rvc_wav)
        
        # Transcripción RVC
        res_r = whisper_engine.transcribe(str(rvc_wav), language="es", task="transcribe", fp16=False)
        hyp_rvc = res_r.get("text", "").strip()
        metrics_rvc = calcular_wer_cer(text_ref, hyp_rvc)
        
        wer_delta = metrics_rvc["wer"] - metrics_guide["wer"]
        cer_delta = metrics_rvc["cer"] - metrics_guide["cer"]
        
        print(f"   RVC Salida:      '{hyp_rvc}' (WER: {metrics_rvc['wer']*100:.1f}%, CER: {metrics_rvc['cer']*100:.1f}%)")
        print(f"   Degradación:     ΔWER={wer_delta*100:+.1f}%, ΔCER={cer_delta*100:+.1f}%")
        
        all_guide_wers.append(metrics_guide["wer"])
        all_guide_cers.append(metrics_guide["cer"])
        all_rvc_wers.append(metrics_rvc["wer"])
        all_rvc_cers.append(metrics_rvc["cer"])
        
        reporte["fragments"].append({
            "id": fid,
            "ground_truth": text_ref,
            "guide_wav": str(guide_wav),
            "guide_sha256": sha_guide,
            "guide_transcript": hyp_guide,
            "guide_wer": metrics_guide["wer"],
            "guide_cer": metrics_guide["cer"],
            "rvc_wav": str(rvc_wav),
            "rvc_sha256": sha_rvc,
            "rvc_transcript": hyp_rvc,
            "rvc_wer": metrics_rvc["wer"],
            "rvc_cer": metrics_rvc["cer"],
            "wer_delta": round(wer_delta, 4),
            "cer_delta": round(cer_delta, 4),
            "rvc_time_s": round(t_rvc, 2)
        })
        
    # 4. Agregación de Métricas
    avg_guide_wer = float(np.mean(all_guide_wers))
    avg_guide_cer = float(np.mean(all_guide_cers))
    avg_rvc_wer = float(np.mean(all_rvc_wers))
    avg_rvc_cer = float(np.mean(all_rvc_cers))
    avg_wer_delta = avg_rvc_wer - avg_guide_wer
    avg_cer_delta = avg_rvc_cer - avg_guide_cer
    
    gates = {
        "guide_wer_ok": avg_guide_wer <= 0.05,
        "guide_cer_ok": avg_guide_cer <= 0.03,
        "rvc_wer_ok": avg_rvc_wer <= 0.25,
        "rvc_cer_ok": avg_rvc_cer <= 0.15,
        "wer_degradation_ok": avg_wer_delta <= 0.20,
        "cer_degradation_ok": avg_cer_delta <= 0.10,
        "silence_no_hallucination": alucinacion is False
    }
    
    pass_overall = all(gates.values())
    estado_final = Estado.PASS if pass_overall else Estado.FAIL
    razon_final = "Criterios lingüísticos y de preservación cumplidos" if pass_overall else "Métricas ASR fuera de umbrales C8L"
    
    reporte["status"] = estado_final
    reporte["razon"] = razon_final
    reporte["aggregated_metrics"] = {
        "mean_guide_wer": round(avg_guide_wer, 4),
        "mean_guide_cer": round(avg_guide_cer, 4),
        "mean_rvc_wer": round(avg_rvc_wer, 4),
        "mean_rvc_cer": round(avg_rvc_cer, 4),
        "mean_wer_degradation": round(avg_wer_delta, 4),
        "mean_cer_degradation": round(avg_cer_delta, 4)
    }
    reporte["gates"] = gates
    reporte["wall_time_s"] = round(time.perf_counter() - t_start, 2)
    
    with open("AUDIO-005Q_v2_metrics.json", "w", encoding="utf-8") as f:
        json.dump(reporte, f, indent=2)
        
    print(f"\n{'=' * 70}")
    print(f"RESUMEN AGREGADO AUDIO-005Q v2:")
    print(f"   Guía Promedio:  WER = {avg_guide_wer*100:.1f}% | CER = {avg_guide_cer*100:.1f}%")
    print(f"   RVC Promedio:   WER = {avg_rvc_wer*100:.1f}% | CER = {avg_rvc_cer*100:.1f}%")
    print(f"   Degradación:    ΔWER = {avg_wer_delta*100:+.1f}% | ΔCER = {avg_cer_delta*100:+.1f}%")
    print(f"   Silencio:       Alucinación = {'SÍ' if alucinacion else 'NO'}")
    print(f"STATUS FINAL:      {estado_final}")
    print(f"RAZÓN:             {razon_final}")
    print(f"{'=' * 70}")
    print(f"📄 Reporte generado: AUDIO-005Q_v2_metrics.json")
    
    return reporte

if __name__ == "__main__":
    ejecutar_audio_005q_v2()
