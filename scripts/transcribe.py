#!/usr/bin/env python3
"""
Awesome-Janson Transcribe Engine (Incremental & Streaming)
基於 faster-whisper 進行字詞級精準語音轉錄，支援即時串流寫入
"""
import sys
import os
import json
import time
from faster_whisper import WhisperModel

def transcribe_audio(audio_path, output_json, output_md, model_size="base", beam_size=1):
    print(f"🎙️ 正在載入 faster-whisper 模型 ({model_size})...")
    # Optimize for Apple Silicon CPU threads
    model = WhisperModel(model_size, device="cpu", compute_type="int8", cpu_threads=8)
    
    print(f"🚀 開始轉錄: {audio_path}")
    start_time = time.time()
    
    segments, info = model.transcribe(
        audio_path,
        beam_size=beam_size,
        word_timestamps=True,
        language="zh",
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500)
    )
    
    print(f"📊 偵測語言: {info.language} (信心度: {info.language_probability:.2f})")
    
    results = []
    
    with open(output_md, "w", encoding="utf-8") as f_md:
        f_md.write(f"# Transcript: {os.path.basename(audio_path)}\n\n")
        f_md.flush()
        
        seg_count = 0
        for segment in segments:
            seg_count += 1
            seg_data = {
                "id": segment.id,
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text.strip(),
                "words": [
                    {
                        "word": w.word,
                        "start": round(w.start, 2),
                        "end": round(w.end, 2),
                        "probability": round(w.probability, 2)
                    } for w in (segment.words or [])
                ]
            }
            results.append(seg_data)
            
            m, s = divmod(int(segment.start), 60)
            h, m = divmod(m, 60)
            time_str = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
            
            f_md.write(f"**[{time_str}]** {segment.text.strip()}\n")
            f_md.flush()
            
            # Periodically write JSON
            if seg_count % 25 == 0:
                with open(output_json, "w", encoding="utf-8") as f_json:
                    json.dump(results, f_json, ensure_ascii=False, indent=2)
                elapsed = time.time() - start_time
                print(f"   [進度: {time_str}] 段落: {seg_count} | 耗時: {elapsed:.1f}s | 文案: {segment.text.strip()[:25]}...")
                
    # Final JSON save
    with open(output_json, "w", encoding="utf-8") as f_json:
        json.dump(results, f_json, ensure_ascii=False, indent=2)
        
    elapsed = time.time() - start_time
    print(f"✅ 轉錄完成！共 {len(results)} 個段落，總耗時: {elapsed/60:.2f} 分鐘")
    print(f"📄 JSON: {output_json}")
    print(f"📄 Markdown: {output_md}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: transcribe.py <audio_path> [output_json] [output_md] [model_size] [beam_size]")
        sys.exit(1)
        
    audio = sys.argv[1]
    out_json = sys.argv[2] if len(sys.argv) > 2 else "transcript.json"
    out_md = sys.argv[3] if len(sys.argv) > 3 else "takes_packed.md"
    model = sys.argv[4] if len(sys.argv) > 4 else "base"
    beam = int(sys.argv[5]) if len(sys.argv) > 5 else 1
    
    transcribe_audio(audio, out_json, out_md, model, beam)
