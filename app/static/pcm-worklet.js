// Turns the microphone stream into 16 kHz, 16-bit mono chunks for the recogniser.
class PcmWorklet extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000;
    this.pos = 0;
    this.out = [];
  }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    // Average each block of input samples that falls on one output sample.
    let acc = 0, n = 0;
    for (let i = 0; i < ch.length; i++) {
      acc += ch[i]; n++;
      this.pos += 1;
      if (this.pos >= this.ratio) {
        this.pos -= this.ratio;
        const v = Math.max(-1, Math.min(1, acc / n));
        this.out.push(v < 0 ? v * 0x8000 : v * 0x7fff);
        acc = 0; n = 0;
      }
    }
    if (this.out.length >= 1600) {
      this.port.postMessage(Int16Array.from(this.out).buffer);
      this.out = [];
    }
    return true;
  }
}
registerProcessor("pcm-worklet", PcmWorklet);
