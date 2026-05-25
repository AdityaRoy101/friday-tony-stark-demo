"""Local Parakeet STT provider for LiveKit Agents.

Parakeet V3 is a very fast local recognizer, but the public model variants used
by Sherpa-ONNX and Handy have different ONNX layouts. This adapter keeps
LiveKit's real-time audio transport and VAD endpointing, then decodes each
finalized speech turn locally on CPU with the matching backend.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
import sherpa_onnx
from livekit import rtc
from livekit.agents import (
    APIConnectOptions,
    DEFAULT_API_CONNECT_OPTIONS,
    LanguageCode,
    stt,
)
from livekit.agents.types import NOT_GIVEN, NotGivenOr
from livekit.agents.utils import AudioBuffer, is_given

logger = logging.getLogger("friday.stt.sherpa_parakeet")

SAMPLE_RATE = 16000
NUM_CHANNELS = 1
HANDY_LEADING_SILENCE_SECONDS = 0.25
HANDY_MAX_TOKENS_PER_STEP = 10
_HANDY_SPACE_RE = re.compile(r"\A\s|\s\B|(\s)\b")


@dataclass(frozen=True)
class SherpaParakeetConfig:
    model_dir: Path
    num_threads: int = 4
    sample_rate: int = SAMPLE_RATE
    feature_dim: int = 128
    decoding_method: str = "greedy_search"
    max_active_paths: int = 4
    provider: str = "cpu"
    model_type: str = "nemo_transducer"
    blank_penalty: float = 0.0
    language: str = "en"
    min_audio_seconds: float = 0.18
    debug: bool = False

    @property
    def encoder(self) -> Path:
        return self.model_dir / "encoder.int8.onnx"

    @property
    def decoder(self) -> Path:
        return self.model_dir / "decoder.int8.onnx"

    @property
    def joiner(self) -> Path:
        return self.model_dir / "joiner.int8.onnx"

    @property
    def tokens(self) -> Path:
        return self.model_dir / "tokens.txt"

    @property
    def handy_encoder(self) -> Path:
        return self.model_dir / "encoder-model.int8.onnx"

    @property
    def handy_decoder_joint(self) -> Path:
        return self.model_dir / "decoder_joint-model.int8.onnx"

    @property
    def handy_preprocessor(self) -> Path:
        return self.model_dir / "nemo128.onnx"

    @property
    def handy_vocab(self) -> Path:
        return self.model_dir / "vocab.txt"

    @property
    def model_name(self) -> str:
        return self.model_dir.name

    def detect_layout(self) -> str:
        sherpa_files = (self.encoder, self.decoder, self.joiner, self.tokens)
        if all(path.exists() for path in sherpa_files):
            return "sherpa"

        handy_files = (
            self.handy_encoder,
            self.handy_decoder_joint,
            self.handy_preprocessor,
            self.handy_vocab,
        )
        if all(path.exists() for path in handy_files):
            return "handy"

        missing_sherpa = ", ".join(str(path) for path in sherpa_files if not path.exists())
        missing_handy = ", ".join(str(path) for path in handy_files if not path.exists())
        raise FileNotFoundError(
            "Parakeet model directory is incomplete. Expected either Sherpa-ONNX "
            f"layout (missing: {missing_sherpa}) or Handy layout "
            f"(missing: {missing_handy})."
        )


class _ParakeetBackend(Protocol):
    name: str

    def decode(self, samples: np.ndarray) -> str:
        ...


class _SherpaOnnxBackend:
    name = "sherpa-onnx"

    def __init__(self, config: SherpaParakeetConfig) -> None:
        start = time.perf_counter()
        logger.info("Loading Sherpa-ONNX Parakeet model from %s", config.model_dir)
        self._config = config
        self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(config.encoder),
            decoder=str(config.decoder),
            joiner=str(config.joiner),
            tokens=str(config.tokens),
            num_threads=config.num_threads,
            sample_rate=config.sample_rate,
            feature_dim=config.feature_dim,
            decoding_method=config.decoding_method,
            max_active_paths=config.max_active_paths,
            blank_penalty=config.blank_penalty,
            provider=config.provider,
            model_type=config.model_type,
            debug=config.debug,
        )
        logger.info(
            "Sherpa-ONNX Parakeet ready in %.0fms",
            (time.perf_counter() - start) * 1000,
        )

    def decode(self, samples: np.ndarray) -> str:
        stream = self._recognizer.create_stream()
        stream.accept_waveform(self._config.sample_rate, samples)
        self._recognizer.decode_stream(stream)
        return stream.result.text.strip()


class _HandyOnnxBackend:
    name = "handy-onnx"

    def __init__(self, config: SherpaParakeetConfig) -> None:
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise RuntimeError(
                "Handy Parakeet layout requires onnxruntime. Run `uv sync` after "
                "installing the updated dependencies."
            ) from exc

        start = time.perf_counter()
        logger.info("Loading Handy Parakeet ONNX model from %s", config.model_dir)
        self._config = config
        self._ort = ort
        self._preprocessor = self._create_session(config.handy_preprocessor)
        self._encoder = self._create_session(config.handy_encoder)
        self._decoder_joint = self._create_session(config.handy_decoder_joint)
        self._vocab, self._blank_idx = _load_handy_vocab(config.handy_vocab)
        self._vocab_size = len(self._vocab)
        self._state1_shape = self._decoder_state_shape("input_states_1")
        self._state2_shape = self._decoder_state_shape("input_states_2")
        logger.info(
            "Handy Parakeet ONNX ready in %.0fms (blank=%s, vocab=%s)",
            (time.perf_counter() - start) * 1000,
            self._blank_idx,
            self._vocab_size,
        )

    def _create_session(self, path: Path):
        options = self._ort.SessionOptions()
        options.intra_op_num_threads = max(1, self._config.num_threads)
        options.inter_op_num_threads = 1
        options.graph_optimization_level = self._ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        return self._ort.InferenceSession(
            str(path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )

    def _decoder_state_shape(self, input_name: str) -> tuple[int, ...]:
        for model_input in self._decoder_joint.get_inputs():
            if model_input.name != input_name:
                continue
            return tuple(1 if not isinstance(dim, int) else dim for dim in model_input.shape)
        raise RuntimeError(f"Handy Parakeet model is missing decoder input {input_name!r}")

    def decode(self, samples: np.ndarray) -> str:
        samples = np.ascontiguousarray(samples, dtype=np.float32)
        if samples.size == 0:
            return ""

        leading_silence = np.zeros(
            int(self._config.sample_rate * HANDY_LEADING_SILENCE_SECONDS),
            dtype=np.float32,
        )
        samples = np.concatenate((leading_silence, samples))

        waveforms = samples.reshape(1, -1)
        waveforms_lens = np.asarray([samples.size], dtype=np.int64)
        features, features_lens = self._preprocessor.run(
            ["features", "features_lens"],
            {"waveforms": waveforms, "waveforms_lens": waveforms_lens},
        )
        encoder_outputs, encoded_lengths = self._encoder.run(
            ["outputs", "encoded_lengths"],
            {"audio_signal": features, "length": features_lens},
        )

        encodings = np.transpose(encoder_outputs, (0, 2, 1))[0]
        encoding_len = int(encoded_lengths[0])
        token_ids = self._decode_sequence(encodings, encoding_len)
        return _decode_handy_tokens(self._vocab, token_ids).strip()

    def _decode_sequence(self, encodings: np.ndarray, encoding_len: int) -> list[int]:
        state1 = np.zeros(self._state1_shape, dtype=np.float32)
        state2 = np.zeros(self._state2_shape, dtype=np.float32)
        token_ids: list[int] = []

        t = 0
        emitted_tokens = 0
        while t < encoding_len:
            target_token = token_ids[-1] if token_ids else self._blank_idx
            logits, new_state1, new_state2 = self._decode_step(
                encodings[t],
                target_token,
                state1,
                state2,
            )
            vocab_logits = logits.ravel()[: self._vocab_size]
            token = int(np.argmax(vocab_logits))

            if token != self._blank_idx:
                state1 = new_state1
                state2 = new_state2
                token_ids.append(token)
                emitted_tokens += 1

            if token == self._blank_idx or emitted_tokens == HANDY_MAX_TOKENS_PER_STEP:
                t += 1
                emitted_tokens = 0

        return token_ids

    def _decode_step(
        self,
        encoder_step: np.ndarray,
        target_token: int,
        state1: np.ndarray,
        state2: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        encoder_outputs = np.ascontiguousarray(encoder_step, dtype=np.float32).reshape(1, -1, 1)
        targets = np.asarray([[target_token]], dtype=np.int32)
        target_length = np.asarray([1], dtype=np.int32)
        outputs, _, output_state1, output_state2 = self._decoder_joint.run(
            ["outputs", "prednet_lengths", "output_states_1", "output_states_2"],
            {
                "encoder_outputs": encoder_outputs,
                "targets": targets,
                "target_length": target_length,
                "input_states_1": state1,
                "input_states_2": state2,
            },
        )
        return outputs, output_state1, output_state2


class SherpaParakeetSTT(stt.STT):
    """Local CPU STT adapter backed by Parakeet V3."""

    def __init__(self, config: SherpaParakeetConfig) -> None:
        super().__init__(
            capabilities=stt.STTCapabilities(
                # Parakeet V3 is used as a very fast offline recognizer here.
                # LiveKit wraps non-streaming STT with StreamAdapter + VAD, which
                # gives us an explicit end-of-speech flush for each user turn.
                streaming=False,
                interim_results=False,
                aligned_transcript=False,
                offline_recognize=True,
            )
        )
        self._config = config
        self._layout = config.detect_layout()
        self._backend: _ParakeetBackend | None = None
        self._decode_lock = asyncio.Lock()

    @classmethod
    def from_paths(
        cls,
        *,
        model_dir: str | Path,
        num_threads: int = 4,
        provider: str = "cpu",
        model_type: str = "nemo_transducer",
        decoding_method: str = "greedy_search",
        max_active_paths: int = 4,
        min_audio_seconds: float = 0.18,
        debug: bool = False,
    ) -> "SherpaParakeetSTT":
        return cls(
            SherpaParakeetConfig(
                model_dir=Path(model_dir).expanduser(),
                num_threads=num_threads,
                provider=provider,
                model_type=model_type,
                decoding_method=decoding_method,
                max_active_paths=max_active_paths,
                min_audio_seconds=min_audio_seconds,
                debug=debug,
            )
        )

    @property
    def model(self) -> str:
        return self._config.model_name

    @property
    def provider(self) -> str:
        if self._backend is not None:
            return self._backend.name
        return "handy-onnx" if self._layout == "handy" else "sherpa-onnx"

    def prewarm(self) -> None:
        self._get_backend()

    def stream(
        self,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> "SherpaParakeetStream":
        stream = SherpaParakeetStream(stt=self, conn_options=conn_options, language=language)
        return stream

    async def _recognize_impl(
        self,
        buffer: AudioBuffer,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions,
    ) -> stt.SpeechEvent:
        frame = _ensure_sample_rate(rtc.combine_audio_frames(buffer), self._config.sample_rate)
        text, audio_duration = await self._decode_frame(frame)
        request_id = str(uuid.uuid4())
        lang = LanguageCode(language if is_given(language) else self._config.language)
        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            request_id=request_id,
            alternatives=[
                stt.SpeechData(
                    language=lang,
                    text=text,
                    start_time=0.0,
                    end_time=audio_duration,
                    confidence=0.0,
                )
            ],
        )

    def _get_backend(self) -> _ParakeetBackend:
        if self._backend is not None:
            return self._backend

        if self._layout == "handy":
            self._backend = _HandyOnnxBackend(self._config)
        else:
            self._backend = _SherpaOnnxBackend(self._config)
        return self._backend

    async def _decode_frame(self, frame: rtc.AudioFrame) -> tuple[str, float]:
        samples = _audio_frame_to_float32(frame)
        audio_duration = len(samples) / self._config.sample_rate
        if audio_duration < self._config.min_audio_seconds:
            return "", audio_duration

        async with self._decode_lock:
            start = time.perf_counter()
            text = await asyncio.to_thread(self._decode_sync, samples)
            rms, peak = _sample_stats(samples)
            logger.info(
                "%s decoded %.2fs audio in %.0fms (rms=%.4f peak=%.4f): %s",
                self.provider,
                audio_duration,
                (time.perf_counter() - start) * 1000,
                rms,
                peak,
                text,
            )
            return text, audio_duration

    def _decode_sync(self, samples: np.ndarray) -> str:
        return self._get_backend().decode(samples)


class SherpaParakeetStream(stt.RecognizeStream):
    def __init__(
        self,
        *,
        stt: SherpaParakeetSTT,
        conn_options: APIConnectOptions,
        language: NotGivenOr[str],
    ) -> None:
        super().__init__(stt=stt, conn_options=conn_options, sample_rate=SAMPLE_RATE)
        self._stt: SherpaParakeetSTT = stt
        self._language = LanguageCode(language if is_given(language) else stt._config.language)

    async def _run(self) -> None:
        frames: list[rtc.AudioFrame] = []

        async for data in self._input_ch:
            if isinstance(data, rtc.AudioFrame):
                frames.append(data)
                continue

            if isinstance(data, self._FlushSentinel):
                await self._flush_frames(frames)
                frames.clear()

        await self._flush_frames(frames)

    async def _flush_frames(self, frames: list[rtc.AudioFrame]) -> None:
        if not frames:
            return

        request_id = str(uuid.uuid4())
        frame = rtc.combine_audio_frames(frames)
        text, audio_duration = await self._stt._decode_frame(frame)

        if text:
            self._event_ch.send_nowait(
                stt.SpeechEvent(
                    type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                    request_id=request_id,
                    alternatives=[
                        stt.SpeechData(
                            language=self._language,
                            text=text,
                            start_time=0.0,
                            end_time=audio_duration,
                            confidence=0.0,
                        )
                    ],
                )
            )

        self._event_ch.send_nowait(
            stt.SpeechEvent(
                type=stt.SpeechEventType.RECOGNITION_USAGE,
                request_id=request_id,
                alternatives=[],
                recognition_usage=stt.RecognitionUsage(audio_duration=audio_duration),
            )
        )


def _audio_frame_to_float32(frame: rtc.AudioFrame) -> np.ndarray:
    raw = frame.data.cast("b")
    pcm = np.frombuffer(raw, dtype=np.int16)
    if frame.num_channels > 1:
        pcm = pcm.reshape(-1, frame.num_channels).mean(axis=1)
    samples = pcm.astype(np.float32) / 32768.0
    return np.ascontiguousarray(samples)


def _sample_stats(samples: np.ndarray) -> tuple[float, float]:
    if samples.size == 0:
        return 0.0, 0.0
    rms = float(np.sqrt(np.mean(samples * samples)))
    peak = float(np.max(np.abs(samples)))
    return rms, peak


def _ensure_sample_rate(frame: rtc.AudioFrame, sample_rate: int) -> rtc.AudioFrame:
    if frame.sample_rate == sample_rate:
        return frame

    resampler = rtc.AudioResampler(
        frame.sample_rate,
        sample_rate,
        quality=rtc.AudioResamplerQuality.HIGH,
    )
    frames = list(resampler.push(frame))
    frames.extend(resampler.flush())
    return rtc.combine_audio_frames(frames)


def _load_handy_vocab(path: Path) -> tuple[list[str], int]:
    vocab: list[str] = []
    blank_idx: int | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        token, index_text = line.rsplit(" ", 1)
        index = int(index_text)
        while len(vocab) <= index:
            vocab.append("")
        if token == "<blk>":
            blank_idx = index
        vocab[index] = token.replace("\u2581", " ")

    if blank_idx is None:
        raise ValueError(f"Handy Parakeet vocabulary has no <blk> token: {path}")
    return vocab, blank_idx


def _decode_handy_tokens(vocab: list[str], token_ids: list[int]) -> str:
    pieces = [vocab[token_id] for token_id in token_ids if 0 <= token_id < len(vocab)]
    text = "".join(pieces)
    return _HANDY_SPACE_RE.sub(lambda match: " " if match.group(1) else "", text)
