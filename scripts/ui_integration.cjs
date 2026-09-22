const {JSDOM,VirtualConsole}=require(process.env.NEXO_JSDOM_MODULE || 'jsdom');
const path=require('path'), os=require('os');
const root=path.resolve(__dirname,'..');
const fs=require('fs');
const assert=require('assert');
const directory=fs.mkdtempSync(path.join(os.tmpdir(),'nexo-ui-'));
const child=require('child_process').spawn(process.env.NEXO_PYTHON || (process.platform==='win32'?'python':'python3'),['-c',"from unittest.mock import patch\nfrom nexo7.desktop import main\nwith patch('nexo7.setup.local_daemon', side_effect=ValueError('Docker is missing (UI test fixture)')):\n    main()\n",'--no-open','--data-dir',directory],{cwd:root,stdio:'ignore'});
child.on('exit',()=>fs.rmSync(directory,{recursive:true,force:true}));
let access;
const errors=[];
const virtualConsole=new VirtualConsole();
virtualConsole.on('jsdomError',e=>errors.push(e.message));
async function waitFor(predicate,ms=10000){const end=Date.now()+ms;while(!predicate()){if(Date.now()>end)throw new Error('UI state did not arrive');await new Promise(r=>setTimeout(r,50));}}
(async()=>{
 await waitFor(()=>fs.existsSync(directory+'/access.json'));
 access=JSON.parse(fs.readFileSync(directory+'/access.json','utf8'));
 const dom=await JSDOM.fromURL(access.url,{runScripts:'dangerously',resources:'usable',pretendToBeVisual:true,virtualConsole,
 beforeParse(w){w.fetch=(url,opts)=>fetch(new URL(url,access.url),opts);w.HTMLElement.prototype.scrollIntoView=function(){};w.confirm=()=>true;}});
 const w=dom.window,d=w.document;
 try {
  await waitFor(()=>d.getElementById('setup-view')&&!d.getElementById('setup-view').hidden);
  assert.equal(d.documentElement.lang,'en');
  d.getElementById('check-system').click();
  await waitFor(()=>d.getElementById('setup-requirements').textContent.includes('Docker is missing'));
  assert(d.getElementById('start-local').disabled);
  d.getElementById('try-demo').click();
  assert(d.getElementById('setup-view').hidden);
  d.getElementById('prompt').value='/calc 24.5 * 40';
  d.getElementById('composer').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
  await waitFor(()=>[...d.querySelectorAll('.assistant .message-text')].some(e=>e.textContent==='980.0'));
  d.getElementById('memory-tab').click();
  d.getElementById('doc-title').value='UI integration fixture';
  d.getElementById('doc-content').value='<img src=x onerror=alert(1)> Test fixture with literal HTML.';
  d.getElementById('memory-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
  await waitFor(()=>[...d.querySelectorAll('.document-card h3')].some(e=>e.textContent==='UI integration fixture'));
  assert(!d.querySelector('.document-card img'));
  d.getElementById('chat-tab').click();
  assert(!d.getElementById('chat-view').hidden);
  d.getElementById('setup-tab').click();
  assert(!d.getElementById('setup-view').hidden);
  d.getElementById('performance').value='fast';
  d.getElementById('reply-style').value='detailed';
  d.getElementById('save-preferences').click();
  await waitFor(()=>d.getElementById('preferences-status').textContent.includes('Saved.'));
  const privateURL=new URL(access.url);
  const key=new URLSearchParams(privateURL.hash.slice(1)).get('token');
  const request=async(route,method='GET',body)=>{
   const response=await fetch(new URL(route,access.url),{method,headers:{'X-Nexo-Key':key,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
   assert(response.ok,route+' '+response.status);return response.json();
  };
  assert.equal((await request('/api/preferences')).performance,'fast');
  const unauthorized=await fetch(new URL('/api/artifacts',access.url));assert.equal(unauthorized.status,401);
  d.getElementById('chat-tab').click();
  const useful=[...d.querySelectorAll('.assistant button')].find(b=>b.textContent.includes('useful'));
  assert(useful);useful.click();
  await waitFor(()=>useful.disabled);
  assert((await request('/api/documents')).documents.some(x=>x.source.includes('user-approved')));
  d.getElementById('workspace-tab').click();
  d.getElementById('artifact-name').value='example.py';
  d.getElementById('artifact-content').value='print("review before running")';
  d.getElementById('artifact-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
  await waitFor(()=>d.getElementById('artifacts').textContent.includes('example.py'));
  const saved=(await request('/api/artifacts')).artifacts[0];
  assert.equal((await request('/api/artifacts/'+saved.id)).content,'print("review before running")');
  const remove=[...d.querySelectorAll('#artifacts button')].find(b=>b.textContent.includes('Delete'));
  assert(remove);remove.click();
  await waitFor(()=>!d.getElementById('artifacts').textContent.includes('example.py'));
  assert.deepEqual(errors,[]);
  const result={environment:'JSDOM with real local HTTP server; not a rendered-browser layout test',passed:true,checks:['English setup view','missing-Docker explanation','download disabled without prerequisites','demo navigation','calculator response','document import','literal HTML handling','setup navigation','persistent preferences','explicitly approved example','authenticated artifact API','workspace create/read/delete','no JavaScript errors']};
  fs.mkdirSync(path.join(root,'reports'),{recursive:true});
  fs.writeFileSync(path.join(root,'reports/ui-integration.json'),JSON.stringify(result,null,2));
  console.log(JSON.stringify(result));
 } finally {w.close();child.kill('SIGINT');}

})().catch(e=>{console.error(e);child.kill('SIGKILL');process.exitCode=1;});
