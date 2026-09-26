import {pipeline,env,TextStreamer} from '@huggingface/transformers';
import {modelCache} from './model-cache.js';
env.useCustomCache=true;env.customCache=modelCache;
const MODEL='onnx-community/LFM2-350M-ONNX',REV='5bc4b3e8cfd21660c0b1b9faa447ffbd9926b829';
env.allowLocalModels=false;env.useBrowserCache=true;env.backends.onnx.wasm.numThreads=1;env.backends.onnx.wasm.proxy=false;env.backends.onnx.wasm.wasmPaths=new URL('./ort/',self.location).href;
let generator=null,busy=false;
self.onmessage=async({data})=>{
 if(busy){self.postMessage({type:'error',message:'Wait for the current local operation'});return;}
 busy=true;
 try{
  if(data.action==='load'){
   env.allowRemoteModels=true;
   generator=await pipeline('text-generation',MODEL,{revision:REV,dtype:'q4',device:'wasm',progress_callback:x=>self.postMessage({type:'progress',message:x.status+(x.progress?' '+Math.round(x.progress)+'%':'')})});
   for(const file of ['model_q4.onnx','model_q4.onnx_data']){
   const cached=await modelCache.match('https://huggingface.co/'+MODEL+'/resolve/'+REV+'/onnx/'+file);
   if(!cached)throw Error('The model ran but could not be saved offline. Free browser storage and download it again.');
   await cached.body.cancel();
   }
   self.postMessage({type:'ready'});
  }else if(data.action==='chat'){
   if(!generator)throw Error('Download or load the local model first');
   const streamer=new TextStreamer(generator.tokenizer,{skip_prompt:true,skip_special_tokens:true,callback_function:text=>self.postMessage({type:'token',text})});
   const messages=structuredClone(data.messages);
   while(generator.tokenizer.apply_chat_template(messages,{tokenize:true,return_tensor:false,add_generation_prompt:true}).length>512){
    if(messages.length>2)messages.splice(1,1);else{messages[1].content=messages[1].content.slice(0,Math.floor(messages[1].content.length*.8));if(!messages[1].content)throw Error('Message cannot fit the mobile context');}
   }
   const result=await generator(messages,{max_new_tokens:128,do_sample:false,streamer});
   const generated=result[0].generated_text;self.postMessage({type:'answer',text:Array.isArray(generated)?generated.at(-1).content:String(generated)});
  }
 }catch(e){self.postMessage({type:'error',message:String(e.message).slice(0,350)});}finally{busy=false;}
};
