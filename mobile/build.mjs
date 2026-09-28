import {build} from 'esbuild';
import {createHash} from 'node:crypto';
import {mkdir,cp,writeFile,readFile,rm} from 'node:fs/promises';
await rm('dist',{recursive:true,force:true});
await mkdir('dist',{recursive:true});
// Wllama 3.6.1's abort handler assumes a string; WebKit can return an Error.
// Preserve the actual error instead of masking it with `replace is not a function`.
let abortPatched=false;
const normalizeAbort={name:'wllama-abort-message',setup(builder){builder.onLoad({filter:/@wllama[\\/]wllama[\\/]esm[\\/]index\.js$/},async({path})=>{const source=await readFile(path,'utf8'),needle='let newMsg = message.replace(';
  if(source.split(needle).length!==2)throw Error('Recheck Wllama abort-message patch after dependency changes');
  abortPatched=true;
  return {contents:source.replace(needle,'let newMsg = String(message?.message || message).replace(').replace('rawStack.replace(/\\|/g,', 'String(rawStack || \'\').replace(/\\|/g,').replace('yield Debug.decodeStackTrace(stack, isCompatBuild);', 'yield Debug.decodeStackTrace(stack || \'\', isCompatBuild).catch(() => String(stack || \'\'));'),loader:'js'};});}};
await build({entryPoints:['src/app.js','src/inference.js'],outdir:'dist',bundle:true,format:'esm',platform:'browser',minify:true,define:{'process.env.NODE_ENV':'"production"'},external:[],plugins:[normalizeAbort]});
if(!abortPatched)throw Error('Wllama abort-message adapter was not included in the browser bundle');
for(const name of ['index.html','style.css','manifest.webmanifest','icon.svg','sw.js','LFM-LICENSE.txt','LLAMA-CPP-LICENSE.txt'])await cp('src/'+name,'dist/'+name);
await cp('node_modules/@wllama/wllama/esm/wasm/wllama.wasm','dist/wllama.wasm');
await mkdir('dist/compat',{recursive:true});
for(const name of ['wllama.js','wllama.wasm'])await cp('node_modules/@wllama/wllama-compat/wasm/'+name,'dist/compat/'+name);
await cp('node_modules/@wllama/wllama/LICENCE','dist/WLLAMA-LICENSE.txt');
const files=['./','./index.html','./app.js','./inference.js','./style.css','./manifest.webmanifest','./icon.svg','./wllama.wasm','./LFM-LICENSE.txt','./WLLAMA-LICENSE.txt','./LLAMA-CPP-LICENSE.txt','./compat/wllama.js','./compat/wllama.wasm'];
const hash=createHash('sha256');for(const file of files.filter(x=>x!=='./'))hash.update(await readFile('dist/'+file.slice(2)));
let sw=(await readFile('dist/sw.js','utf8')).replace('nexo-mobile-0.19.2','nexo-mobile-'+hash.digest('hex').slice(0,16));await writeFile('dist/sw.js',sw.replace('/*PRECACHE*/[]',JSON.stringify(files)));
console.log('Standalone mobile companion built in mobile/dist');
