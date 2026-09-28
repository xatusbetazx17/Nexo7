// Exercise actual browser encoders, files and cancellation (not mocked renderers).
const assert=require('assert');
module.exports=async function checkMedia(page){
 await page.locator('#media-title').fill('A sunny day');
 await page.locator('#media-scene').selectOption('chicken');
 await page.locator('#media-image').click();await page.locator('#media-output img').waitFor();
 assert.equal(await page.locator('#media-output img').evaluate(async img=>{await img.decode();return img.naturalWidth;}),640);
 await page.locator('#media-draw').check();await page.locator('#media-canvas').click({position:{x:50,y:50}});
 const drawn=await page.locator('#media-canvas').evaluate(c=>c.toDataURL());
 await page.locator('#media-clear-ink').click();assert.notEqual(await page.locator('#media-canvas').evaluate(c=>c.toDataURL()),drawn);
 await page.locator('#media-mode').selectOption('music');
 await page.locator('#media-tempo').fill('120');await page.locator('#media-bars').selectOption('2');await page.locator('#media-music').click();
 await page.waitForFunction(()=>{const a=document.querySelector('#media-output audio');return a&&Number.isFinite(a.duration);});
 assert(Math.abs(await page.locator('#media-output audio').evaluate(a=>a.duration)-4)<.05);
 assert.equal(await page.locator('#media-output a[download="Nexo-music.mid"]').count(),1);
 await page.locator('#media-output audio').evaluate(async a=>{await a.play();a.pause();});
 const supported=await page.evaluate(()=>!!HTMLCanvasElement.prototype.captureStream&&typeof MediaRecorder!=='undefined'&&['video/mp4;codecs=avc1.42E01E,mp4a.40.2','video/webm;codecs=vp8,opus','video/mp4','video/webm'].some(t=>MediaRecorder.isTypeSupported(t)));
 await page.locator('#media-mode').selectOption('video');
 await page.locator('#media-seconds').selectOption('4');
 await page.locator('#media-video').click();
 if(supported){
   await page.locator('#media-output video').waitFor({timeout:25000});
   await page.waitForFunction(()=>{const v=document.querySelector('#media-output video');return v&&v.videoWidth>0;},{},{timeout:10000});
   assert.equal(await page.locator('#media-output video').evaluate(v=>v.videoWidth),640);
   await page.locator('#media-output video').evaluate(async v=>{await v.play();v.pause();});
   await page.locator('#media-video').click();await page.locator('#media-stop').click();
   await page.waitForFunction(()=>!document.querySelector('#media-video').disabled);
   assert.equal(await page.locator('#media-output video').count(),0,'Cancelled video must not be offered as finished');
 }else{
   await page.locator('#media-output a[download="Nexo-animation.gif"]').waitFor({timeout:25000});assert((await page.locator('#media-status').innerText()).includes('Animated GIF ready'));
 }
 await page.locator('#media-gif').click();await page.locator('#media-output a[download="Nexo-animation.gif"]').waitFor({timeout:25000});
 const downloaded=page.waitForEvent('download');await page.locator('#media-output a[download="Nexo-animation.gif"]').click();const gif=await downloaded;const gifBytes=require('fs').readFileSync(await gif.path());
 const result=require('child_process').spawnSync(process.env.NEXO_PYTHON||'python',['-c',"import sys,io;from PIL import Image;im=Image.open(io.BytesIO(sys.stdin.buffer.read()));assert im.size==(320,180);assert im.n_frames==32;im.seek(31);im.load()"],{input:Buffer.from(gifBytes)});assert.equal(result.status,0,result.stderr?.toString());
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 return {videoEncoded:supported};
};
