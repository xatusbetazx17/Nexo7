// Deterministic local editing. This is not a diffusion or segmentation model.
export function setupImageStudio() {
  const $ = id => document.getElementById(id);
  const canvas = $('studio-canvas'), ctx = canvas.getContext('2d', {willReadFrequently:true});
  let original = null, undo = null, drawing = false, version = 0;
  const message = text => { $('studio-status').textContent = text; };
  const capture = () => ctx.getImageData(0, 0, canvas.width, canvas.height);
  function restore(data) {
    canvas.width = data.width; canvas.height = data.height;
    ctx.putImageData(data, 0, 0);
  }
  function controls(enabled) {
    for (const node of document.querySelectorAll('[data-image-action]')) node.disabled = !enabled;
    $('studio-undo').disabled = !undo;
    canvas.hidden = !enabled;
  }
  function checkpoint() { undo = capture(); $('studio-undo').disabled = false; }
  function reset() {
    version++; original = undo = null; drawing = false;
    canvas.width = canvas.height = 1;
    $('studio-file').value = '';
    controls(false); message('Choose an image. It stays in this tab until you download or clear it.');
  }
  $('studio-file').onchange = async () => {
    const file = $('studio-file').files[0], current = ++version;
    if (!file) return;
    try {
      if (!['image/png','image/jpeg','image/webp'].includes(file.type) || file.size > 8 * 1024 * 1024) throw Error('Choose a PNG, JPEG or WebP image under 8 MB.');
      const url = URL.createObjectURL(file), image = new Image();
      try {
        image.src = url; await image.decode();
        if (current !== version) return;
        if (image.naturalWidth * image.naturalHeight > 24_000_000) throw Error('Choose a photo of 24 megapixels or less.');
        const scale = Math.min(1, 1024 / Math.max(image.naturalWidth, image.naturalHeight));
        canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
        canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
        ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
        original = capture(); undo = null; controls(true);
        message(`Ready · ${canvas.width} × ${canvas.height}. Local editing; no image is uploaded.`);
      } finally { URL.revokeObjectURL(url); }
    } catch (error) { if (current === version) message(error.message || 'This image could not be opened.'); }
  };
  $('studio-rotate').onclick = () => {
    checkpoint(); const source = document.createElement('canvas'); source.width=canvas.width; source.height=canvas.height;
    source.getContext('2d').drawImage(canvas,0,0);
    canvas.width=source.height; canvas.height=source.width;
    ctx.translate(canvas.width,0); ctx.rotate(Math.PI/2); ctx.drawImage(source,0,0); ctx.setTransform(1,0,0,1,0,0);
  };
  $('studio-flip').onclick = () => {
    checkpoint(); const source=document.createElement('canvas'); source.width=canvas.width;source.height=canvas.height;
    source.getContext('2d').drawImage(canvas,0,0);ctx.clearRect(0,0,canvas.width,canvas.height);
    ctx.translate(canvas.width,0);ctx.scale(-1,1);ctx.drawImage(source,0,0);ctx.setTransform(1,0,0,1,0,0);
  };
  $('studio-crop').onclick = () => {
    checkpoint();const size=Math.min(canvas.width,canvas.height),data=ctx.getImageData(Math.floor((canvas.width-size)/2),Math.floor((canvas.height-size)/2),size,size);restore(data);
  };
  $('studio-gray').onclick = () => {
    checkpoint();const data=capture();for(let i=0;i<data.data.length;i+=4){const gray=Math.round(.2126*data.data[i]+.7152*data.data[i+1]+.0722*data.data[i+2]);data.data[i]=data.data[i+1]=data.data[i+2]=gray;}ctx.putImageData(data,0,0);
  };
  $('studio-undo').onclick = () => {if(undo){restore(undo);undo=null;$('studio-undo').disabled=true;}};
  $('studio-reset').onclick = () => {if(original){checkpoint();restore(original);}};
  $('studio-clear').onclick = reset;
  function erase(event) {
    if (!drawing) return;
    const rect=canvas.getBoundingClientRect();
    ctx.save();ctx.globalCompositeOperation='destination-out';ctx.beginPath();
    ctx.arc((event.clientX-rect.left)*canvas.width/rect.width,(event.clientY-rect.top)*canvas.height/rect.height,Number($('studio-brush').value)*canvas.width/rect.width/2,0,2*Math.PI);ctx.fill();ctx.restore();
  }
  canvas.onpointerdown = event => {if(!original||!$('studio-erase').checked)return;checkpoint();drawing=true;canvas.setPointerCapture(event.pointerId);erase(event);};
  canvas.onpointermove = erase;
  canvas.onpointerup = canvas.onpointercancel = () => {drawing=false;};
  $('studio-erase').onchange = () => {canvas.classList.toggle('erasing',$('studio-erase').checked);};
  $('studio-download').onclick = () => {
    canvas.toBlob(blob=>{if(!blob)return;const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='nexo-edited.png';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);},'image/png');
    message('PNG exported. Erased areas remain transparent.');
  };
  reset();
  return {reset};
}
