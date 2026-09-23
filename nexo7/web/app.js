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
    if(result.companion){
      const steps=node('details','');steps.append(node('summary','How Nexo handled this request'));
      for(const step of result.companion.steps)steps.append(node('p',step.action+': '+step.result));
      if(result.sources.length)steps.append(node('p',result.companion.evidence.domains.length+' source domains. Agreement and truth are not automatically verified.'));
      article.append(steps);
    }
    const s=result.stats;
    const line = `${s.model_calls} calls · ${s.input_tokens+s.output_tokens} reported tokens · ${(s.elapsed_ms/1000).toFixed(2)} s${s.cache_hit ? " · Cache" : ""}${s.provider === "openai" && s.estimated_cost_usd !== null ? " · Estimated API $" + s.estimated_cost_usd.toFixed(6) : ""}`;
    article.append(node("div", line, "metrics"));
    if(s.web_reused||s.network_requests)article.append(node("div",`${s.network_requests||0} search requests · ${s.web_reused?"Saved sources reused":"New excerpts retrieved"}${s.web_saved?" · Saved locally":""}`,"metrics"));
    if (result.sources.length) {
      const details=document.createElement("details"); details.append(node("summary",`${result.sources.length} retrieved sources`));
      for (const source of result.sources) {
        const p=node("p",`[${source.id}] ${source.title}${source.year ? " · " + source.year : ""}`);
        if (source.url && /^https:\/\/pubmed\.ncbi\.nlm\.nih\.gov\/\d+\/$/.test(source.url)) {
          const link=node("a"," Open record ↗");link.href=source.url;link.target="_blank";link.rel="noopener noreferrer";p.append(link);
        }
        if(source.id.startsWith("W") && safeWebLink(source.url)){
          const link=node("a"," Open web source ↗");link.href=source.url;link.target="_blank";link.rel="noopener noreferrer";p.append(link);
          p.append(node("small",` Retrieved ${source.retrieved_at} · ${source.source}`));
          const excerpt=node("pre",source.text);details.append(excerpt);
        }
        if (source.retraction_flag) p.append(node("strong"," · Retraction notice"));
        details.append(p);
      }
      article.append(details);
    }
    if(question && !result.sources.length && result.mode!=="web"){
      const lookup=node("button","Look up this topic online","quiet");
      lookup.onclick=()=>{$("mode").value="web";$("mode").onchange();$("prompt").value=question.slice(0,500);$("prompt").focus();};
      article.append(lookup);
    }
    if(desktopMode && ["completed","incomplete"].includes(result.status)){
      const actions=node("div","","language-controls");
      const create=node("button","Create file","quiet");
      create.onclick=()=>{const code=text.match(/```[^\n]*\n([\s\S]*?)```/);$("artifact-content").value=code?code[1]:text;showWorkspace();};actions.append(create);
      if(!result.private && question && result.status==="completed") {
        const correct=node("button","Correct / teach","quiet");
        correct.onclick=()=>{view(true);$("learn-question").value=question.slice(0,2000);$("learn-answer").value=text.slice(0,8000);$("learn-consent").checked=false;$("share-consent").checked=false;$("contribution-preview").replaceChildren();$("learning-panel").scrollIntoView();};actions.append(correct);
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
    $("language").value=language;
    $("resource-note").textContent = config.local_ram_limit_bytes ? `Native memory budget: ${(config.local_ram_limit_bytes/1e9).toFixed(1)} GB · ${config.local_backend}` : "";
    $("privacy-note").textContent = config.provider === "openai" ? "Your queries and relevant excerpts will be sent to OpenAI. Local history is not encrypted." : "Memory and history stay on this computer, without encryption. PubMed needs an Internet connection.";
    if (!config.persist_history) { $("private").checked=true; $("private").disabled=true; }
    const data=await api("/api/history?session="+encodeURIComponent(session));
    $("messages").replaceChildren(); conversation=data.messages; for(const m of conversation) message(m.role,m.content);
    await loadDocuments(); await loadLearning(); await loadWebSources();
    desktopMode=Boolean(config.desktop);$("workspace-tab").hidden=!desktopMode; $("setup-tab").hidden=!desktopMode; $("quit").hidden=!desktopMode;
    if(first && desktopMode) {showSetup(); clearTimeout(setupTimer); pollSetup();}
  } catch(exc) { error(exc.message); }
}
$("connect").onclick=()=>{token=$("token").value;sessionStorage.setItem("nexo-token",token);error();initialize();};
$("composer").onsubmit=async event=>{
  event.preventDefault(); if(busy) return;
  const text=$("prompt").value.trim(); if(!text) return;
  busy=true;$("send").disabled=true;$("send").textContent="Working…";error();
  const started=Date.now(); const progress=setInterval(()=>{$("send").textContent=`Working… ${Math.floor((Date.now()-started)/1000)}s`;},1000);
  message("user",text);conversation.push({role:"user",content:text});$("prompt").value="";
  try {
    const result=await api("/api/chat","POST",{message:text,session,mode:$("mode").value,private:$("private").checked,language:$("language").value,web_provider:$("web-provider").value,web_language:$("web-language").value,remember_web:$("remember-web").checked,refresh_web:$("refresh-web").checked,synthesize_web:$("synthesize-web").checked,allow_internet:$("allow-internet").checked});
    message("assistant",result.answer,result,text);conversation.push({role:"assistant",content:result.answer,sources:result.sources,stats:result.stats});
  } catch(exc) {error(exc.message);}
  finally {$("allow-internet").checked=false;clearInterval(progress);busy=false;$("send").disabled=false;$("send").textContent="Send ↑";$("prompt").focus();}
};
$("prompt").onkeydown=event=>{if(event.key==="Enter"&&!event.shiftKey){event.preventDefault();$("composer").requestSubmit();}};
$("language").onchange=()=>sessionStorage.setItem("nexo-language",$("language").value);
for(const button of document.querySelectorAll("[data-prompt]")) button.onclick=()=>{$("prompt").value=button.dataset.prompt;$("prompt").focus();};
$("mode").onchange=()=>{$("research-notice").hidden=$("mode").value!=="research";$("web-controls").hidden=!["web","companion"].includes($("mode").value);$("prompt").maxLength=["research","web"].includes($("mode").value)?500:8000;};
$("research-suggestion").onclick=()=>{$("mode").value="research";$("mode").onchange();$("prompt").value="sleep and cognition systematic review";$("prompt").focus();};
function view(memory) {if(memory){loadLearning().catch(exc=>error(exc.message));loadWebSources().catch(exc=>error(exc.message));}hideSetup();$("workspace-view").hidden=true;$("workspace-tab").classList.remove("active");$("chat-view").hidden=memory;$("memory-view").hidden=!memory;$("chat-tab").classList.toggle("active",!memory);$("memory-tab").classList.toggle("active",memory);$("page-title").textContent=memory?"My knowledge.":"Let’s talk.";}
$("chat-tab").onclick=()=>view(false);$("memory-tab").onclick=()=>view(true);
$("new").onclick=()=>{if(busy)return;$("allow-internet").checked=false;$("mode").value="companion";$("mode").onchange();session=crypto.randomUUID();sessionStorage.setItem("nexo-session",session);conversation=[];$("messages").replaceChildren();$("welcome").hidden=false;error();view(false);};
$("export").onclick=()=>{const blob=new Blob([JSON.stringify({app:"Nexo 7",exported_at:new Date().toISOString(),conversation},null,2)],{type:"application/json"});const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="nexo7-conversation.json";a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);};
$("forget").onclick=async()=>{if(busy||!confirm("Clear local history for this conversation? Exported copies and provider data are managed separately."))return;try{await api("/api/history/"+encodeURIComponent(session),"DELETE");$("new").click();}catch(exc){error(exc.message);}};
async function loadDocuments(){
  const data=await api("/api/documents");$("documents").replaceChildren();
  for(const doc of data.documents){const card=node("div","","document-card");const info=node("div","");info.append(node("h3",doc.title),node("p",`${doc.characters.toLocaleString()} characters · ${doc.source}`,"muted small"));const button=node("button","Remove","quiet");button.onclick=async()=>{if(!confirm("Remove this document and its cache entries?"))return;try{await api("/api/documents/"+encodeURIComponent(doc.id),"DELETE");await loadDocuments();}catch(exc){alert(exc.message);}};card.append(info,button);$("documents").append(card);}
}
$("memory-form").onsubmit=async event=>{event.preventDefault();try{await api("/api/documents","POST",{title:$("doc-title").value,content:$("doc-content").value,source:"Added by user"});$("memory-form").reset();await loadDocuments();}catch(exc){alert(exc.message);}};
$("file").onchange=async()=>{
 const file=$("file").files[0];if(!file)return;
 if(file.size>5000000){$("import-status").textContent="Import limit: 5 MB";return;}
 $("import-status").textContent="Extracting locally…";
 try{
  const encoded=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(",")[1]);r.onerror=reject;r.readAsDataURL(file);});
  const doc=await api("/api/import","POST",{name:file.name,data:encoded});
  $("doc-title").value=doc.title;$("doc-content").value=doc.content;$("import-status").textContent=doc.notice;
 }catch(exc){$("import-status").textContent=exc.message;}
};

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
  $("model-summary").textContent = plan ? `${plan.selected_model || plan.profiles[0].model} · ${plan.backend.toUpperCase()} · ${(plan.ram_limit_bytes/1e9).toFixed(1)} GB memory budget · ${(plan.reserved_host_bytes/1e9).toFixed(1)} GB additional free headroom. ${plan.guard_scope}. Actual loading is checked during setup.` : "No suitable model profile is currently available.";
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
  $("check-system").disabled=true;$("setup-error").textContent="";$("setup-requirements").textContent="Checking your computer and native memory budget…";
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
  const analyze=node("button","Analyze","quiet");
  analyze.onclick=async()=>{try{const data=await api("/api/inspect","POST",{filename:item.id});$("analysis-result").textContent=JSON.stringify(data,null,2);}catch(exc){$("analysis-result").textContent=exc.message;}};
  const discuss=node("button","Ask about file","quiet");
  discuss.onclick=()=>{view(false);$("mode").value="balanced";$("mode").onchange();$("prompt").value=`Read the workspace file with ID ${item.id} (${item.name}) and explain its contents.`;$("prompt").focus();};
  const repair=node("button","Propose syntax repair","quiet");
  repair.hidden=!/\.(py|json)$/.test(item.name);
  repair.onclick=()=>{view(false);$("mode").value="companion";$("mode").onchange();$("allow-internet").checked=false;$("prompt").value='/repair '+item.id;$("prompt").focus();};
  card.append(label,download,analyze,discuss,repair,remove);$("artifacts").append(card);
 }
}
$("artifact-form").onsubmit=async event=>{event.preventDefault();try{const saved=await api("/api/artifacts","POST",{name:$("artifact-name").value,content:$("artifact-content").value});$("artifact-status").textContent="Saved locally. Check: "+JSON.stringify(saved.verification)+". No code executed; syntax is not proof of correctness.";await loadArtifacts();}catch(exc){$("artifact-status").textContent=exc.message;}};
$("mode").onchange();
initialize();

