import io
import struct
import wave

import pytest

from app.services.openrouter_tts_service import _pcm_to_wav

PCM = struct.pack("<44100h", *([0] * 44100))


@pytest.fixture
def wav_bytes() -> bytes:
    return _pcm_to_wav(PCM)


def test_wav_has_riff_header(wav_bytes: bytes) -> None:
    assert wav_bytes[:4] == b"RIFF", "WAV must start with RIFF header"
    # RIFF....WAVE....fmt
    assert b"WAVE" in wav_bytes[:12], "WAV must contain WAVE format identifier"


@pytest.mark.parametrize(("getter", "expected"), [("getnchannels", 1), ("getsampwidth", 2), ("getframerate", 44100)])
def test_wav_format_parameters(wav_bytes: bytes, getter: str, expected: int) -> None:
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        assert getattr(w, getter)() == expected


def test_wav_contains_pcm_data(wav_bytes: bytes) -> None:
    data_chunk = wav_bytes[44:]  # WAV data chunk follows the ~44-byte header
    assert len(data_chunk) > 0, "WAV should contain audio data"
    assert data_chunk == PCM, "PCM data should be preserved in WAV"


def test_wav_larger_than_pcm(wav_bytes: bytes) -> None:
    assert len(wav_bytes) > len(PCM), "WAV should be larger than raw PCM"


def test_empty_pcm_produces_minimal_wav() -> None:
    wav_bytes = _pcm_to_wav(b"")
    assert wav_bytes[:4] == b"RIFF"
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        assert w.getnframes() == 0
