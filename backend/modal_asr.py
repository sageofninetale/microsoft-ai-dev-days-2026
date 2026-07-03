"""
CascadeAI — VibeVoice-ASR on Modal GPU
Deploy with: modal deploy backend/modal_asr.py
"""

import modal
from pydantic import BaseModel

app = modal.App("cascadeai-asr")

# Persistent volume caches HuggingFace model weights across container restarts.
# First cold start downloads ~14GB once; all subsequent starts load from disk in ~60s.
model_volume = modal.Volume.from_name("cascadeai-model-cache", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg")
    .pip_install(
        "torch==2.3.0",
        "torchaudio==2.3.0",
        "transformers>=4.40.0",
        "huggingface_hub",
        "soundfile",
        "numpy",
        "requests",
    )
    .run_commands("pip install git+https://github.com/microsoft/VibeVoice.git")
)


class TranscribeRequest(BaseModel):
    audio_b64: str  # base64-encoded WAV bytes


@app.cls(
    image=image,
    gpu="T4",
    scaledown_window=3600,  # stays warm for 1 hour between calls
    volumes={"/model-cache": model_volume},
)
class VibeVoiceASR:

    @modal.enter()
    def load_model(self):
        import os
        import torch
        from vibevoice.modular.modeling_vibevoice_asr import VibeVoiceASRForConditionalGeneration
        from vibevoice.processor.vibevoice_asr_processor import VibeVoiceASRProcessor

        # Use the persistent volume as HuggingFace cache so weights are downloaded once
        os.environ["HF_HOME"] = "/model-cache"
        os.environ["TRANSFORMERS_CACHE"] = "/model-cache"

        print("Loading VibeVoice-ASR model...")
        self.processor = VibeVoiceASRProcessor.from_pretrained(
            "microsoft/VibeVoice-ASR",
            language_model_pretrained_name="Qwen/Qwen2.5-7B",
        )
        self.model = VibeVoiceASRForConditionalGeneration.from_pretrained(
            "microsoft/VibeVoice-ASR",
            dtype=torch.bfloat16,
            attn_implementation="sdpa",
            trust_remote_code=True,
        ).to("cuda")
        self.model.eval()
        print("VibeVoice-ASR ready on GPU.")

    @modal.fastapi_endpoint(method="POST")
    def transcribe(self, request: TranscribeRequest):
        import base64
        import os
        import tempfile
        import torch

        audio_bytes = base64.b64decode(request.audio_b64)

        # Use an auto-cleaned temp directory so the decoded audio (PHI) is guaranteed
        # removed on exit, including on exception — not left behind by a skipped unlink.
        with tempfile.TemporaryDirectory(prefix="cascade_asr_") as tmpdir:
            wav_path = os.path.join(tmpdir, "input.wav")
            with open(wav_path, "wb") as f:
                f.write(audio_bytes)

            inputs = self.processor(
                audio=[wav_path],
                sampling_rate=None,
                return_tensors="pt",
                padding=True,
                add_generation_prompt=True,
            )
            inputs = {
                k: v.to("cuda") if isinstance(v, torch.Tensor) else v
                for k, v in inputs.items()
            }

            with torch.no_grad():
                output_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=512,
                    do_sample=False,
                )

            input_length = inputs["input_ids"].shape[1]
            generated_ids = output_ids[0, input_length:]
            raw_text = self.processor.decode(generated_ids, skip_special_tokens=True)

            # Extract plain text from the structured diarized output
            try:
                segments = self.processor.post_process_transcription(raw_text)
                plain_text = " ".join(
                    seg.get("text", "").strip()
                    for seg in segments
                    if seg.get("text", "").strip()
                )
            except Exception:
                plain_text = raw_text

            return {"transcription": plain_text.strip(), "success": True}
