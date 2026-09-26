const encode=new TextEncoder(),decode=new TextDecoder();
const hex=b=>Array.from(b,x=>x.toString(16).padStart(2,'0')).join('');
const fromHex=s=>{if(typeof s!=='string'||!/^[a-f0-9]{64}$/.test(s))throw Error('Invalid identity key');return Uint8Array.from(s.match(/../g),x=>parseInt(x,16));};
export function b64(b){let text='';for(let i=0;i<b.length;i+=8192)text+=String.fromCharCode(...b.subarray(i,i+8192));return btoa(text);}
const raw=s=>Uint8Array.from(atob(s),x=>x.charCodeAt(0));
async function key(phrase,salt){if(typeof phrase!=='string'||phrase.length<16||phrase.length>512)throw Error('Use a pairing phrase of 16–512 characters');const base=await crypto.subtle.importKey('raw',encode.encode(phrase),'PBKDF2',false,['deriveKey']);return crypto.subtle.deriveKey({name:'PBKDF2',hash:'SHA-256',salt,iterations:600000},base,{name:'AES-GCM',length:256},false,['encrypt','decrypt']);}
export async function validate(p){
 if(!p||p.format!=='nexo-profile-v1'||encode.encode(JSON.stringify(p)).length>4000000)throw Error('Invalid or oversized profile');
 const seed=fromHex(p.identity?.private_key),publicKey=fromHex(p.identity?.public_key);
 const pkcs=new Uint8Array(48);pkcs.set([48,46,2,1,0,48,5,6,3,43,101,112,4,34,4,32]);pkcs.set(seed,16);
 let privateKey;
 try{privateKey=await crypto.subtle.importKey('pkcs8',pkcs,'Ed25519',false,['sign']);const pub=await crypto.subtle.importKey('raw',publicKey,'Ed25519',false,['verify']);const msg=encode.encode('Nexo profile identity check');if(!await crypto.subtle.verify('Ed25519',pub,await crypto.subtle.sign('Ed25519',privateKey,msg),msg))throw Error();}catch{throw Error('This browser cannot verify the profile identity. Use a current browser with Ed25519 support.');}
 if(p.identity.id!=='nexo:'+hex(new Uint8Array(await crypto.subtle.digest('SHA-256',publicKey))))throw Error('Identity mismatch');
 if(!Array.isArray(p.documents)||p.documents.length>200)throw Error('Profile limit: 200 notes');
 for(const d of p.documents)if(!d||typeof d.title!=='string'||!d.title.trim()||d.title.length>160||typeof d.content!=='string'||!d.content.trim()||d.content.length>200000||typeof d.source!=='string'||d.source.length>500)throw Error('Invalid note');
 if(!['neutral','friendly','coach','playful'].includes(p.preferences?.personality||'neutral'))throw Error('Invalid personality');
 if(!Array.isArray(p.reminders)||p.reminders.length>100)throw Error('Invalid reminders');
 for(const r of p.reminders)if(typeof r.text!=='string'||!r.text.trim()||r.text.length>500||typeof r.due!=='number'||!(r.due>0&&r.due<32503680000))throw Error('Invalid reminder');
 return p;
}
export async function decrypt(envelope,phrase){
 if(!envelope||envelope.format!=='nexo-transfer-v1'||envelope.kdf!=='PBKDF2-SHA256'||envelope.iterations!==600000||JSON.stringify(envelope).length>6000000)throw Error('Unsupported transfer file');
 let p;try{const salt=raw(envelope.salt),nonce=raw(envelope.nonce);if(salt.length!==16||nonce.length!==12)throw Error();p=JSON.parse(decode.decode(await crypto.subtle.decrypt({name:'AES-GCM',iv:nonce,additionalData:encode.encode('nexo-transfer-v1')},await key(phrase,salt),raw(envelope.ciphertext))));}catch{throw Error('Cannot unlock this profile. Check the pairing phrase and file.');}
 return validate(p);
}
export async function encrypt(p,phrase){await validate(p);const salt=crypto.getRandomValues(new Uint8Array(16)),nonce=crypto.getRandomValues(new Uint8Array(12));const ciphertext=await crypto.subtle.encrypt({name:'AES-GCM',iv:nonce,additionalData:encode.encode('nexo-transfer-v1')},await key(phrase,salt),encode.encode(JSON.stringify(p)));return {format:'nexo-transfer-v1',kdf:'PBKDF2-SHA256',iterations:600000,salt:b64(salt),nonce:b64(nonce),ciphertext:b64(new Uint8Array(ciphertext))};}
export async function create(){const pair=await crypto.subtle.generateKey('Ed25519',true,['sign','verify']);const pkcs=new Uint8Array(await crypto.subtle.exportKey('pkcs8',pair.privateKey)),publicKey=new Uint8Array(await crypto.subtle.exportKey('raw',pair.publicKey));return {format:'nexo-profile-v1',identity:{private_key:hex(pkcs.slice(-32)),public_key:hex(publicKey),id:'nexo:'+hex(new Uint8Array(await crypto.subtle.digest('SHA-256',publicKey)))},preferences:{personality:'friendly',style:'concise',response_language:'auto',adapt_tone:false},documents:[],reminders:[]};}
export function storage(mode,value){return new Promise((resolve,reject)=>{const req=indexedDB.open('nexo-mobile',1);req.onupgradeneeded=()=>req.result.createObjectStore('profile');req.onerror=()=>reject(req.error);req.onsuccess=()=>{const db=req.result,tx=db.transaction('profile',mode==='get'?'readonly':'readwrite'),store=tx.objectStore('profile');const r=mode==='get'?store.get('encrypted'):mode==='delete'?store.delete('encrypted'):store.put(value,'encrypted');r.onsuccess=()=>{const result=r.result;tx.oncomplete=()=>{db.close();resolve(result);};};tx.onerror=()=>{db.close();reject(tx.error);};};});}
