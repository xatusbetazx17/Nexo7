// Chunked IndexedDB storage avoids large single-response Cache API limits.
// Only public model files use this database; encrypted profiles live separately.
const DB='nexo-model-cache-v1',CHUNK=8*1024*1024,MAX=900*1024*1024;
function open(){return new Promise((resolve,reject)=>{const request=indexedDB.open(DB,1);request.onupgradeneeded=()=>{request.result.createObjectStore('files');request.result.createObjectStore('chunks');};request.onerror=()=>reject(request.error);request.onsuccess=()=>resolve(request.result);});}
function transaction(db,store,mode,action){return new Promise((resolve,reject)=>{const tx=db.transaction(store,mode);let value;const req=action(tx.objectStore(store));req.onsuccess=()=>{value=req.result;};tx.oncomplete=()=>resolve(value);tx.onabort=tx.onerror=()=>reject(tx.error||Error('Model cache transaction failed'));});}
export const modelCache={
 async match(name){const db=await open();try{const meta=await transaction(db,'files','readonly',s=>s.get(String(name)));if(!meta){db.close();return undefined;}db.close();let index=0;return new Response(new ReadableStream({async pull(controller){try{if(index>=meta.count){controller.close();return;}const readDb=await open();let bytes;try{bytes=await transaction(readDb,'chunks','readonly',s=>s.get(meta.id+':'+index++));}finally{readDb.close();}if(!bytes)throw Error('Model cache is incomplete; download the model again');controller.enqueue(new Uint8Array(bytes));}catch(e){controller.error(e);}}},{highWaterMark:0}),{headers:meta.headers});}catch(e){db.close();throw e;}},
 async put(name,response){const db=await open(),id=crypto.randomUUID(),reader=response.body.getReader();let count=0,total=0,buffer=new Uint8Array(CHUNK),used=0;
  const flush=async()=>{await transaction(db,'chunks','readwrite',s=>s.put(buffer.slice(0,used).buffer,id+':'+count));count++;used=0;};
  try{for(;;){const {done,value}=await reader.read();if(done)break;total+=value.length;if(total>MAX)throw Error('Model file exceeds the 900 MB mobile download limit');let offset=0;while(offset<value.length){const n=Math.min(CHUNK-used,value.length-offset);buffer.set(value.subarray(offset,offset+n),used);used+=n;offset+=n;if(used===CHUNK)await flush();}}if(used)await flush();
   const old=await transaction(db,'files','readonly',s=>s.get(String(name)));const headers={'Content-Type':response.headers.get('Content-Type')||'application/octet-stream','Content-Length':String(total)};
   await transaction(db,'files','readwrite',s=>s.put({id,count,total,headers},String(name)));
   if(old)for(let i=0;i<old.count;i++)await transaction(db,'chunks','readwrite',s=>s.delete(old.id+':'+i));
  }catch(e){for(let i=0;i<count;i++)await transaction(db,'chunks','readwrite',s=>s.delete(id+':'+i)).catch(()=>{});throw e;}finally{reader.releaseLock();db.close();}
 }
};
