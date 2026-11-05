"""Tests for WAV wrapping in OpenRouter TTS service."""

import io
import struct
import wave

from app.services.openrouter_tts_service import _pcm_to_wav


class TestPcmToWav:
    """Verify that _pcm_to_wav produces valid WAV with correct headers."""

    def _make_fake_pcm(self, duration_seconds=1, sample_rate=44100):
        """Generate silent 16-bit mono PCM for testing."""
        n_samples = sample_rate * duration_seconds
        return struct.pack(f"<{n_samples}h", *[0] * n_samples)

    def test_wav_has_riff_header(self):
        pcm = self._make_fake_pcm()
        wav_bytes = _pcm_to_wav(pcm)
        assert wav_bytes[:4] == b"RIFF", "WAV must start with RIFF header"

    def test_wav_has_wav_format(self):
        pcm = self._make_fake_pcm()
        wav_bytes = _pcm_to_wav(pcm)
        # RIFF....WAVE....fmt
        assert b"WAVE" in wav_bytes[:12], "WAV must contain WAVE format identifier"

    def test_wav_mono(self):
        pcm = self._make_fake_pcm()
        wav_bytes = _pcm_to_wav(pcm)
        wf = io.BytesIO(wav_bytes)
        with wave.open(wf, "rb") as w:
            assert w.getnchannels() == 1, "WAV should be mono"

    def test_wav_16bit(self):
        pcm = self._make_fake_pcm()
        wav_bytes = _pcm_to_wav(pcm)
        wf = io.BytesIO(wav_bytes)
        with wave.open(wf, "rb") as w:
            assert w.getsampwidth() == 2, "WAV should be 16-bit"

    def test_wav_44100hz(self):
        pcm = self._make_fake_pcm()
        wav_bytes = _pcm_to_wav(pcm)
        wf = io.BytesIO(wav_bytes)
        with wave.open(wf, "rb") as w:
            assert w.getframerate() == 44100, "WAV should be 44100 Hz"

    def test_wav_contains_pcm_data(self):
        pcm = self._make_fake_pcm()
        wav_bytes = _pcm_to_wav(pcm)
        # WAV data chunk is after headers (~44 bytes for minimal WAV)
        data_chunk = wav_bytes[44:]
        assert len(data_chunk) > 0, "WAV should contain audio data"
        # The PCM data should be present in the WAV
        assert data_chunk == pcm, "PCM data should be preserved in WAV"

    def test_wav_larger_than_pcm(self):
        """WAV file should be slightly larger than raw PCM due to headers."""
        pcm = self._make_fake_pcm()
        wav_bytes = _pcm_to_wav(pcm)
        assert len(wav_bytes) > len(pcm), "WAV should be larger than raw PCM"

    def test_empty_pcm_produces_minimal_wav(self):
        wav_bytes = _pcm_to_wav(b"")
        assert wav_bytes[:4] == b"RIFF"
        wf = io.BytesIO(wav_bytes)
        with wave.open(wf, "rb") as w:
            assert w.getnframes() == 0
