/* Shared, bounded, offline media studio. No prompts, pictures or audio leave the tab. */
const RATE = 16000, WIDTH = 640, HEIGHT = 360;
const palettes = {sunrise:['#fbd9bb','#ed926b','#5e7890'],ocean:['#c2e9fa','#4385b1','#214e76'],night:['#18213e','#745fa7','#333b68'],forest:['#dce9c6','#78a67c','#305a4c']};
export function randomFrom(text) {
  let seed=2166136261;
  for(const ch of text)seed=Math.imul(seed^ch.codePointAt(0),16777619);
  return ()=>{seed+=0x6D2B79F5;let t=seed;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return ((t^(t>>>14))>>>0)/4294967296;};
}
export function compose({seed='Nexo',mood='bright',bpm=100,bars=4}={}) {
  if(!['bright','calm','mysterious'].includes(mood)||!Number.isInteger(bpm)||bpm<60||bpm>160||![2,4,8].includes(bars))throw Error('Choose 60–160 BPM and 2, 4 or 8 bars.');
  const random=randomFrom(seed+mood),scale=mood==='mysterious'?[0,2,3,7,10]:[0,2,4,7,9],notes=[];
  for(let bar=0;bar<bars;bar++){
    const root=[0,5,7,0][bar%4];
    for(let beat=0;beat<4;beat++){
      const pitch=60+root+scale[Math.floor(random()*scale.length)];
      notes.push({pitch,start:bar*4+beat,duration:mood==='calm'?0.9:0.6,velocity:75});
      if(beat%2===0)notes.push({pitch:36+root,start:bar*4+beat,duration:1.8,velocity:50});
    }
  }
  return {bpm,notes,seconds:bars*4*60/bpm};
}
export function synthesize(score,sound='soft') {
  if(!['soft','bell','synth'].includes(sound))throw Error('Unknown instrument');
  const samples=new Float32Array(Math.ceil(score.seconds*RATE));
  for(const n of score.notes){const start=Math.round(n.start*60/score.bpm*RATE),duration=n.duration*60/score.bpm,count=Math.round(duration*RATE),f=440*2**((n.pitch-69)/12);
    for(let i=0;i<count&&start+i<samples.length;i++){const t=i/RATE,p=2*Math.PI*f*t,env=Math.min(1,t/.015,(duration-t)/.05),harmonic=sound==='synth'?.25*Math.sin(2*p):sound==='bell'?.3*Math.sin(2*p):0;
      samples[start+i]+=(Math.sin(p)+harmonic)*env*(sound==='bell'?Math.exp(-4*t/duration):1)*n.velocity/127*.35;}
  }
  return samples;
}
export function wav(samples) {
  const buffer=new ArrayBuffer(44+samples.length*2),v=new DataView(buffer);
  const word=(at,s)=>{for(let i=0;i<s.length;i++)v.setUint8(at+i,s.charCodeAt(i));};
  word(0,'RIFF');v.setUint32(4,36+samples.length*2,true);word(8,'WAVE');word(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,RATE,true);v.setUint32(28,RATE*2,true);v.setUint16(32,2,true);v.setUint16(34,16,true);word(36,'data');v.setUint32(40,samples.length*2,true);
  for(let i=0;i<samples.length;i++)v.setInt16(44+i*2,Math.round(Math.max(-1,Math.min(1,samples[i]))*30000),true);
  return new Blob([buffer],{type:'audio/wav'});
}
export function midi(score) {
  const vlq=n=>{let a=[n&127];while(n>>=7)a.unshift((n&127)|128);return a;},tempo=Math.round(60000000/score.bpm),events=[];
  for(const n of score.notes){events.push([Math.round(n.start*480),0x90,n.pitch,n.velocity],[Math.round((n.start+n.duration)*480),0x80,n.pitch,0]);}
  events.sort((a,b)=>a[0]-b[0]||a[1]-b[1]);const track=[0,255,81,3,(tempo>>16)&255,(tempo>>8)&255,tempo&255];let previous=0;
  for(const [tick,...event] of events){track.push(...vlq(tick-previous),...event);previous=tick;}track.push(0,255,47,0);
  const n=track.length;return new Blob([new Uint8Array([77,84,104,100,0,0,0,6,0,0,0,1,1,224,77,84,114,107,(n>>>24)&255,(n>>>16)&255,(n>>>8)&255,n&255,...track])],{type:'audio/midi'});
}
export function paint(canvas,{scene='landscape',palette='sunrise',title='',seed='Nexo'}={},time=0,photo=null,ink=null) {
  const c=canvas.getContext('2d'),[sky,mid,deep]=palettes[palette]||palettes.sunrise,random=randomFrom(seed),w=canvas.width,h=canvas.height;
  c.save();c.scale(w/WIDTH,h/HEIGHT);c.fillStyle=sky;c.fillRect(0,0,WIDTH,HEIGHT);
  const ellipse=(x,y,rx,ry,color)=>{c.fillStyle=color;c.beginPath();c.ellipse(x,y,rx,ry,0,0,2*Math.PI);c.fill();};
  if(photo){const ratio=Math.min(WIDTH/photo.width,HEIGHT/photo.height),pw=photo.width*ratio,ph=photo.height*ratio;c.drawImage(photo,(WIDTH-pw)/2,(HEIGHT-ph)/2,pw,ph);}
  else if(scene==='space'){
    c.fillStyle='#121932';c.fillRect(0,0,WIDTH,HEIGHT);
    for(let i=0;i<65;i++){const x=random()*WIDTH,y=random()*HEIGHT;ellipse((x+time*(i%3+1))%WIDTH,y,1+random(),1+random(),'#fff7df');}
    ellipse(330,155,82,82,mid);c.strokeStyle=deep;c.lineWidth=13;c.beginPath();c.ellipse(330,155,131,25,-.3,0,Math.PI*2);c.stroke();
  } else if(scene==='abstract'){
    for(let i=0;i<24;i++)ellipse(random()*WIDTH+Math.sin(time+i)*10,random()*HEIGHT,12+random()*60,12+random()*60,[mid,deep,'#ffffff88'][i%3]);
  } else {
    ellipse(490,72,36,36,'#fff0c0');
    for(let layer=0;layer<2;layer++){c.fillStyle=layer?deep:mid;c.beginPath();c.moveTo(0,HEIGHT);for(let x=0;x<=WIDTH;x+=40)c.lineTo(x,210+layer*60+Math.sin(x/120+layer)*35+random()*12);c.lineTo(WIDTH,HEIGHT);c.fill();}
    for(let i=0;i<3;i++){const x=(90+i*210+time*6)%750-40,y=70+(i%2)*45;ellipse(x,y,36,13,'#ffffffcc');ellipse(x+13,y-12,19,18,'#ffffffcc');}
    if(scene==='chicken'){
      const bob=Math.sin(time*3)*4;ellipse(300,230+bob,64,48,'#fff4d5');ellipse(350,177+bob,29,31,'#fff4d5');ellipse(284,232+bob,31,23,'#eab873');
      ellipse(343,147+bob,9,12,'#d24949');ellipse(358,147+bob,9,12,'#d24949');ellipse(359,174+bob,4,4,'#172333');
      c.fillStyle='#e39128';c.beginPath();c.moveTo(376,179+bob);c.lineTo(399,185+bob);c.lineTo(376,191+bob);c.fill();c.strokeStyle='#e39128';c.lineWidth=5;for(const x of [280,320]){c.beginPath();c.moveTo(x,269+bob);c.lineTo(x,296);c.lineTo(x+13,296);c.stroke();}
    }
  }
  if(title){c.fillStyle='#10182dbb';c.fillRect(20,HEIGHT-63,WIDTH-40,43);c.fillStyle='#ffffff';c.font='22px system-ui';c.textAlign='center';c.fillText(title,WIDTH/2,HEIGHT-34,WIDTH-64);}
  if(ink)c.drawImage(ink,0,0,WIDTH,HEIGHT);c.restore();
}
// GIF89a with a bounded 3/3/2-bit palette. Frequent clear codes keep LZW at 9 bits.
export function gifHeader(width,height) {
  const a=[71,73,70,56,57,97,width&255,width>>8,height&255,height>>8,247,0,0];
  for(let i=0;i<256;i++)a.push(Math.round((i>>5)*255/7),Math.round(((i>>2)&7)*255/7),(i&3)*85);
  a.push(33,255,11,...Array.from('NETSCAPE2.0',c=>c.charCodeAt(0)),3,1,0,0,0);return new Uint8Array(a);
}
export function gifFrame(rgba,width,height,delay=12) {
  const codes=[];let bits=0,count=0;
  const code=n=>{bits|=n<<count;count+=9;while(count>=8){codes.push(bits&255);bits>>>=8;count-=8;}};
  for(let p=0;p<width*height;p++){if(p%200===0)code(256);const i=p*4;code((rgba[i]>>5)<<5|(rgba[i+1]>>5)<<2|(rgba[i+2]>>6));}
  code(257);if(count)codes.push(bits&255);
  const out=[33,249,4,4,delay&255,delay>>8,0,0,44,0,0,0,0,width&255,width>>8,height&255,height>>8,0,8];
  for(let i=0;i<codes.length;i+=255){const chunk=codes.slice(i,i+255);out.push(chunk.length,...chunk);}out.push(0);return new Uint8Array(out);
}
const node=(tag,text='')=>{const e=document.createElement(tag);e.textContent=text;return e;};
export function setupMediaStudio(root) {
  if(!root)return {reset(){}};
  root.classList.add('media-studio');
  const intro=node('p','Create illustrations, instrumental tunes and short animated clips on this device. The lightweight tools use templates, drawing and procedural composition—not a text-to-image, singing or AI video model. No uploads or downloads of models.');root.append(node('h2','Create on this device'),intro);
  const field=(label,id,element)=>{element.id=id;const l=node('label',label);l.htmlFor=id;root.append(l,element);return element;};
  const select=(items)=>{const e=node('select');for(const [value,text]of items){const o=node('option',text);o.value=value;e.append(o);}return e;};
  const mode=field('What would you like to create?','media-mode',select([['image','Picture'],['music','Music'],['video','Video clip']]));
  const title=field('Caption / title','media-title',node('input'));title.maxLength=80;title.placeholder='My little world';
  const scene=field('Illustration template','media-scene',select([['landscape','Landscape'],['space','Space'],['chicken','Chicken'],['abstract','Abstract shapes']]));
  const palette=field('Illustration colors','media-palette',select(Object.keys(palettes).map(x=>[x,x[0].toUpperCase()+x.slice(1)])));
  const canvas=node('canvas');canvas.id='media-canvas';canvas.width=WIDTH;canvas.height=HEIGHT;canvas.setAttribute('aria-label','Illustration preview and drawing surface');root.append(canvas);
  const ink=node('canvas');ink.width=WIDTH;ink.height=HEIGHT;
  const draw=field('Draw on the picture (finger or mouse)','media-draw',node('input'));draw.type='checkbox';
  const color=field('Pen color','media-pen-color',node('input'));color.type='color';color.value='#29344e';
  const pen=field('Pen width','media-pen-width',node('input'));pen.type='range';pen.min=2;pen.max=30;pen.value=5;
  const photoInput=field('Use your own picture instead (optional)','media-photo',node('input'));photoInput.type='file';photoInput.accept='image/png,image/jpeg,image/webp';
  root.append(node('p','Pictures: PNG, JPEG or WebP, up to 8 MB and 24 megapixels; resized to 640px. Imported photos stay in this tab.'));
  const mood=field('Music mood','media-mood',select([['bright','Bright'],['calm','Calm'],['mysterious','Mysterious']]));
  const sound=field('Instrument','media-sound',select([['soft','Soft keys'],['bell','Bell'],['synth','Synth']]));
  const tempo=field('Tempo (60–160 beats per minute)','media-tempo',node('input'));tempo.type='number';tempo.min=60;tempo.max=160;tempo.value=100;
  const bars=field('Music length','media-bars',select([['2','2 bars'],['4','4 bars'],['8','8 bars']]));bars.value='4';
  const seconds=field('Clip length','media-seconds',select([['4','4 seconds'],['8','8 seconds'],['12','12 seconds']]));
  const soundtrack=field('Include an instrumental soundtrack in the clip','media-soundtrack',node('input'));soundtrack.type='checkbox';soundtrack.checked=true;
  const actions=node('div');actions.className='media-actions';root.append(actions);
  const status=node('p');status.id='media-status';status.setAttribute('role','status');
  const output=node('div');output.id='media-output';root.append(status,output);
  let photo=null,variant=0,urls=[],job=null,disposed=0,loading=false;
  const config=()=>({scene:scene.value,palette:palette.value,title:title.value,seed:title.value+variant});
  const render=()=>paint(canvas,config(),0,photo,ink);
  const clearOutput=()=>{for(const media of output.querySelectorAll('audio,video')){media.pause();media.removeAttribute('src');media.load();}for(const url of urls)URL.revokeObjectURL(url);urls=[];output.replaceChildren();};
  const publish=(blob,name,kind)=>{const url=URL.createObjectURL(blob);urls.push(url);if(kind){const media=node(kind);media.src=url;if(kind==='img')media.alt='Locally composed illustration';else{media.controls=true;media.preload='metadata';if(kind==='video')media.playsInline=true;}output.append(media);}const a=node('a','Download '+name);a.href=url;a.download=name;output.append(a);};
  const button=(text,id,fn)=>{const b=node('button',text);b.type='button';b.id=id;b.onclick=async()=>{try{await fn();}catch(e){status.textContent=e.message;}};actions.append(b);return b;};
  const controls=[mode,title,scene,palette,draw,color,pen,photoInput,mood,sound,tempo,bars,seconds,soundtrack];
  const busy=value=>{for(const e of [...controls,...actions.querySelectorAll('button')])e.disabled=value;stop.disabled=!value;};
  const score=()=>compose({seed:title.value+variant,mood:mood.value,bpm:Number(tempo.value),bars:Number(bars.value)});
  button('New variation','media-variation',()=>{variant++;render();status.textContent='New procedural variation. Choose a template or draw your own picture.';});
  button('Clear pen strokes','media-clear-ink',()=>{ink.getContext('2d').clearRect(0,0,WIDTH,HEIGHT);render();});
  button('Remove imported picture','media-clear-photo',()=>{disposed++;photo=null;photoInput.value='';render();});
  button('Create PNG','media-image',async()=>{const revision=disposed;render();const blob=await new Promise(r=>canvas.toBlob(r,'image/png'));if(revision!==disposed)return;if(!blob)throw Error('Could not export the picture');clearOutput();publish(blob,'Nexo-illustration.png','img');status.textContent='PNG ready. This is your template illustration or drawing, not neural image generation.';});
  button('Compose music','media-music',async()=>{busy(true);status.textContent='Composing instruments locally…';try{const s=score(),samples=synthesize(s,sound.value);clearOutput();publish(wav(samples),'Nexo-music.wav','audio');publish(midi(s),'Nexo-music.mid');status.textContent=`Instrumental music ready · ${s.seconds.toFixed(1)} seconds. Press play to listen. No vocals.`;}finally{busy(false);}});
  const stop=button('Cancel clip','media-stop',()=>cancel('Clip cancelled.'));stop.disabled=true;
  button('Create video clip','media-video',async()=>{
    if(!canvas.captureStream||typeof MediaRecorder==='undefined')return createGif('Video recording is unavailable here. ');
    const type=['video/mp4;codecs=avc1.42E01E,mp4a.40.2','video/webm;codecs=vp8,opus','video/mp4','video/webm'].find(t=>MediaRecorder.isTypeSupported(t));
    if(!type)return createGif('No video encoder is available here. ');
    const duration=Number(seconds.value),cfg=config(),picture=photo,strokes=ink,revision=disposed;
    busy(true);clearOutput();status.textContent='Recording locally… Keep this tab visible.';
    const state={cancelled:false,stream:null,context:null,source:null,recorder:null,timer:null,deadline:null};job=state;
    try{
      if(soundtrack.checked){const Audio=window.AudioContext||window.webkitAudioContext;if(!Audio)throw Error('Audio playback is unavailable. Turn off the soundtrack.');state.context=new Audio();await state.context.resume();if(state.cancelled)return;const s=score(),samples=synthesize(s,sound.value),buffer=state.context.createBuffer(1,samples.length,RATE);buffer.copyToChannel(samples,0);state.source=state.context.createBufferSource();state.source.buffer=buffer;state.source.loop=true;state.destination=state.context.createMediaStreamDestination();state.source.connect(state.destination);}
      if(state.cancelled||revision!==disposed)return;
      paint(canvas,cfg,0,picture,strokes);state.stream=canvas.captureStream(20);
      if(state.destination)for(const t of state.destination.stream.getAudioTracks())state.stream.addTrack(t);
      const recorder=state.recorder=new MediaRecorder(state.stream,{mimeType:type,videoBitsPerSecond:1200000}),chunks=[];let size=0;
      const done=new Promise((resolve,reject)=>{recorder.ondataavailable=e=>{if(e.data.size){size+=e.data.size;if(size>16*1024*1024){state.cancelled=true;status.textContent='Clip exceeded the 16 MB limit.';recorder.stop();}else chunks.push(e.data);}};recorder.onerror=()=>reject(Error('Video encoder failed. Try without soundtrack or choose a shorter clip.'));recorder.onstop=resolve;});
      const start=performance.now();recorder.start(250);state.source?.start();
      state.timer=setInterval(()=>{const t=(performance.now()-start)/1000;paint(canvas,cfg,t,picture,strokes);status.textContent=`Recording locally · ${Math.min(duration,t).toFixed(1)} / ${duration}s`;if(t>=duration&&recorder.state!=='inactive')recorder.stop();},50);
      state.deadline=setTimeout(()=>cancel('Recording timed out. Keep the tab visible and try again.'),(duration+15)*1000);
      await done;
      if(!state.cancelled&&revision===disposed){const blob=new Blob(chunks,{type:recorder.mimeType});if(blob.size<100)throw Error('The encoder returned an empty clip');publish(blob,type.startsWith('video/mp4')?'Nexo-clip.mp4':'Nexo-clip.webm','video');status.textContent='Animated clip ready. This animates a template (or shows your picture) with optional synthesized music; it is not AI text-to-video.';}
    } finally {cleanup(state);if(job===state){job=null;busy(false);render();}}
  });
  button('Create silent animation (GIF)','media-gif',()=>createGif());
  async function createGif(prefix='') {
    busy(true);clearOutput();const state={cancelled:false},revision=disposed;job=state;
    const small=node('canvas');small.width=320;small.height=180;
    const cfg=config(),picture=photo,parts=[gifHeader(320,180)],frames=Number(seconds.value)*8;
    try{for(let frame=0;frame<frames;frame++){
      if(state.cancelled||revision!==disposed)return;
      paint(small,cfg,frame/8,picture,ink);const pixels=small.getContext('2d').getImageData(0,0,320,180).data;
      parts.push(gifFrame(pixels,320,180,frame%2?13:12));status.textContent=prefix+'Creating silent GIF · '+Math.round((frame+1)/frames*100)+'%';
      await new Promise(resolve=>setTimeout(resolve,0));
    }
    if(state.cancelled||revision!==disposed)return;parts.push(new Uint8Array([59]));publish(new Blob(parts,{type:'image/gif'}),'Nexo-animation.gif','img');status.textContent=prefix+'Animated GIF ready · 320×180 · silent. Download WAV separately for music.';
    }finally{if(job===state){job=null;busy(false);render();}}
  }
  function chooseMode(){
    const isMusic=mode.value==='music',isVideo=mode.value==='video';
    for(const e of [scene,palette,draw,color,pen,photoInput]){e.hidden=isMusic;root.querySelector('label[for="'+e.id+'"]').hidden=isMusic;}
    for(const e of [mood,sound,tempo,bars]){e.hidden=!isMusic&&!isVideo;root.querySelector('label[for="'+e.id+'"]').hidden=e.hidden;}
    for(const e of [seconds,soundtrack]){e.hidden=!isVideo;root.querySelector('label[for="'+e.id+'"]').hidden=e.hidden;}
    canvas.hidden=isMusic;
    for(const id of ['media-clear-ink','media-clear-photo'])root.querySelector('#'+id).hidden=isMusic;
    root.querySelector('#media-image').hidden=mode.value!=='image';root.querySelector('#media-music').hidden=!isMusic;
    root.querySelector('#media-video').hidden=!isVideo;root.querySelector('#media-gif').hidden=!isVideo;stop.hidden=!isVideo;
  }
  mode.onchange=chooseMode;chooseMode();
  function cleanup(s){clearInterval(s.timer);clearTimeout(s.deadline);try{s.source?.stop();}catch{}s.stream?.getTracks().forEach(t=>t.stop());s.destination?.stream.getTracks().forEach(t=>t.stop());s.context?.close().catch(()=>{});}
  function cancel(message){if(job){job.cancelled=true;if(job.recorder?.state==='recording')job.recorder.stop();cleanup(job);}status.textContent=message;}
  const visibility=()=>{if(document.hidden&&job)cancel('Clip cancelled because the tab was hidden. Keep it visible while recording.');};document.addEventListener('visibilitychange',visibility);
  for(const input of [title,scene,palette])input.addEventListener('input',render);
  draw.onchange=()=>{canvas.style.touchAction=draw.checked?'none':'auto';};let point=null;
  const position=e=>{const rect=canvas.getBoundingClientRect();return [(e.clientX-rect.left)*WIDTH/rect.width,(e.clientY-rect.top)*HEIGHT/rect.height];};
  canvas.onpointerdown=e=>{if(!draw.checked||job||loading)return;point=position(e);canvas.setPointerCapture(e.pointerId);stroke(point);};
  function stroke(next){const ctx=ink.getContext('2d');ctx.strokeStyle=color.value;ctx.lineWidth=Number(pen.value);ctx.lineCap='round';ctx.beginPath();ctx.moveTo(...point);ctx.lineTo(next[0]+.01,next[1]);ctx.stroke();point=next;render();}
  canvas.onpointermove=e=>{if(point)stroke(position(e));};canvas.onpointerup=canvas.onpointercancel=()=>{point=null;};
  photoInput.onchange=async()=>{const file=photoInput.files[0],revision=++disposed;if(!file)return;loading=true;busy(true);try{
    if(file.size>8*1024*1024||!['image/png','image/jpeg','image/webp'].includes(file.type))throw Error('Choose a PNG, JPEG or WebP up to 8 MB.');
    const url=URL.createObjectURL(file),image=new Image();try{image.src=url;await image.decode();}finally{URL.revokeObjectURL(url);}if(revision!==disposed)return;
    if(image.width*image.height>24000000)throw Error('Choose a picture up to 24 megapixels.');const ratio=Math.min(1,640/Math.max(image.width,image.height)),small=node('canvas');small.width=Math.max(1,Math.round(image.width*ratio));small.height=Math.max(1,Math.round(image.height*ratio));small.getContext('2d').drawImage(image,0,0,small.width,small.height);photo=small;render();status.textContent='Picture loaded locally. Add a caption, draw, or export a clip.';
  }catch(e){status.textContent=e.message;}finally{loading=false;busy(false);}};
  render();
  return {reset(){disposed++;cancel('');clearOutput();photo=null;photoInput.value='';title.value='';point=null;ink.getContext('2d').clearRect(0,0,WIDTH,HEIGHT);render();}};
}
if(typeof document!=='undefined'){const root=document.getElementById('desktop-media-studio');if(root)setupMediaStudio(root);}
