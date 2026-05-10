/**
 * voice_bot_v2.js — Natural Conversation Engine
 * Handles continuous listening, VAD, and interruption.
 */
window.NaturalVoiceBot = (function() {
  "use strict";

  let _config = {
    vadThreshold: 15,
    vadHold: 1200,
    interruptThreshold: 22,
    interruptHold: 80, // Much faster interruption response
    sttUrl: "/api/v2/stt",
    chatUrl: "/api/v2/chat",
    ttsUrl: "/api/v2/tts"
  };

  let _state = "idle"; // idle, listening, thinking, speaking
  let _stream = null;
  let _audioCtx = null;
  let _analyser = null;
  let _recorder = null;
  let _chunks = [];
  
  let _silenceTimer = null;
  let _hasSpeech = false;
  let _interruptTimer = null;
  let _isContinuous = false;

  let _onStateChange = null;
  let _onTranscript = null;
  let _onReply = null;

  function init(callbacks) {
    _onStateChange = callbacks.onStateChange;
    _onTranscript = callbacks.onTranscript;
    _onReply = callbacks.onReply;
  }

  async function start() {
    if (_stream) return;
    try {
      _stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const source = _audioCtx.createMediaStreamSource(_stream);
      _analyser = _audioCtx.createAnalyser();
      _analyser.fftSize = 512;
      source.connect(_analyser);

      _isContinuous = true;
      _loop();
      _setState("idle");
    } catch (e) {
      console.error("Mic access denied", e);
    }
  }

  function stop() {
    _isContinuous = false;
    if (_stream) {
      _stream.getTracks().forEach(t => t.stop());
      _stream = null;
    }
    if (_audioCtx) {
      _audioCtx.close();
      _audioCtx = null;
    }
    _setState("idle");
  }

  function _setState(s) {
    _state = s;
    if (_onStateChange) _onStateChange(s);
  }

  function _loop() {
    if (!_isContinuous) return;

    const buf = new Uint8Array(_analyser.frequencyBinCount);
    _analyser.getByteFrequencyData(buf);
    const avg = buf.reduce((a, b) => a + b, 0) / buf.length;

    // ── Interruption Detection ───────────────────────────────────
    if (_state === "speaking" && avg > _config.interruptThreshold) {
      if (!_interruptTimer) {
        _interruptTimer = setTimeout(() => {
          console.log("Interruption detected!");
          window.dispatchEvent(new CustomEvent("voice-interrupt"));
          _startRecording();
          _interruptTimer = null;
        }, _config.interruptHold);
      }
    } else {
      clearTimeout(_interruptTimer);
      _interruptTimer = null;
    }

    // ── VAD Logic ───────────────────────────────────────────────
    if (_state === "idle" || _state === "listening") {
      if (avg > _config.vadThreshold) {
        if (_state === "idle") {
          _startRecording();
        }
        _hasSpeech = true;
        clearTimeout(_silenceTimer);
        _silenceTimer = null;
      } else if (_hasSpeech && !_silenceTimer) {
        _silenceTimer = setTimeout(() => {
          if (_state === "listening") {
            _stopRecording();
          }
        }, _config.vadHold);
      }
    }

    requestAnimationFrame(_loop);
  }

  async function _startRecording() {
    if (_state === "listening" || _state === "thinking") return;
    
    // If we were speaking, stop it
    if (_state === "speaking") {
        window.dispatchEvent(new CustomEvent("voice-stop-speech"));
    }

    _chunks = [];
    _hasSpeech = false;
    
    const mime = _bestMime();
    _recorder = new MediaRecorder(_stream, { mimeType: mime });
    _recorder.ondataavailable = e => e.data.size > 0 && _chunks.push(e.data);
    _recorder.onstop = () => {
      const blob = new Blob(_chunks, { type: mime });
      _processAudio(blob);
    };
    
    _recorder.start();
    _setState("listening");
  }

  function _stopRecording() {
    if (_recorder && _recorder.state === "recording") {
      _recorder.stop();
    }
    _setState("thinking");
  }

  async function _processAudio(blob) {
    try {
      // 1. STT
      const formData = new FormData();
      formData.append("audio", blob, "recording.webm");
      const sttRes = await fetch(_config.sttUrl, { method: "POST", body: formData });
      const sttData = await sttRes.json();
      const text = sttData.transcript?.trim();

      if (!text) {
        _setState("idle");
        return;
      }

      if (_onTranscript) _onTranscript(text);

      // 2. Chat
      const chatRes = await fetch(_config.chatUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history: window.getChatHistory?.() || [] })
      });
      const chatData = await chatRes.json();
      const reply = chatData.reply || chatData.error;

      if (_onReply) _onReply(reply, chatData.tools_used);

      // 3. Speaking state is handled by the UI/Audio player
      // We set state to speaking when we start playing audio
      _setState("speaking");
      
    } catch (e) {
      console.error("Process error", e);
      _setState("idle");
    }
  }

  function setSpeakingDone() {
    if (_state === "speaking") {
        _setState("idle");
    }
  }

  function _bestMime() {
    const t = ["audio/webm;codecs=opus","audio/webm","audio/ogg","audio/mp4"];
    return t.find(m => MediaRecorder.isTypeSupported(m)) || "";
  }

  return { init, start, stop, setSpeakingDone };
})();
