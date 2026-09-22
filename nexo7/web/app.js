"use strict";
const $ = id => document.getElementById(id);
const fragment = new URLSearchParams(location.hash.slice(1));
let token = fragment.get("token") || sessionStorage.getItem("nexo-token") || "";
if (token) sessionStorage.setItem("nexo-token", token);
history.replaceState(null, "", location.pathname);
let session = sessionStorage.getItem("nexo-session") || crypto.randomUUID();
sessionStorage.setItem("nexo-session", session);
let conversation = [], busy = false;

function error(message="") { $("error").textContent = message; $("error").hidden = !message; }
async function api(path, method="GET", body) {
  const response = await fetch(path, {method, headers:{"X-Nexo-Key":token,"Content-Type":"application/json"}, body:body === undefined ? undefined : JSON.stringify(body)});
  const data = await response.json();
  if (response.status === 401) $("login").hidden = false;
  if (!response.ok) throw new Error(data.error || "Could not complete the request");
  return data;
}
function node(tag, text, className="") { const el=document.createElement(tag); el.textContent=text; el.className=className; return el; }
function message(role, text, result, question="") {
  $("welcome").hidden = true;
  const article = node("article", "", "message " + role);
  article.append(node("div", role === "user" ? "YOU" : "NEXO 7", "message-label"));
  article.append(node("div", text, "message-text"));
  if (result) {
    const s=result.stats;
    const line = `${s.model_calls} calls · ${s.input_tokens+s.output_tokens} reported tokens · ${(s.elapsed_ms/1000).toFixed(2)} s${s.cache_hit ? " · Cache" : ""}${s.provider === "openai" && s.estimated_cost_usd !== null ? " · Estimated API $" + s.estimated_cost_usd.toFixed(6) : ""}`;
    article.append(node("div", line, "metrics"));
    if (result.sources.length) {
      const details=document.createElement("details"); details.append(node("summary",`${result.sources.length} retrieved sources`));
      for (const source of result.sources) {
        const p=node("p",`[${source.id}] ${source.title}${source.year ? " · " + source.year : ""}`);
        if (source.url && /^https:\/\/pubmed\.ncbi\.nlm\.nih\.gov\/\d+\/$/.test(source.url)) {
          const link=node("a"," Open record ↗");link.href=source.url;link.target="_blank";link.rel="noopener noreferrer";p.append(link);
        }
        if (source.retraction_flag) p.append(node("strong"," · Retraction notice"));
        details.append(p);
      }
      article.append(details);
    }
    if(desktopMode){
      const actions=node("div","","language-controls");
      const create=node("button","Create file","quiet");
      create.onclick=()=>{const code=text.match(/```[^\n]*\n([\s\S]*?)```/);$("artifact-content").value=code?code[1]:text;showWorkspace();};actions.append(create);
      if(!result.private && question && result.status==="completed") {
        for(const [rating,label] of [["useful","Save as useful example"],["incorrect","Mark incorrect"]]){
          const feedback=node("button",label,"quiet");feedback.onclick=async()=>{
            if(rating==="useful"&&!confirm("Save this question and answer as a searchable example? This does not verify its accuracy or retrain the model."))return;
            try{await api("/api/feedback","POST",{question,answer:text,rating});feedback.disabled=true;feedback.textContent=rating==="useful"?"Example saved":"Marked; answer cache cleared";await loadDocuments();}catch(exc){error(exc.message);}
          };actions.append(feedback);
        }
      }
      article.append(actions);
    }
    for(const warning of result.warnings) article.append(node("p",warning,"warning"));
  }
  $("messages").append(article);
  article.scrollIntoView({behavior:"smooth",block:"end"});
}
async function initialize(first=true) {
  try {
    const config=await api("/api/status"); $("login").hidden=true;
    $("provider").textContent = config.provider === "demo" ? "Demo · no AI model" : `Configured: ${config.provider} · ${config.model}`;
    const preferences=await api("/api/preferences");
    $("performance").value=preferences.performance;$("reply-style").value=preferences.style;$("auto-start").checked=preferences.auto_start;$("cpu-only").checked=preferences.cpu_only;
    const language = preferences.response_language || config.response_language || "auto";
    if([...$("language").options].some(o=>o.value===language)) $("language").value=language;
    $("resource-note").textContent = config.local_ram_limit_bytes ? `Runtime RAM: configured limit ${(config.local_ram_limit_bytes/1e9).toFixed(1)} GB · ${config.local_backend}` : "";
    $("privacy-note").textContent = config.provider === "openai" ? "Your queries and relevant excerpts will be sent to OpenAI. Local history is not encrypted." : "Memory and history stay on this computer, without encryption. PubMed needs an Internet connection.";
    if (!config.persist_history) { $("private").checked=true; $("private").disabled=true; }
    const data=await api("/api/history?session="+encodeURIComponent(session));
    $("messages").replaceChildren(); conversation=data.messages; for(const m of conversation) message(m.role,m.content);
    await loadDocuments();
    desktopMode=Boolean(config.desktop);$("workspace-tab").hidden=!desktopMode; $("setup-tab").hidden=!desktopMode; $("quit").hidden=!desktopMode;
    if(first && desktopMode) {showSetup(); clearTimeout(setupTimer); pollSetup();}
  } catch(exc) { error(exc.message); }
}
$("connect").onclick=()=>{token=$("token").value;sessionStorage.setItem("nexo-token",token);error();initialize();};
$("composer").onsubmit=async event=>{
  event.preventDefault(); if(busy) return;
  const text=$("prompt").value.trim(); if(!text) return;
  busy=true;$("send").disabled=true;$("send").textContent="Working…";error();
  message("user",text);conversation.push({role:"user",content:text});$("prompt").value="";
  try {
    const result=await api("/api/chat","POST",{message:text,session,mode:$("mode").value,private:$("private").checked,language:$("language").value});
    message("assistant",result.answer,result,text);conversation.push({role:"assistant",content:result.answer,sources:result.sources,stats:result.stats});
  } catch(exc) {error(exc.message);}
  finally {busy=false;$("send").disabled=false;$("send").textContent="Send ↑";$("prompt").focus();}
};
$("prompt").onkeydown=event=>{if(event.key==="Enter"&&!event.shiftKey){event.preventDefault();$("composer").requestSubmit();}};
$("language").onchange=()=>sessionStorage.setItem("nexo-language",$("language").value);
for(const button of document.querySelectorAll("[data-prompt]")) button.onclick=()=>{$("prompt").value=button.dataset.prompt;$("prompt").focus();};
$("mode").onchange=()=>{$("research-notice").hidden=$("mode").value!=="research";$("prompt").maxLength=$("mode").value==="research"?500:8000;};
$("research-suggestion").onclick=()=>{$("mode").value="research";$("mode").onchange();$("prompt").value="sleep and cognition systematic review";$("prompt").focus();};
function view(memory) {hideSetup();$("workspace-view").hidden=true;$("workspace-tab").classList.remove("active");$("chat-view").hidden=memory;$("memory-view").hidden=!memory;$("chat-tab").classList.toggle("active",!memory);$("memory-tab").classList.toggle("active",memory);$("page-title").textContent=memory?"My knowledge.":"Let’s talk.";}
$("chat-tab").onclick=()=>view(false);$("memory-tab").onclick=()=>view(true);
$("new").onclick=()=>{if(busy)return;session=crypto.randomUUID();sessionStorage.setItem("nexo-session",session);conversation=[];$("messages").replaceChildren();$("welcome").hidden=false;error();view(false);};
$("export").onclick=()=>{const blob=new Blob([JSON.stringify({app:"Nexo 7",exported_at:new Date().toISOString(),conversation},null,2)],{type:"application/json"});const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="nexo7-conversation.json";a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);};
$("forget").onclick=async()=>{if(busy||!confirm("Clear local history for this conversation? Exported copies and provider data are managed separately."))return;try{await api("/api/history/"+encodeURIComponent(session),"DELETE");$("new").click();}catch(exc){error(exc.message);}};
async function loadDocuments(){
  const data=await api("/api/documents");$("documents").replaceChildren();
  for(const doc of data.documents){const card=node("div","","document-card");const info=node("div","");info.append(node("h3",doc.title),node("p",`${doc.characters.toLocaleString()} characters · ${doc.source}`,"muted small"));const button=node("button","Remove","quiet");button.onclick=async()=>{if(!confirm("Remove this document and its cache entries?"))return;try{await api("/api/documents/"+encodeURIComponent(doc.id),"DELETE");await loadDocuments();}catch(exc){alert(exc.message);}};card.append(info,button);$("documents").append(card);}
}
$("memory-form").onsubmit=async event=>{event.preventDefault();try{await api("/api/documents","POST",{title:$("doc-title").value,content:$("doc-content").value,source:"Added by user"});$("memory-form").reset();await loadDocuments();}catch(exc){alert(exc.message);}};
$("file").onchange=async()=>{const file=$("file").files[0];if(!file)return;if(file.size>500000){alert("The file must be at most 500 KB");return;}$("doc-title").value=file.name;$("doc-content").value=await file.text();};

