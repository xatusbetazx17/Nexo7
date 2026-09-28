'use strict';
const $=id=>document.getElementById(id);
let key=new URLSearchParams(location.hash.slice(1)).get('key')||'';
try{if(key)sessionStorage.setItem('nexo-companion-key',key);else key=sessionStorage.getItem('nexo-companion-key')||'';}catch{}
history.replaceState(null,'',location.pathname);
function add(text,role){const item=document.createElement('article');item.className=role;item.textContent=text;$('messages').append(item);item.scrollIntoView({block:'end',behavior:'smooth'});}
$('clear').onclick=()=>$('messages').replaceChildren();
function appearance(){document.body.dataset.color=$('color').value;$('avatar').textContent=$('face').value;try{localStorage.setItem('nexo-companion-look',JSON.stringify({color:$('color').value,face:$('face').value}));}catch{}}
try{const look=JSON.parse(localStorage.getItem('nexo-companion-look')||'{}');if(['blue','violet','green','rose'].includes(look.color))$('color').value=look.color;if(['🤖','🐱','◉'].includes(look.face))$('face').value=look.face;}catch{}appearance();$('color').onchange=appearance;$('face').onchange=appearance;
async function picture(file){
 if(!file)return [];
 if(file.size>4000000)throw Error('Choose an image smaller than 4 MB.');
 const url=URL.createObjectURL(file);
 try{const img=new Image();await new Promise((resolve,reject)=>{img.onload=resolve;img.onerror=()=>reject(Error('Cannot read this image.'));img.src=url;});
 const scale=Math.min(1,512/Math.max(img.width,img.height)),canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(img.width*scale));canvas.height=Math.max(1,Math.round(img.height*scale));canvas.getContext('2d').drawImage(img,0,0,canvas.width,canvas.height);return [canvas.toDataURL('image/png').split(',')[1]];
 }finally{URL.revokeObjectURL(url);}
}
$('form').onsubmit=async e=>{e.preventDefault();$('send').disabled=true;$('status').textContent='Waiting for your PC…';
 try{if(!key)throw Error('Open the private companion link shown in Nexo Settings on your PC.');const message=$('question').value.trim();const images=await picture($('picture').files[0]);add(message,'user');
 const response=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json','X-Nexo-Companion':key},body:JSON.stringify({message,images})});const data=await response.json();if(!response.ok)throw Error(data.error||'Request failed');add(data.answer,'assistant');$('question').value='';$('picture').value='';$('status').textContent=data.status==='incomplete'?'Reply reached the local output limit.':'Answered locally on your PC.';
 }catch(error){$('status').textContent=error.message;}finally{$('send').disabled=false;}};
