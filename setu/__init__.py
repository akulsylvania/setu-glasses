"""Setu Glasses: silent speech in, voice out.

This package is the public integration layer: voice agent (Bolna), telephony (Plivo / Exotel),
speech synthesis and recognition (Sarvam, Cartesia, Deepgram, Kalpa Labs via Bolna), the LLM layer
and the multilingual data pipeline. The sensor signal processing, firmware and trained recogniser
are proprietary and not in this repository (see docs/PRIVACY_IP.md); they talk to this layer
through the JSONL interface in setu/decoder.py.
"""

__version__ = "0.3.0"