$("workspace-file").onchange=async()=>{const file=$("workspace-file").files[0];if(!file)return;if(file.size>200000){$("artifact-status").textContent="Workspace file limit: 200 KB";return;}$("artifact-name").value=file.name;$("artifact-content").value=await file.text();$("artifact-status").textContent="Loaded into editor. Review and save to make it available to Nexo.";};

let pendingLearningPack=null;
function learningEntry(){return {question:$("learn-question").value,answer:$("learn-answer").value,language:$("learn-language").value.trim(),kind:$("learn-kind").value};}
async function loadLearning(){
 const [data,prefs]=await Promise.all([api("/api/learning"),api("/api/preferences")]);
 $("use-learning").checked=prefs.use_learning;$("local-metrics").checked=prefs.local_metrics;
 $("learning-entries").replaceChildren();
 for(const entry of data.entries){
  const card=node("div","","document-card"),label=node("label",` ${entry.language} · ${entry.kind}: ${entry.question}`),check=document.createElement("input");
  check.type="checkbox";check.dataset.learningId=entry.id;label.prepend(check);card.append(label);
  const detail=document.createElement("details");detail.append(node("summary","Review full example"),node("pre",entry.answer));card.append(detail);
  const edit=node("button","Load into editor","quiet");edit.onclick=()=>{for(const key of ["question","answer","language","kind"])$("learn-"+key).value=entry[key];$("learn-consent").checked=false;$("share-consent").checked=false;$("contribution-preview").replaceChildren();$("learning-status").textContent="Loaded. Saving creates a new example; delete the old one if replacing it.";};
  const remove=node("button","Delete","quiet");remove.onclick=async()=>{if(!confirm("Delete this learned example and its searchable reference?"))return;try{await api("/api/learning/"+entry.id,"DELETE");await loadLearning();await loadDocuments();}catch(exc){$("learning-status").textContent=exc.message;}};
  card.append(edit,remove);$("learning-entries").append(card);
 }
 $("learning-metrics").textContent=data.metrics.length?data.metrics.map(m=>`${m.bucket}: ${m.count} responses · ${(m.elapsed_ms/m.count/1000).toFixed(2)} s average · ${m.tokens} reported tokens`).join("\n"):"No performance totals saved.";
}
$("learning-settings").onclick=async()=>{try{await api("/api/preferences","POST",{use_learning:$("use-learning").checked,local_metrics:$("local-metrics").checked});$("learning-status").textContent="Saved locally. No telemetry upload is enabled.";}catch(exc){$("learning-status").textContent=exc.message;}};
$("learning-form").onsubmit=async event=>{event.preventDefault();try{const result=await api("/api/learning/import","POST",{pack:{format:"nexo-learning-v1",entries:[learningEntry()]},consent:$("learn-consent").checked});$("learning-status").textContent=`Saved ${result.added} new example(s); ${result.duplicates} duplicate(s). Model weights unchanged.`;$("learn-consent").checked=false;await loadLearning();await loadDocuments();}catch(exc){$("learning-status").textContent=exc.message;}};
for(const key of ["question","answer","language","kind"])$("learn-"+key).addEventListener("input",()=>{$("learn-consent").checked=false;$("share-consent").checked=false;$("contribution-preview").replaceChildren();});
$("prepare-contribution").onclick=async()=>{try{
 const draft=await api("/api/learning/contribute","POST",{entry:learningEntry(),consent:$("share-consent").checked});
 const link=node("a","Open GitHub to review and submit ↗");link.href=draft.url;link.target="_blank";link.rel="noopener noreferrer";
 $("contribution-preview").replaceChildren(node("pre",draft.body),link);$("learning-status").textContent="Draft prepared locally. Opening GitHub sends this draft to GitHub; submitting the issue publishes it.";
}catch(exc){$("learning-status").textContent=exc.message;}};
$("export-learning").onclick=async()=>{try{const ids=[...document.querySelectorAll("[data-learning-id]:checked")].map(e=>e.dataset.learningId);const pack=await api("/api/learning/export","POST",{ids});const url=URL.createObjectURL(new Blob([JSON.stringify(pack,null,2)],{type:"application/json"}));const a=node("a","");a.href=url;a.download="nexo-learning-pack.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(exc){$("learning-status").textContent=exc.message;}};
function resetPack(){pendingLearningPack=null;$("pack-consent").checked=false;$("import-learning").disabled=true;$("learning-preview").textContent="";}
async function previewPack(pack){resetPack();const data=await api("/api/learning/preview","POST",{pack});pendingLearningPack={format:"nexo-learning-v1",entries:data.entries};$("learning-preview").textContent=JSON.stringify(pendingLearningPack,null,2);$("import-learning").disabled=false;}
$("learning-file").onchange=async()=>{resetPack();try{const file=$("learning-file").files[0];if(!file)return;if(file.size>400000)throw new Error("Learning pack limit: 400 KB");await previewPack(JSON.parse(await file.text()));}catch(exc){$("learning-status").textContent=exc.message;}};
$("community-learning").onclick=async()=>{resetPack();try{await previewPack(await api("/api/learning/community"));}catch(exc){$("learning-status").textContent=exc.message;}};
$("import-learning").onclick=async()=>{try{const result=await api("/api/learning/import","POST",{pack:pendingLearningPack,consent:$("pack-consent").checked});$("learning-status").textContent=`Imported ${result.added}; skipped ${result.duplicates} duplicates.`;resetPack();await loadLearning();await loadDocuments();}catch(exc){$("learning-status").textContent=exc.message;}};
$("clear-learning-metrics").onclick=async()=>{try{await api("/api/learning-metrics","DELETE");await loadLearning();}catch(exc){$("learning-status").textContent=exc.message;}};

function safeWebLink(value){try{const u=new URL(value);return u.protocol==="https:"&&!u.username&&!u.password;}catch{return false;}}
async function loadWebSources(){
 const data=await api("/api/web");$("brave-status").textContent=data.brave_configured?"Key configured for this run. Storage permission: "+(data.storage_rights?"confirmed":"not confirmed; search answers will not be saved"):"No Brave key configured. Wikipedia remains available.";
 $("web-sources").replaceChildren();
 for(const source of data.sources){
  const card=node("div","","document-card"),details=document.createElement("details");
  details.append(node("summary",`[${source.id}] ${source.title} · ${source.expired?"Expired — refresh before reuse":"Available for local reuse"}`),node("p",`Retrieved ${source.retrieved_at}. ${source.source}`),node("pre",source.text));
  if(safeWebLink(source.url)){const link=node("a","Open original source ↗");link.href=source.url;link.target="_blank";link.rel="noopener noreferrer";details.append(link);}
  const remove=node("button","Delete","quiet");remove.onclick=async()=>{try{await api("/api/web/"+source.id,"DELETE");await loadWebSources();}catch(exc){$("web-status").textContent=exc.message;}};
  card.append(details,remove);$("web-sources").append(card);
 }
}
$("save-brave-key").onclick=async()=>{try{await api("/api/web/key","POST",{key:$("brave-key").value,storage_rights:$("brave-storage").checked});$("brave-key").value="";await loadWebSources();}catch(exc){$("web-status").textContent=exc.message;}};
$("clear-brave-key").onclick=async()=>{try{await api("/api/web/key","POST",{key:""});$("brave-key").value="";$("brave-storage").checked=false;await loadWebSources();}catch(exc){$("web-status").textContent=exc.message;}};
$("reload-web-sources").onclick=()=>loadWebSources().catch(exc=>$("web-status").textContent=exc.message);
$("clear-web-sources").onclick=async()=>{if(!confirm("Delete saved web excerpts? Existing chat history is separate; use Clear history to remove a conversation."))return;try{await api("/api/web","DELETE");await loadWebSources();}catch(exc){$("web-status").textContent=exc.message;}};
