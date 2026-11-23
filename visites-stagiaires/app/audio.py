"""Audio : décodage, conversion en fichier lisible partout (.m4a), transcription locale par morceaux.

La transcription est découpée en tranches d'environ 5 minutes, coupées sur un silence.
Chaque tranche terminée est enregistrée : si le Mac s'éteint, on reprend où on en était.
"""

from __future__ import annotations

import platform
import re
from pathlib import Path

import numpy as np

SR = 16000
CHUNK_S = 300  # 5 minutes

# Phrases que Whisper « invente » sur les silences en français (sous-titres de vidéos).
HALLUCINATIONS = [
    r"sous-titr", r"amara\.org", r"merci d'avoir regard", r"abonnez-vous",
    r"radio-canada", r"soustitreur", r"^\W*merci\.?\W*$", r"^\W*\.\W*$",
]
_HALLU_RE = re.compile("|".join(HALLUCINATIONS), re.IGNORECASE)


def decode(path: Path) -> np.ndarray:
    """Décode n'importe quel fichier audio/vidéo en mono 16 kHz (float32), sans ffmpeg externe."""
    import av

    out = []
    with av.open(str(path)) as container:
        stream = next(s for s in container.streams if s.type == "audio")
        resampler = av.AudioResampler(format="s16", layout="mono", rate=SR)
        for frame in container.decode(stream):
            for rf in resampler.resample(frame):
                out.append(rf.to_ndarray().reshape(-1))
        for rf in resampler.resample(None):
            out.append(rf.to_ndarray().reshape(-1))
    if not out:
        return np.zeros(0, dtype=np.float32)
    return (np.concatenate(out).astype(np.float32) / 32768.0)


def duration(path: Path) -> float:
    import av

    try:
        with av.open(str(path)) as c:
            if c.duration:
                return c.duration / 1_000_000
    except Exception:
        pass
    try:
        return len(decode(path)) / SR
    except Exception:
        return 0.0


def to_m4a(src: Path, dst: Path) -> Path:
    """Convertit en AAC/.m4a : fichier compact, et la lecture permet d'avancer/reculer."""
    import av

    with av.open(str(src)) as inp, av.open(str(dst), "w", format="mp4") as out:
        in_stream = next(s for s in inp.streams if s.type == "audio")
        o = out.add_stream("aac", rate=SR * 3)  # 48 kHz
        o.layout = "mono"
        o.bit_rate = 64000
        resampler = av.AudioResampler(format="fltp", layout="mono", rate=SR * 3)
        for frame in inp.decode(in_stream):
            frame.pts = None
            for rf in resampler.resample(frame):
                for pkt in o.encode(rf):
                    out.mux(pkt)
        for rf in resampler.resample(None):
            for pkt in o.encode(rf):
                out.mux(pkt)
        for pkt in o.encode(None):
            out.mux(pkt)
    return dst


def split_points(audio: np.ndarray, chunk_s: int = CHUNK_S, search_s: int = 8) -> list[tuple[int, int]]:
    """Découpe en tranches d'environ chunk_s secondes, en coupant sur le moment le plus calme."""
    n = len(audio)
    bounds, start = [], 0
    win = int(0.2 * SR)
    while start < n:
        target = start + chunk_s * SR
        if target >= n - 30 * SR:  # moins de 30 s restantes : on garde tout
            bounds.append((start, n))
            break
        lo, hi = max(start, target - search_s * SR), min(n, target + search_s * SR)
        seg = audio[lo:hi]
        k = len(seg) // win
        if k > 1:
            energy = (seg[: k * win].reshape(k, win) ** 2).mean(axis=1)
            cut = lo + int(np.argmin(energy)) * win + win // 2
        else:
            cut = target
        bounds.append((start, cut))
        start = cut
    return bounds


def is_hallucination(text: str) -> bool:
    return bool(_HALLU_RE.search(text.strip())) or len(text.strip()) == 0


def engine_name(pref: str = "auto") -> str:
    if pref in ("mlx", "faster-whisper"):
        return pref
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        try:
            import mlx_whisper  # noqa: F401
            return "mlx"
        except ImportError:
            pass
    return "faster-whisper"


MLX_REPOS = {
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "tiny": "mlx-community/whisper-tiny",
}


class Transcriber:
    def __init__(self, engine: str, model: str, language: str = "fr", prompt: str = ""):
        self.engine = engine
        self.model_name = model
        self.language = language
        self.prompt = prompt
        self._fw = None

    def release(self):
        """Libère la mémoire occupée par le modèle de transcription."""
        import gc

        self._fw = None
        if self.engine == "mlx":
            try:
                from mlx_whisper.transcribe import ModelHolder

                ModelHolder.model = None
                ModelHolder.model_path = None
                import mlx.core as mx

                (getattr(mx, "clear_cache", None) or mx.metal.clear_cache)()
            except Exception:
                pass
        gc.collect()

    def _load_fw(self):
        if self._fw is None:
            from faster_whisper import WhisperModel

            self._fw = WhisperModel(self.model_name, device="auto", compute_type="int8")
        return self._fw

    def transcribe_chunk(self, audio: np.ndarray, offset_s: float) -> list[dict]:
        segs = []
        if self.engine == "mlx":
            import mlx_whisper

            repo = MLX_REPOS.get(self.model_name, self.model_name)
            res = mlx_whisper.transcribe(
                audio, path_or_hf_repo=repo, language=self.language,
                initial_prompt=self.prompt or None, condition_on_previous_text=False,
            )
            raw = [(s["start"], s["end"], s["text"], s.get("no_speech_prob", 0)) for s in res.get("segments", [])]
        else:
            model = self._load_fw()
            it, _info = model.transcribe(
                audio, language=self.language, initial_prompt=self.prompt or None,
                vad_filter=True, condition_on_previous_text=False, beam_size=5,
            )
            raw = [(s.start, s.end, s.text, s.no_speech_prob) for s in it]
        for start, end, text, nsp in raw:
            text = (text or "").strip()
            if is_hallucination(text) or nsp > 0.9:
                continue
            segs.append({
                "debut": round(offset_s + float(start), 2),
                "fin": round(offset_s + float(end), 2),
                "texte": text,
            })
        return segs
