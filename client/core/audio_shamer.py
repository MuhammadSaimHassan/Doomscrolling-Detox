"""
DoomScroll Detox - client/core/audio_shamer.py

Phase 4: The Voice-Shame Escalation

Wraps pyttsx3 in a small, thread-safe class that reads the AI-generated
roast out loud without blocking the PyQt6 overlay's event loop.

Why this needs care:
  - pyttsx3 engines are NOT safe to share across threads, and on some
    platforms (notably Windows/SAPI5) a single engine instance can only
    reliably run one say()/runAndWait() cycle before it needs to be
    re-initialized. To sidestep both issues, a fresh engine is created
    inside the worker thread for every shame_user_out_loud() call.
  - Only one utterance should ever play at a time (you don't want two
    overlapping AI voices roasting the user simultaneously if triggers
    stack up), so access is serialized with a threading.Lock.
  - Because PyQt6 widgets must only be touched from the GUI thread, this
    class never touches Qt directly -- it just runs speech on a daemon
    thread and calls an optional `on_complete` callback when done. If the
    caller needs to update the UI from that callback, it should marshal
    back to the GUI thread itself (e.g. via a pyqtSignal).
"""

from __future__ import annotations

import platform
import threading
from typing import Callable, Optional


# --------------------------------------------------------------------------
# Platform-appropriate default speaking rate (words per minute)
# --------------------------------------------------------------------------
# pyttsx3's "rate" property maps roughly 1:1 to WPM, but the *comfortable*
# range differs slightly per OS/engine because SAPI5, NSSpeechSynthesizer,
# and espeak all interpret it a little differently. These defaults sit in
# the 150-180 WPM band requested: fast enough to feel urgent/annoying,
# slow enough to stay intelligible.
_DEFAULT_RATES_BY_OS = {
    "Windows": 170,  # SAPI5 voices tend to sound clearer a bit faster
    "Darwin": 175,   # macOS NSSpeechSynthesizer voices are naturally brisk
    "Linux": 155,    # espeak gets harder to understand above ~160 WPM
}
_FALLBACK_RATE = 165


def _default_rate_for_platform() -> int:
    return _DEFAULT_RATES_BY_OS.get(platform.system(), _FALLBACK_RATE)


# --------------------------------------------------------------------------
# AudioShamer
# --------------------------------------------------------------------------

class AudioShamer:
    """
    Thread-safe, non-blocking local TTS wrapper for reading roasts aloud.

    Parameters
    ----------
    rate:
        Speaking rate in words-per-minute. Defaults to a platform-tuned
        value in the 150-180 WPM range if not provided.
    volume:
        0.0 (silent) to 1.0 (full volume). Defaults to 1.0.
    """

    def __init__(self, rate: Optional[int] = None, volume: float = 1.0) -> None:
        self.os_name = platform.system()
        self.rate = rate if rate is not None else _default_rate_for_platform()
        self.volume = max(0.0, min(1.0, volume))

        self._speak_lock = threading.Lock()
        self._current_engine = None  # set while an utterance is in progress
        self._engine_lock = threading.Lock()  # guards _current_engine access

    # -- Public API ---------------------------------------------------------

    def shame_user_out_loud(
        self,
        roast_text: str,
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> threading.Thread:
        """
        Speaks `roast_text` aloud on a background daemon thread so the
        calling PyQt6 UI never blocks. Returns the Thread object in case
        the caller wants to join() or track it, but does not join it
        itself.

        If a previous shame session is still speaking, this call will
        queue behind it (via the internal lock) rather than overlapping.
        """
        thread = threading.Thread(
            target=self._speak_safely,
            args=(roast_text, on_complete, on_error),
            daemon=True,
            name="AudioShamerThread",
        )
        thread.start()
        return thread

    def stop(self) -> None:
        """
        Interrupts whatever is currently being spoken, if anything.
        Safe to call from any thread.
        """
        with self._engine_lock:
            if self._current_engine is not None:
                try:
                    self._current_engine.stop()
                except Exception:
                    pass  # best-effort; engine may already be tearing down

    # -- Internal -------------------------------------------------------------

    def _speak_safely(
        self,
        roast_text: str,
        on_complete: Optional[Callable[[], None]],
        on_error: Optional[Callable[[Exception], None]],
    ) -> None:
        with self._speak_lock:
            try:
                self._speak_blocking(roast_text)
            except Exception as exc:  # noqa: BLE001
                if on_error:
                    on_error(exc)
                else:
                    print(f"[audio_shamer] TTS failed: {exc}")
            finally:
                if on_complete:
                    on_complete()

    def _speak_blocking(self, text: str) -> None:
        """
        Runs entirely on the calling (background) thread. Creates a fresh
        pyttsx3 engine for this single utterance -- deliberately not
        reused across calls, since pyttsx3 engines are unreliable when
        shared across threads or reused for multiple runAndWait() cycles.
        """
        try:
            import pyttsx3
        except ImportError as exc:
            raise ImportError(
                "Missing dependency 'pyttsx3'. Install it with:\n"
                "    pip install pyttsx3"
            ) from exc

        engine = pyttsx3.init()
        engine.setProperty("rate", self.rate)
        engine.setProperty("volume", self.volume)

        with self._engine_lock:
            self._current_engine = engine

        try:
            engine.say(text)
            engine.runAndWait()
        finally:
            with self._engine_lock:
                self._current_engine = None
            try:
                engine.stop()
            except Exception:
                pass


# --------------------------------------------------------------------------
# Manual test
# --------------------------------------------------------------------------

def _test_runner() -> None:
    shamer = AudioShamer()
    print(f"[audio_shamer] Platform: {shamer.os_name}, rate: {shamer.rate} WPM")
    print("[audio_shamer] Speaking a test roast asynchronously...")

    done_event = threading.Event()

    def _on_done():
        print("[audio_shamer] Finished speaking.")
        done_event.set()

    def _on_error(exc: Exception):
        print(f"[audio_shamer] Error: {exc}")
        done_event.set()

    shamer.shame_user_out_loud(
        "bestie, seriously? put the fucking phone down and get your ass back to studying.  Bitch!",
        on_complete=_on_done,
        on_error=_on_error,
    )

    print("[audio_shamer] Main thread is NOT blocked -- this prints immediately.")
    done_event.wait(timeout=15)


if __name__ == "__main__":
    _test_runner()
