/* Shared, bounded, offline media studio. No prompts, pictures or audio leave the tab. */
const RATE = 16000, WIDTH = 640, HEIGHT = 360;
const SW = 360, SH = 640; // vertical short-video canvas
const SHORT_MAX_BEATS = 8, SHORT_MAX_SECONDS = 60, SHORT_MIN_BEAT = 3, SHORT_MAX_BEAT = 12, SHORT_MAX_CHARS = 140;
const NARRATION_WPS = 2.5; // ~150 words per minute
const SHORT_SCENES = ['landscape','space','chicken','abstract'];
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
// --- Short-video pipeline (script -> timings -> captions -> vertical scenes -> one MP4) ---
function roundRectPath(c,x,y,w,h,r){c.beginPath();c.moveTo(x+r,y);c.arcTo(x+w,y,x+w,y+h,r);c.arcTo(x+w,y+h,x,y+h,r);c.arcTo(x,y+h,x,y,r);c.arcTo(x,y,x+w,y,r);c.closePath();}
function checkBeatText(text){
  if(typeof text!=='string'||!text.trim()||text.length>SHORT_MAX_CHARS)throw Error(`Each beat needs 1 to ${SHORT_MAX_CHARS} characters of text.`);
  if(/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(text))throw Error('Beats must be plain printable text.');
  return text.trim();
}
// Split a pasted paragraph into sentence beats, hard-splitting overlong sentences at word boundaries.
export function splitBeats(text){
  if(typeof text!=='string'||!text.trim())throw Error('Paste a paragraph to split into beats.');
  const pieces=[];
  for(const chunk of text.split(/\n+/))
    for(const m of chunk.match(/[^.!?…]+[.!?…]+|[^.!?…]+$/g)||[]){const s=m.trim();if(s)pieces.push(s);}
  const beats=[];
  for(const piece of pieces){
    if(piece.length<=SHORT_MAX_CHARS){beats.push(piece);continue;}
    let cur='';
    for(const w of piece.split(/\s+/)){
      if((cur+' '+w).trim().length>SHORT_MAX_CHARS){beats.push(cur.trim());cur=w;}
      else cur+=' '+w;
    }
    if(cur.trim())beats.push(cur.trim());
  }
  const clean=beats.map(s=>s.trim()).filter(Boolean);
  if(!clean.length)throw Error('Paste a paragraph to split into beats.');
  if(clean.length>SHORT_MAX_BEATS)throw Error(`That makes ${clean.length} beats; keep it to ${SHORT_MAX_BEATS} or fewer.`);
  return clean.map(checkBeatText);
}
// Estimated narration seconds for one beat at a calm speaking pace, clamped to the per-beat bounds.
export function beatSeconds(text){
  const words=checkBeatText(text).split(/\s+/).length;
  return Math.min(SHORT_MAX_BEAT,Math.max(SHORT_MIN_BEAT,Math.round(words/NARRATION_WPS*10)/10));
}
// Validate beats and lay out cumulative timings. Throws a plain-language error for anything invalid.
export function shortPlan(beats){
  if(!Array.isArray(beats)||!beats.length)throw Error('Add at least one beat.');
  if(beats.length>SHORT_MAX_BEATS)throw Error(`At most ${SHORT_MAX_BEATS} beats per short.`);
  let t=0;
  const items=beats.map((b,i)=>{
    const text=checkBeatText(b.text);
    if(!SHORT_SCENES.includes(b.scene))throw Error(`Beat ${i+1}: choose a scene.`);
    if(!palettes[b.palette])throw Error(`Beat ${i+1}: choose a color palette.`);
    const seconds=beatSeconds(text),start=Math.round(t*100)/100;t+=seconds;
    return {text,scene:b.scene,palette:b.palette,start,end:Math.round(t*100)/100,seconds};
  });
  const total=Math.round(t*100)/100;
  if(total>SHORT_MAX_SECONDS)throw Error(`That short runs ${total.toFixed(1)}s — over the ${SHORT_MAX_SECONDS}s limit. Shorten a beat or remove one.`);
  return {items,total};
}
function srtTime(sec){
  const ms=Math.round(sec*1000);
  const p=(v,l)=>String(v).padStart(l,'0');
  return `${p(Math.floor(ms/3600000),2)}:${p(Math.floor(ms/60000)%60,2)}:${p(Math.floor(ms/1000)%60,2)},${p(ms%1000,3)}`;
}
export function shortSrt(items){
  if(!Array.isArray(items)||!items.length)throw Error('Add at least one beat.');
  return items.map((b,i)=>`${i+1}\n${srtTime(b.start)} --> ${srtTime(b.end)}\n${b.text}\n`).join('\n');
}
// Word-wrap a caption to a pixel width; truncate with an ellipsis past maxLines.
export function wrapCaption(ctx,text,maxWidth,maxLines=4){
  const words=String(text).split(/\s+/).filter(Boolean),lines=[];let line='';
  for(const w of words){
    const test=line?line+' '+w:w;
    if(ctx.measureText(test).width<=maxWidth||!line)line=test;
    else{lines.push(line);line=w;}
  }
  if(line)lines.push(line);
  if(lines.length>maxLines){
    const cut=lines.slice(0,maxLines);let last=cut[maxLines-1];
    while(ctx.measureText(last+'…').width>maxWidth&&last.length>1)last=last.slice(0,-1);
    cut[maxLines-1]=last+'…';return cut;
  }
  return lines;
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
// Vertical 9:16 scene for short videos: one template scene per beat, caption band, progress.
export function paintShort(canvas,{scene='landscape',palette='sunrise',caption='',index=0,count=1,seed='Nexo',photo=null,progress=0}={},time=0){
  const c=canvas.getContext('2d'),W=canvas.width,H=canvas.height;
  const [sky,mid,deep]=palettes[palette]||palettes.sunrise;
  const random=randomFrom(seed+':'+index);
  const ellipse=(x,y,rx,ry,color)=>{c.fillStyle=color;c.beginPath();c.ellipse(x,y,rx,ry,0,0,2*Math.PI);c.fill();};
  const g=c.createLinearGradient(0,0,0,H);g.addColorStop(0,sky);g.addColorStop(.55,mid);g.addColorStop(1,deep);
  c.fillStyle=g;c.fillRect(0,0,W,H);
  if(photo){
    const ratio=Math.max(W/photo.width,H/photo.height),pw=photo.width*ratio,ph=photo.height*ratio;
    c.drawImage(photo,(W-pw)/2,(H-ph)/2,pw,ph);
    c.fillStyle='#00000055';c.fillRect(0,0,W,H); // scrim keeps captions legible
  } else if(scene==='space'){
    c.fillStyle='#101736';c.fillRect(0,0,W,H);
    for(let i=0;i<48;i++){const x=(random()*W+time*(2+random()*4))%W;ellipse(x,random()*H,1+random()*1.6,1+random()*1.6,'#fff7df');}
    ellipse(W/2,H*0.30,64,64,mid);
    c.strokeStyle=deep;c.lineWidth=11;c.beginPath();c.ellipse(W/2,H*0.30,104,22,-.28,0,Math.PI*2);c.stroke();
  } else if(scene==='abstract'){
    for(let i=0;i<16;i++){const x=random()*W+Math.sin(time*.8+i)*14,y=((random()*H+time*22*(0.4+random()))%(H+140))-70;
      ellipse(x,y,16+random()*46,16+random()*46,[mid,deep,'#ffffff77'][i%3]);}
  } else {
    ellipse(W*0.74,H*0.15,30,30,'#fff0c0');
    for(let layer=0;layer<2;layer++){c.fillStyle=layer?deep:mid;c.beginPath();c.moveTo(0,H);
      for(let x=0;x<=W;x+=24)c.lineTo(x,H*0.52+layer*H*0.14+Math.sin(x/70+layer)*22+random()*8);
      c.lineTo(W,H);c.fill();}
    for(let i=0;i<3;i++){const x=(40+i*110+time*10)%(W+120)-60,y=H*0.16+(i%2)*H*0.09;
      ellipse(x,y,30,11,'#ffffffcc');ellipse(x+11,y-10,16,15,'#ffffffcc');}
    if(scene==='chicken'){
      const bob=Math.sin(time*3)*4,k=W/560;
      c.save();c.translate(W/2-300*k,H*0.52-230*k);c.scale(k,k);
      ellipse(300,230+bob,64,48,'#fff4d5');ellipse(350,177+bob,29,31,'#fff4d5');ellipse(284,232+bob,31,23,'#eab873');
      ellipse(343,147+bob,9,12,'#d24949');ellipse(358,147+bob,9,12,'#d24949');ellipse(359,174+bob,4,4,'#172333');
      c.fillStyle='#e39128';c.beginPath();c.moveTo(376,179+bob);c.lineTo(399,185+bob);c.lineTo(376,191+bob);c.fill();
      c.strokeStyle='#e39128';c.lineWidth=5;for(const x of [280,320]){c.beginPath();c.moveTo(x,269+bob);c.lineTo(x,296);c.lineTo(x+13,296);c.stroke();}
      c.restore();
    }
  }
  c.fillStyle='#ffffff55';c.fillRect(0,0,W,5);
  c.fillStyle='#ffffffdd';c.fillRect(0,0,Math.max(0,Math.min(1,progress))*W,5);
  if(count>1){c.font='600 14px system-ui';c.textAlign='right';c.textBaseline='alphabetic';c.fillStyle='#ffffffee';c.fillText(`${index+1} / ${count}`,W-14,26);}
  if(caption){
    c.font='600 21px system-ui';c.textAlign='center';
    const lines=wrapCaption(c,caption,W-56);
    if(lines.length){
      const lh=27,pad=14,bw=Math.min(W-32,Math.max(...lines.map(l=>c.measureText(l).width))+pad*2),bh=lines.length*lh+pad*2;
      const bx=(W-bw)/2,by=H-30-bh;
      c.fillStyle='#10182dcc';roundRectPath(c,bx,by,bw,bh,14);c.fill();
      c.fillStyle='#ffffff';
      lines.forEach((l,i)=>c.fillText(l,W/2,by+pad+20+i*lh,W-56));
    }
  }
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
  const intro=node('p','Create illustrations, instrumental tunes, short animated clips and vertical short videos on this device. The lightweight tools use templates, drawing and procedural composition—not a text-to-image, singing or AI video model. No uploads or downloads of models.');root.append(node('h2','Create on this device'),intro);
  const field=(label,id,element)=>{element.id=id;const l=node('label',label);l.htmlFor=id;root.append(l,element);return element;};
  const select=(items)=>{const e=node('select');for(const [value,text]of items){const o=node('option',text);o.value=value;e.append(o);}return e;};
  const mode=field('What would you like to create?','media-mode',select([['image','Picture'],['music','Music'],['video','Video clip'],['shorts','Short video']]));
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
  // --- Short video maker: script beats -> timings -> captions -> vertical scenes -> one MP4 ---
  const shortsBox=node('div');shortsBox.id='shorts-box';root.append(shortsBox);
  const shortsIntro=node('p');shortsIntro.textContent='Write one line per scene (up to 8 beats). Timings come from word count at about 150 words per minute. Captions burn into the video and can also export as .srt. Narrate with your microphone while recording — no AI voice is included.';shortsBox.append(shortsIntro);
  const beatsWrap=node('div');beatsWrap.id='shorts-beats';shortsBox.append(beatsWrap);
  let beats=exampleBeats(),previewIndex=0;
  function exampleBeats(){return [
    {text:'Every sunrise is a quiet promise: today is unwritten.',scene:'landscape',palette:'sunrise'},
    {text:'Small steps, taken daily, move mountains.',scene:'abstract',palette:'forest'},
    {text:'Made locally on this device. No uploads, no cloud.',scene:'space',palette:'night'}];}
  function renderBeats(){
    beatsWrap.replaceChildren();
    beats.forEach((beat,i)=>{
      const row=node('div');row.className='shorts-beat';
      row.append(node('strong','Beat '+(i+1)));
      const text=node('textarea');text.maxLength=SHORT_MAX_CHARS;text.rows=2;text.value=beat.text;
      text.placeholder='Narration line for this scene (max 140 characters)';text.setAttribute('aria-label','Beat '+(i+1)+' narration');
      text.oninput=()=>{beat.text=text.value;previewIndex=i;previewShorts();updateShortsInfo();};
      text.onfocus=()=>{previewIndex=i;previewShorts();};
      const sceneSel=node('select');sceneSel.setAttribute('aria-label','Beat '+(i+1)+' scene');
      for(const s of SHORT_SCENES){const o=node('option',s[0].toUpperCase()+s.slice(1));o.value=s;sceneSel.append(o);}
      sceneSel.value=beat.scene;sceneSel.onchange=()=>{beat.scene=sceneSel.value;previewShorts();};
      const palSel=node('select');palSel.setAttribute('aria-label','Beat '+(i+1)+' colors');
      for(const p of Object.keys(palettes)){const o=node('option',p[0].toUpperCase()+p.slice(1));o.value=p;palSel.append(o);}
      palSel.value=beat.palette;palSel.onchange=()=>{beat.palette=palSel.value;previewShorts();};
      const remove=node('button','Remove');remove.type='button';remove.className='secondary';
      remove.onclick=()=>{if(beats.length<=1){status.textContent='A short needs at least one beat.';return;}beats.splice(i,1);previewIndex=0;renderBeats();previewShorts();updateShortsInfo();};
      row.append(text,sceneSel,palSel,remove);beatsWrap.append(row);
    });
    const add=node('button','+ Add beat');add.type='button';add.className='secondary';
    add.onclick=()=>{if(beats.length>=SHORT_MAX_BEATS){status.textContent='At most 8 beats per short.';return;}beats.push({text:'',scene:'landscape',palette:'sunrise'});renderBeats();updateShortsInfo();};
    beatsWrap.append(add);
  }
  const splitInput=node('textarea');splitInput.rows=2;splitInput.maxLength=1200;
  splitInput.placeholder='Or paste a paragraph here, then split it into beats…';splitInput.setAttribute('aria-label','Paragraph to split into beats');
  const splitBtn=node('button','Split paragraph into beats');splitBtn.type='button';splitBtn.id='media-split-beats';splitBtn.className='secondary';
  splitBtn.onclick=()=>{try{
    beats=splitBeats(splitInput.value).map(text=>({text,scene:'landscape',palette:'sunrise'}));
    previewIndex=0;renderBeats();previewShorts();updateShortsInfo();
    status.textContent=beats.length+' beat(s) ready. Edit the lines, then record.';
  }catch(e){status.textContent=e.message;}};
  shortsBox.append(splitInput,splitBtn);
  const shortsInfo=node('p');shortsInfo.id='shorts-info';shortsInfo.setAttribute('role','status');shortsBox.append(shortsInfo);
  const voiceover=node('input');voiceover.type='checkbox';voiceover.id='media-voiceover';voiceover.checked=true;
  const voiceLabel=node('label');voiceLabel.htmlFor='media-voiceover';
  voiceLabel.textContent=' Record my voiceover with the microphone while recording (the browser asks permission; earphones avoid echo).';
  voiceLabel.prepend(voiceover);shortsBox.append(voiceLabel);
  function updateShortsInfo(){
    try{const plan=shortPlan(beats);shortsInfo.textContent=`≈ ${plan.total.toFixed(1)} seconds · ${beats.length} beat(s). Keep this tab visible while recording.`;}
    catch(e){shortsInfo.textContent=e.message;}
  }
  function beatOpts(i,progress=0){
    const b=beats[i]||{text:'',scene:'landscape',palette:'sunrise'};
    return {scene:b.scene,palette:b.palette,caption:b.text,index:i,count:beats.length,seed:title.value+'#'+variant,photo,progress};
  }
  function previewShorts(){if(job||mode.value!=='shorts')return;paintShort(canvas,beatOpts(Math.min(previewIndex,beats.length-1)),0);}
  async function recordShort(){
    const plan=shortPlan(beats),total=plan.total;
    const type=['video/mp4;codecs=avc1.42E01E,mp4a.40.2','video/webm;codecs=vp8,opus','video/mp4','video/webm'].find(t=>typeof MediaRecorder!=='undefined'&&MediaRecorder.isTypeSupported(t));
    if(!type)return createShortGif('Video recording is unavailable here. ');
    busy(true);clearOutput();status.textContent='Recording short locally… Keep this tab visible.';
    const revision=disposed,state={cancelled:false,stream:null,context:null,source:null,micSource:null,micStream:null,destination:null,recorder:null,timer:null,deadline:null};job=state;
    canvas.width=SW;canvas.height=SH;
    try{
      const Audio=window.AudioContext||window.webkitAudioContext;if(!Audio)throw Error('Audio playback is unavailable here.');
      state.context=new Audio();await state.context.resume();if(state.cancelled)return;
      state.destination=state.context.createMediaStreamDestination();
      if(soundtrack.checked){
        const s=score(),samples=synthesize(s,sound.value),buffer=state.context.createBuffer(1,samples.length,RATE);
        buffer.copyToChannel(samples,0);state.source=state.context.createBufferSource();state.source.buffer=buffer;state.source.loop=true;
        const musicGain=state.context.createGain();musicGain.gain.value=voiceover.checked?0.22:0.4;
        state.source.connect(musicGain);musicGain.connect(state.destination);musicGain.connect(state.context.destination);
      }
      if(voiceover.checked){
        if(!navigator.mediaDevices?.getUserMedia)throw Error('Microphone recording is unavailable in this browser.');
        status.textContent='Waiting for microphone permission…';
        state.micStream=await navigator.mediaDevices.getUserMedia({audio:true});if(state.cancelled)return;
        state.micSource=state.context.createMediaStreamSource(state.micStream);state.micSource.connect(state.destination);
        status.textContent='Recording short locally… Keep this tab visible.';
      }
      if(state.cancelled||revision!==disposed)return;
      state.stream=canvas.captureStream(20);
      for(const t of state.destination.stream.getAudioTracks())state.stream.addTrack(t);
      const recorder=state.recorder=new MediaRecorder(state.stream,{mimeType:type,videoBitsPerSecond:1200000}),chunks=[];let size=0;
      const done=new Promise((resolve,reject)=>{recorder.ondataavailable=e=>{if(e.data.size){size+=e.data.size;
        if(size>16*1024*1024){state.cancelled=true;status.textContent='Short exceeded the 16 MB limit.';recorder.stop();}
        else chunks.push(e.data);}};recorder.onerror=()=>reject(Error('Video encoder failed. Try without voiceover or shorten the short.'));recorder.onstop=resolve;});
      const start=performance.now();recorder.start(250);state.source?.start();
      state.timer=setInterval(()=>{const t=(performance.now()-start)/1000;
        let bi=plan.items.findIndex(b=>t<b.end);if(bi<0)bi=plan.items.length-1;
        const item=plan.items[bi];
        paintShort(canvas,{scene:item.scene,palette:item.palette,caption:item.text,index:bi,count:plan.items.length,seed:title.value+'#'+variant,photo,progress:Math.min(1,t/total)},Math.max(0,t-item.start));
        status.textContent=`Recording short locally · beat ${bi+1}/${plan.items.length} · ${Math.min(total,t).toFixed(1)} / ${total.toFixed(1)}s`;
        if(t>=total&&recorder.state!=='inactive')recorder.stop();},50);
      state.deadline=setTimeout(()=>cancel('Recording timed out. Keep the tab visible and try again.'),(total+15)*1000);
      await done;
      if(!state.cancelled&&revision===disposed){const blob=new Blob(chunks,{type:recorder.mimeType});if(blob.size<100)throw Error('The encoder returned an empty clip');
        publish(blob,(title.value.trim()||'Nexo')+(type.startsWith('video/mp4')?'-short.mp4':'-short.webm'),'video');
        status.textContent='Short video ready — vertical 360×640 with burned-in captions. Template animation, your voiceover and procedural music: not AI text-to-video.';}
    } finally {cleanup(state);if(job===state){job=null;busy(false);}
      if(mode.value==='shorts'){canvas.width=SW;canvas.height=SH;previewShorts();}else{canvas.width=WIDTH;canvas.height=HEIGHT;render();}}
  }
  async function createShortGif(prefix=''){
    const plan=shortPlan(beats);
    busy(true);clearOutput();const state={cancelled:false},revision=disposed;job=state;
    const small=node('canvas');small.width=180;small.height=320;
    const frames=Math.min(Math.round(plan.total),20)*8,parts=[gifHeader(180,320)];
    try{for(let frame=0;frame<frames;frame++){
      if(state.cancelled||revision!==disposed)return;
      const t=frame/8;let bi=plan.items.findIndex(b=>t<b.end);if(bi<0)bi=plan.items.length-1;const item=plan.items[bi];
      paintShort(small,{scene:item.scene,palette:item.palette,caption:item.text,index:bi,count:plan.items.length,seed:title.value+'#'+variant,photo,progress:Math.min(1,t/plan.total)},Math.max(0,t-item.start));
      const pixels=small.getContext('2d').getImageData(0,0,180,320).data;
      parts.push(gifFrame(pixels,180,320,frame%2?13:12));status.textContent=prefix+`Creating silent GIF · ${Math.round((frame+1)/frames*100)}%`;
      await new Promise(r=>setTimeout(r,0));
    }
    if(state.cancelled||revision!==disposed)return;parts.push(new Uint8Array([59]));
    publish(new Blob(parts,{type:'image/gif'}),(title.value.trim()||'Nexo')+'-short.gif','img');
    status.textContent=prefix+'Silent GIF ready · 180×320 · first 20 seconds. Record the video for the full short with voiceover.';
    }finally{if(job===state){job=null;busy(false);}}
  }
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
  const recordShortsBtn=button('Record short video','media-shorts',()=>{recordShort().catch(e=>{status.textContent=e.message;});});
  const srtBtn=button('Download captions (.srt)','media-shorts-srt',()=>{try{
    const plan=shortPlan(beats);clearOutput();
    publish(new Blob([shortSrt(plan.items)],{type:'text/plain'}),(title.value.trim()||'Nexo')+'-short.srt');
    status.textContent='Captions exported as .srt with the same timings burned into the video.';
  }catch(e){status.textContent=e.message;}});
  controls.push(voiceover,splitInput,splitBtn);
  renderBeats();updateShortsInfo();
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
  button('Create silent animation (GIF)','media-gif',()=>{if(mode.value==='shorts')return createShortGif();return createGif();});
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
    const isMusic=mode.value==='music',isVideo=mode.value==='video',isShorts=mode.value==='shorts';
    for(const e of [scene,palette,draw,color,pen]){const hide=isMusic||isShorts;e.hidden=hide;root.querySelector('label[for="'+e.id+'"]').hidden=hide;}
    photoInput.hidden=isMusic;root.querySelector('label[for="media-photo"]').hidden=isMusic;
    for(const e of [mood,sound,tempo,bars]){e.hidden=!isMusic&&!isVideo&&!isShorts;root.querySelector('label[for="'+e.id+'"]').hidden=e.hidden;}
    seconds.hidden=!isVideo;root.querySelector('label[for="media-seconds"]').hidden=!isVideo;
    soundtrack.hidden=!isVideo&&!isShorts;root.querySelector('label[for="media-soundtrack"]').hidden=!isVideo&&!isShorts;
    shortsBox.hidden=!isShorts;
    root.querySelector('label[for="media-title"]').textContent=isShorts?'Short title':'Caption / title';
    canvas.hidden=isMusic;
    root.querySelector('#media-clear-ink').hidden=isMusic||isShorts;
    root.querySelector('#media-clear-photo').hidden=isMusic;
    root.querySelector('#media-image').hidden=mode.value!=='image';root.querySelector('#media-music').hidden=!isMusic;
    root.querySelector('#media-video').hidden=!isVideo;root.querySelector('#media-gif').hidden=!(isVideo||isShorts);
    recordShortsBtn.hidden=!isShorts;srtBtn.hidden=!isShorts;stop.hidden=!(isVideo||isShorts);
    if(isShorts){canvas.width=SW;canvas.height=SH;previewShorts();}
    else if(canvas.width!==WIDTH||canvas.height!==HEIGHT){canvas.width=WIDTH;canvas.height=HEIGHT;render();}
  }
  mode.onchange=chooseMode;chooseMode();
  function cleanup(s){clearInterval(s.timer);clearTimeout(s.deadline);try{s.source?.stop();}catch{}s.stream?.getTracks().forEach(t=>t.stop());s.micStream?.getTracks().forEach(t=>t.stop());try{s.micSource?.disconnect();}catch{}s.destination?.stream.getTracks().forEach(t=>t.stop());s.context?.close().catch(()=>{});}
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
  return {reset(){disposed++;cancel('');clearOutput();photo=null;photoInput.value='';title.value='';point=null;
    beats=exampleBeats();previewIndex=0;splitInput.value='';renderBeats();updateShortsInfo();
    canvas.width=WIDTH;canvas.height=HEIGHT;ink.getContext('2d').clearRect(0,0,WIDTH,HEIGHT);render();}};
}
if(typeof document!=='undefined'){const root=document.getElementById('desktop-media-studio');if(root)setupMediaStudio(root);}