let desktopMode = false, setupTimer = null, previousPhase = "", setupBusy = false;
function showSetup() {
  $("workspace-view").hidden=true;$("workspace-tab").classList.remove("active");
  $("setup-view").hidden = false; $("chat-view").hidden = true; $("memory-view").hidden = true;
  $("page-title").textContent = "Your local assistant.";
  $("chat-tab").classList.remove("active"); $("memory-tab").classList.remove("active");
  $("setup-tab").classList.add("active");
}
function hideSetup() {$("setup-view").hidden=true;$("setup-tab").classList.remove("active");}
function displayReport(report) {
  const hw=report.hardware, plan=report.plan;
  $("hardware-summary").textContent = `${hw.system} ${hw.machine} · ${hw.cpu_threads} CPU threads · ${(hw.available_bytes/1e9).toFixed(1)} GB available of ${(hw.total_bytes/1e9).toFixed(1)} GB RAM${hw.gpu_total_bytes ? ` · ${(hw.gpu_free_bytes/1e9).toFixed(1)} GB free NVIDIA VRAM` : ""}`;
  $("setup-requirements").textContent = report.requirements_ok ? "Requirements checked. Ready for setup." : report.error;
  $("model-summary").textContent = plan ? `${plan.profiles[0].model} · ${plan.backend.toUpperCase()} · ${(plan.ram_limit_bytes/1e9).toFixed(1)} GB RAM limit. Recommendation; actual loading is checked during setup.` : "No suitable model profile is currently available.";
  $("start-local").disabled = !report.requirements_ok || setupBusy || previousPhase==="ready";
}
async function pollSetup() {
  try {
    const state=await api("/api/setup"); setupBusy=state.phase==="preparing";
    $("setup-phase").textContent=state.phase==="ready"?"Ready to chat":state.phase==="preparing"?"Preparing your model…":state.phase==="error"?"Setup needs attention":"Waiting";
    $("setup-log").textContent=state.logs.join("\n")||"No downloads have started.";
    $("setup-log").scrollTop=$("setup-log").scrollHeight;
    $("setup-error").textContent=state.error||"";
    $("cancel-setup").hidden=!setupBusy; $("cpu-only").disabled=setupBusy||state.ready;
    $("check-system").disabled=setupBusy; $("start-local").disabled=setupBusy||state.ready||!state.report?.requirements_ok;
    if(state.report) displayReport(state.report);
    if(state.ready && previousPhase!=="ready") {
      $("try-demo").textContent="Start a conversation";
      await initialize(false); hideSetup();view(false);
    }
    previousPhase=state.phase;
    if(desktopMode) setupTimer=setTimeout(pollSetup,setupBusy?1500:5000);
  } catch(exc) {$("setup-error").textContent=exc.message;}
}
$("setup-tab").onclick=showSetup;
$("try-demo").onclick=()=>{hideSetup();view(false);};
$("cpu-only").onchange=()=>{$("start-local").disabled=true;$("setup-requirements").textContent="Check requirements again after changing acceleration.";};
$("check-system").onclick=async()=>{
  $("check-system").disabled=true;$("setup-error").textContent="";$("setup-requirements").textContent="Checking your computer and Docker…";
  try{await savePreferences();displayReport(await api("/api/setup/check","POST",{cpu_only:$("cpu-only").checked}));}
  catch(exc){$("setup-error").textContent=exc.message;}
  finally{$("check-system").disabled=setupBusy;}
};
$("start-local").onclick=async()=>{
  $("start-local").disabled=true;$("setup-error").textContent="";
  try{await savePreferences();await api("/api/setup/start","POST",{cpu_only:$("cpu-only").checked,language:$("language").value});clearTimeout(setupTimer);await pollSetup();}
  catch(exc){$("setup-error").textContent=exc.message;}
};
$("cancel-setup").onclick=async()=>{try{await api("/api/setup/cancel","POST",{});$("setup-error").textContent="Cancellation requested. Waiting for the current operation to stop.";}catch(exc){$("setup-error").textContent=exc.message;}};
$("quit").onclick=async()=>{
  if(!confirm("Quit Nexo and stop its local model? Downloaded models and saved notes will be kept.")) return;
  try{await api("/api/shutdown","POST",{});desktopMode=false;clearTimeout(setupTimer);document.body.replaceChildren(node("main","Nexo is closing and stopping its model. You can close this tab."));}
  catch(exc){error(exc.message);}
};
async function savePreferences(){
 return api("/api/preferences","POST",{performance:$("performance").value,style:$("reply-style").value,auto_start:$("auto-start").checked,cpu_only:$("cpu-only").checked,response_language:$("language").value});
}
$("save-preferences").onclick=async()=>{try{await savePreferences();$("preferences-status").textContent="Saved. Hardware settings apply at the next local start.";}catch(exc){$("preferences-status").textContent=exc.message;}};
$("language").onchange=async()=>{try{await api("/api/preferences","POST",{response_language:$("language").value});}catch(exc){error(exc.message);}};
function showWorkspace(){hideSetup();$("chat-view").hidden=true;$("memory-view").hidden=true;$("workspace-view").hidden=false;$("chat-tab").classList.remove("active");$("memory-tab").classList.remove("active");$("workspace-tab").classList.add("active");$("page-title").textContent="My workspace.";loadArtifacts().catch(exc=>$("artifact-status").textContent=exc.message);}
$("workspace-tab").onclick=showWorkspace;
async function loadArtifacts(){
 const data=await api("/api/artifacts");$("artifacts").replaceChildren();
 for(const item of data.artifacts){
  const card=node("div","","document-card"),label=node("div",`${item.name} · ${item.bytes.toLocaleString()} bytes`),download=node("button","Download","quiet"),remove=node("button","Delete","quiet");
  download.onclick=async()=>{try{const file=await api("/api/artifacts/"+item.id);const url=URL.createObjectURL(new Blob([file.content],{type:"application/octet-stream"}));const a=node("a","");a.href=url;a.download=file.name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(exc){$("artifact-status").textContent=exc.message;}};
  remove.onclick=async()=>{if(!confirm("Permanently delete this workspace file?"))return;try{await api("/api/artifacts/"+item.id,"DELETE");await loadArtifacts();}catch(exc){$("artifact-status").textContent=exc.message;}};
  card.append(label,download,remove);$("artifacts").append(card);
 }
}
$("artifact-form").onsubmit=async event=>{event.preventDefault();try{await api("/api/artifacts","POST",{name:$("artifact-name").value,content:$("artifact-content").value});$("artifact-status").textContent="Saved locally. Review code before executing it.";await loadArtifacts();}catch(exc){$("artifact-status").textContent=exc.message;}};
initialize();
