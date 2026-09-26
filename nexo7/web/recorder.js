class NexoRecorder extends AudioWorkletProcessor {
  constructor(){super();this.buffer=new Float32Array(2048);this.offset=0;}
  process(inputs){const channel=inputs[0]?.[0];if(channel)for(const value of channel){this.buffer[this.offset++]=value;if(this.offset===2048){this.port.postMessage(this.buffer);this.buffer=new Float32Array(2048);this.offset=0;}}return true;}
}
registerProcessor('nexo-recorder',NexoRecorder);
