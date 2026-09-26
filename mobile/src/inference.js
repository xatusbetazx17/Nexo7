import {Wllama} from '@wllama/wllama';
import {modelCache} from './model-cache.js';
const URL_MODEL='https://huggingface.co/LiquidAI/LFM2.5-350M-GGUF/resolve/657e078c94084481950a2d555a941481f715536b/LFM2.5-350M-Q4_K_M.gguf';
const SIZE=229312224,SHA='7e6f72643caafc9a68256686638c4d7916f2cec76d1df478d4c3ddcd95a6aed4';
let generator=null,busy=false;
const progress=message=>self.postMessage({type:'progress',message});
self.onmessage=async({data})=>{
 if(busy){self.postMessage({type:'error',message:'Wait for the current local operation'});return;}
 busy=true;
 try{
  if(data.action==='load'){
   progress('Checking downloaded model…');
   let cached=await modelCache.match(URL_MODEL);
   if(!cached){
    progress('Downloading local model · 230 MB…');
    const response=await fetch(URL_MODEL);
    if(!response.ok)throw Error('The model download failed. Check the connection and try again.');
    await modelCache.put(URL_MODEL,response);
    cached=await modelCache.match(URL_MODEL);
   }
   if(!cached)throw Error('Could not save the model offline. Free browser storage and try again.');
   const blob=await cached.blob();
   progress('Verifying model…');
   const digest=blob.size===SIZE?Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await blob.arrayBuffer())),x=>x.toString(16).padStart(2,'0')).join(''):'';
   if(digest!==SHA)throw Error('Model integrity check failed. Remove downloaded models in Settings, then download again.');
   generator=new Wllama({default:new URL('./wllama.wasm',self.location).href},{allowOffline:true,suppressNativeLog:true,logger:{debug(){},log(){},warn(){},error(){}}});
   generator.setCompat({worker:new URL('./compat/wllama.js',self.location).href,wasm:new URL('./compat/wllama.wasm',self.location).href});
   progress('Loading local model…');
   await generator.loadModel([blob],{n_ctx:2048,n_batch:128,n_ubatch:64,n_threads:1,n_gpu_layers:0,offload_kqv:false,n_parallel:1,seed:42,reasoning:false});
   self.postMessage({type:'ready'});
  }else if(data.action==='chat'){
   if(!generator)throw Error('Download or load the local model first');
   const messages=structuredClone(data.messages),encoder=new TextEncoder();
   // Byte fallback cannot require more tokens than UTF-8 bytes. Reserve room
   // for the chat template and response within the fixed 2048-token context.
   while(messages.reduce((n,m)=>n+encoder.encode(m.content).length,0)>1600&&messages.length>2)messages.splice(1,1);
   if(messages.reduce((n,m)=>n+encoder.encode(m.content).length,0)>1600)throw Error('Please shorten this question for the mobile model. Longer tasks work best on your desktop.');
   let answer='';
   await generator.createChatCompletion({messages,max_tokens:128,temperature:0,seed:42,penalty_repeat:1.05,stream:true,onData:chunk=>{const text=chunk.choices?.[0]?.delta?.content||'';answer+=text;if(text)self.postMessage({type:'token',text});}});
   if(!answer.trim())throw Error('The local model returned no text. Try a shorter question.');
   self.postMessage({type:'answer',text:answer});
  }
 }catch(e){self.postMessage({type:'error',message:String(e.message).slice(0,350)});}finally{busy=false;}
};
