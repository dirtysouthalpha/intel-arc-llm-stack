<script>
/* Sentinel Prime Command Center - live backend integration v2.
   Chat is a body-level overlay (outside React's tree) -> no removeChild, persists across nav,
   Claude-style thinking + streaming. Plus model switcher/auto, live data, Overview repurpose. */
(function () {
  if (window.__spWired) return; window.__spWired = true;
  var auto = false, busy = false, modelsCache = null, modelsLoading = false, activeVal = null;
  var convo = [];                 // {role,text,thinking} - kept in memory, survives view nav
  var overlay, msgArea, input, sel, tog, historyLoaded = false;

  function ensureCSS(){
    if (document.getElementById('sp-ov-css')) return;
    var st = document.createElement('style'); st.id = 'sp-ov-css';
    st.textContent =
      '.overview-grid .chatlist,.overview-grid .conv{display:none!important}'
    + '.overview-grid{grid-template-columns:minmax(0,1fr)!important;height:auto!important}'
    + '.overview-grid .rail{display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:18px!important;align-content:start!important;overflow:visible!important;padding-right:0!important}'
    + '.overview-grid .rail .panel:first-child{grid-column:1/-1}'
    + '.placeholder-screen.sp-aichat{visibility:hidden!important}'
    + '#sp-chat .sp-think{display:inline-flex;gap:5px;align-items:center;color:var(--text-dim,#9aa)}'
    + '#sp-chat .sp-think i{width:7px;height:7px;border-radius:50%;background:var(--accent,#5b8cff);display:inline-block;animation:spb 1.2s infinite}'
    + '#sp-chat .sp-think i:nth-child(2){animation-delay:.2s}#sp-chat .sp-think i:nth-child(3){animation-delay:.4s}'
    + '@keyframes spb{0%,100%{opacity:.25;transform:scale(.85)}50%{opacity:1;transform:scale(1)}}'
    + '#sp-chat .bubble{white-space:pre-wrap;word-break:break-word}'
    + '.placeholder-screen.sp-tv{visibility:hidden!important}'
    + '#root.sp-navcol .sidebar{width:0!important;min-width:0!important;padding-left:0!important;padding-right:0!important;border-right:none!important;overflow:hidden!important;opacity:0;transition:.2s}'
    + '#sp-notif .sp-clear{float:right;color:var(--accent,#5b8cff);font-size:11px;font-weight:700;cursor:pointer;letter-spacing:.5px}'
    + '#sp-notif .sp-clear:hover{text-decoration:underline}'
    + '#sp-settings .sp-row{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:11px 16px;border-top:1px solid var(--border,#223)}'
    + '#sp-settings .sp-row:first-child{border-top:none}'
    + '#sp-settings select,#sp-settings button{background:rgba(var(--accent-rgb,91,140,255),.08);border:1px solid var(--border,#223);color:var(--text,#dde);border-radius:6px;padding:6px 10px;font-family:var(--font-mono,monospace);font-size:12px;cursor:pointer}'
    + '#sp-tv .mc-brain-stage{flex:1;min-height:0;position:relative}'
    + '#sp-tv canvas{width:100%!important;height:100%!important;display:block}';
    (document.head || document.documentElement).appendChild(st);
  }

  // ---------- model list ----------
  function loadModels(){
    if (modelsCache || modelsLoading) return; modelsLoading = true;
    fetch('/api/models').then(function(r){return r.json();}).then(function(d){
      var ms = (d.models||[]).filter(function(m){return m.id;}); if (ms.length) modelsCache = ms; modelsLoading = false;
      fetch('/api/models/active').then(function(r){return r.json();}).then(function(a){ if(a&&a.model) activeVal=a.model+'|'+(a.provider||''); fillSelect(); }).catch(fillSelect);
    }).catch(function(){ modelsLoading = false; });
  }
  function fillSelect(){
    if (!sel || !modelsCache) return;
    var sig = modelsCache.length + ':' + modelsCache[0].id;
    if (sel.getAttribute('data-sp') === sig) return;
    sel.innerHTML = '';
    modelsCache.forEach(function(m){ var o=document.createElement('option'); o.value=m.id+'|'+(m.provider||''); o.textContent=m.name||m.id; sel.appendChild(o); });
    sel.setAttribute('data-sp', sig);
    if (activeVal) sel.value = activeVal;
  }
  function doSwitch(v){ activeVal=v; var p=v.split('|'); fetch('/api/models/switch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:p[0],provider:p[1]})}).catch(function(){}); }

  // ---------- overlay ----------
  function chatRoot(){ return document.getElementById('root') || document.body; }
  function buildOverlay(){
    // live INSIDE #root (the z-index:2 app wrapper) at z-index 50: above the shell (1) so it covers
    // the view, below the topbar (90) so theme/notif dropdowns open over it. (A body-level overlay
    // sits above the whole z=2 wrapper and would cover its dropdowns no matter the z-index.)
    if (overlay){ if (!overlay.isConnected) chatRoot().appendChild(overlay); return; }
    overlay = document.createElement('div'); overlay.id = 'sp-chat';
    overlay.className = 'conv panel';
    overlay.style.cssText = 'position:fixed;display:none;flex-direction:column;z-index:50;min-height:0';
    overlay.innerHTML =
      '<div class="conv-head" style="display:flex;align-items:center;justify-content:space-between"><div class="panel-title">Sentinel Prime</div><div class="bot-chip"><span class="blip"></span>Hermes agent</div></div>'
    + '<div class="conv-scroll" id="sp-msgs"></div>'
    + '<div class="conv-foot"><div class="quick-row" id="sp-quick"></div><div class="composer"><input class="field" id="sp-input" placeholder="Ask Hermes…  (paste or drop images)"></div>'
    + '<div class="model-row"><span>MODEL</span><select id="sp-sel"></select><div class="toggle" id="sp-tog"><i></i></div><span>Auto</span></div></div>';
    chatRoot().appendChild(overlay);
    msgArea = overlay.querySelector('#sp-msgs'); input = overlay.querySelector('#sp-input');
    sel = overlay.querySelector('#sp-sel'); tog = overlay.querySelector('#sp-tog');
    input.addEventListener('keydown', function(e){ if(e.key==='Enter'&&!e.shiftKey){ e.preventDefault(); send(); } });
    sel.addEventListener('change', function(){ doSwitch(sel.value); });
    tog.addEventListener('click', function(){ auto=!auto; tog.classList.toggle('on',auto); });
    // quick-action chips (were dead in the Overview mockup) -> send a real prompt to Sentinel Prime
    var QA = [
      ['⚡ Daily briefing','Give me a concise daily briefing: system status, fleet health, brain activity, and anything that needs my attention.'],
      ['🖥️ Fleet status','What is the current status of every node in the fleet right now?'],
      ['🌐 Check tunnels','Check the Cloudflare tunnel status and report whether prime.dirtysouthalpha.com is healthy.'],
      ['🧠 Brain summary','Summarize what you currently have stored in your brain/memory.'],
      ['💾 Run backup','Walk me through running a system backup, and confirm what would be backed up.']
    ];
    var qr = overlay.querySelector('#sp-quick');
    QA.forEach(function(q){ var c=document.createElement('span'); c.className='chip'; c.textContent=q[0]; c.style.cursor='pointer'; c.addEventListener('click', function(){ sendText(q[1]); }); qr.appendChild(c); });
    fillSelect(); render(); loadHistory();
  }
  function render(){
    if (!msgArea) return;
    msgArea.innerHTML = '';
    if (!convo.length){ var e=document.createElement('div'); e.style.cssText='margin:auto;color:var(--text-faint,#667);font-family:var(--font-mono,monospace);font-size:13px'; e.textContent='Ask Sentinel Prime anything…'; msgArea.appendChild(e); }
    convo.forEach(function(m){
      var d=document.createElement('div'); d.className='msg '+(m.role==='user'?'user':'agent');
      var b=document.createElement('div'); b.className='bubble';
      if (m.thinking) b.innerHTML='<span class="sp-think">Sentinel Prime is thinking<i></i><i></i><i></i></span>';
      else b.textContent = m.text;
      d.appendChild(b); msgArea.appendChild(d);
    });
    msgArea.scrollTop = msgArea.scrollHeight;
  }
  function loadHistory(){
    if (historyLoaded) return; historyLoaded = true;
    fetch('/api/conversations').then(function(r){return r.json();}).then(function(d){
      var list = Array.isArray(d) ? d : (d.conversations||d.items||[]);
      if (!list || !list.length) return;
      var id = list[0].id || list[0].conversation_id || list[0].thread; if (id==null) return;
      return fetch('/api/conversations/'+id).then(function(r){return r.json();}).then(function(c){
        var msgs = Array.isArray(c) ? c : (c.messages||[]);
        if (msgs && msgs.length && !convo.length){
          convo = msgs.map(function(m){ return {role:(m.role==='user'?'user':'agent'), text:(m.text||m.content||'')}; }).filter(function(m){return m.text;});
          render();
        }
      });
    }).catch(function(){});
  }

  function send(){ if (!input) return; var t = input.value.trim(); if (!t) return; input.value = ''; sendText(t); }
  async function sendText(text){
    if (busy || !text) return;
    var aiNav = [...document.querySelectorAll('.nav-item')].find(function(n){return /AI Chat/i.test(n.textContent);});
    if (aiNav && !aiNav.classList.contains('active')) aiNav.click();   // make sure the chat is visible
    busy = true;
    convo.push({role:'user', text:text});
    var am = {role:'agent', text:'', thinking:true}; convo.push(am); render();
    if (auto){ try { var ar = await (await fetch('/api/models/auto-route',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})})).json(); if (ar&&ar.model&&ar.provider){ activeVal=ar.model+'|'+ar.provider; if(sel) sel.value=activeVal; await fetch('/api/models/switch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:ar.model,provider:ar.provider})}); } } catch(e){} }
    try {
      var resp = await fetch('/api/chat/sentinel/stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})});
      var reader = resp.body.getReader(), dec = new TextDecoder(), buf='', acc='';
      while (true){
        var rd = await reader.read(); if (rd.done) break;
        buf += dec.decode(rd.value,{stream:true}); var i;
        while ((i=buf.indexOf('\n'))>=0){
          var line=buf.slice(0,i); buf=buf.slice(i+1);
          if (line.indexOf('data:')!==0) continue;
          var js=line.slice(5).trim(); if(!js) continue;
          var ev; try{ ev=JSON.parse(js); }catch(e){ continue; }
          if (ev.type==='delta'){ acc+=(ev.content||''); am.thinking=false; am.text=acc; render(); }
          else if (ev.type==='error'){ am.thinking=false; am.text='⚠ '+(ev.message||'backend error'); render(); }
          else if (ev.type==='done' && ev.full){ am.thinking=false; am.text=ev.full; render(); }
        }
      }
      if (am.thinking || am.text===''){ am.thinking=false; am.text=am.text||'(no response)'; render(); }
    } catch(e){ am.thinking=false; am.text='⚠ '+e.message; render(); }
    busy = false;
  }

  function position(){
    if (!overlay) return;
    var main = document.querySelector('.main'); if (!main){ overlay.style.display='none'; return; }
    var ph = main.querySelector('.placeholder-screen');
    var nav = document.querySelector('.nav-item.active');
    var isAIChat = (ph && /AI\s*CHAT/i.test(ph.textContent||'')) || (nav && /AI Chat/i.test(nav.textContent));
    if (ph && isAIChat) ph.classList.add('sp-aichat');
    if (isAIChat){
      var r = main.getBoundingClientRect();
      overlay.style.display='flex';
      overlay.style.left=(r.left+18)+'px'; overlay.style.top=(r.top+18)+'px';
      overlay.style.width=(r.width-36)+'px'; overlay.style.height=(r.height-36)+'px';
    } else overlay.style.display='none';
  }

  // ---------- notifications bell (decorative in the mockup -> wire it to the live event feed) ----------
  var notif = null, notifOpen = false, notifDismissed = Object.create(null);
  function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
  function clearNotif(){ ((window.DATA && window.DATA.events)||[]).forEach(function(e){ notifDismissed[e.text]=1; }); renderNotif(); }
  function buildNotif(){
    if (notif){ if (!notif.isConnected) document.body.appendChild(notif); return; }
    notif = document.createElement('div'); notif.id = 'sp-notif'; notif.className = 'theme-menu';
    notif.style.cssText = 'position:fixed;display:none;z-index:95;width:360px;max-height:72vh;overflow:auto';
    document.body.appendChild(notif);
  }
  function renderNotif(){
    buildNotif(); if (!notif) return;
    var ev = ((window.DATA && window.DATA.events) || []).filter(function(e){ return !notifDismissed[e.text]; });
    notif.innerHTML = '<div class="theme-menu-head">NOTIFICATIONS · ' + ev.length + (ev.length?'<span class="sp-clear">CLEAR ALL</span>':'') + '</div>'
      + (ev.length ? ev.map(function(e){
          var c = e.level==='error'?'var(--bad,#f55)':(e.level==='warn'?'var(--warn,#fb3)':'var(--good,#3d5)');
          return '<div class="theme-opt" style="cursor:default;align-items:flex-start">'
            + '<span class="blip" style="background:'+c+';box-shadow:0 0 8px '+c+';margin-top:6px"></span>'
            + '<div style="flex:1"><div class="name" style="font-size:13px;font-weight:500;line-height:1.4">'+esc(e.text)+'</div>'
            + '<div class="sub">'+esc(e.time||'')+' · '+esc((e.level||'info').toUpperCase())+'</div></div></div>';
        }).join('') : '<div class="theme-opt"><div class="sub">No notifications</div></div>');
  }
  function toggleNotif(bell){
    notifOpen = !notifOpen; renderNotif();
    if (notifOpen){ var r = bell.getBoundingClientRect(); notif.style.display='block';
      notif.style.top = (r.bottom + 8) + 'px'; notif.style.right = (window.innerWidth - r.right) + 'px'; }
    else notif.style.display='none';
  }
  // ---------- settings (gear icon) ----------
  var settings = null, settingsOpen = false;
  function buildSettings(){
    if (settings){ if(!settings.isConnected) document.body.appendChild(settings); return; }
    settings = document.createElement('div'); settings.id='sp-settings'; settings.className='theme-menu';
    settings.style.cssText='position:fixed;display:none;z-index:95;width:300px';
    document.body.appendChild(settings);
  }
  function renderSettings(){
    buildSettings(); if(!settings) return;
    var cur = activeVal ? activeVal.split('|')[0] : '';
    var opts = (modelsCache||[]).map(function(m){ return '<option value="'+m.id+'|'+(m.provider||'')+'"'+(m.id===cur?' selected':'')+'>'+esc(m.name||m.id)+'</option>'; }).join('');
    settings.innerHTML = '<div class="theme-menu-head">SETTINGS</div>'
      + '<div class="sp-row"><span>Default model</span><select id="sp-set-model">'+opts+'</select></div>'
      + '<div class="sp-row"><span>Live data</span><button id="sp-set-refresh">Refresh now</button></div>'
      + '<div class="sp-row"><span>Backend</span><span class="sub" style="font-family:var(--font-mono,monospace);font-size:11px">Arc B60 · :4000</span></div>'
      + '<div class="sp-row"><span>Status</span><span style="color:var(--good,#3d5);font-family:var(--font-mono,monospace);font-size:12px">'+esc((window.DATA&&window.DATA.__status)||'live')+'</span></div>';
    var ms = settings.querySelector('#sp-set-model'); if(ms) ms.addEventListener('change', function(){ doSwitch(ms.value); });
    var rf = settings.querySelector('#sp-set-refresh'); if(rf) rf.addEventListener('click', function(){ try{ window.HERMES && window.HERMES._tick(); }catch(e){} });
  }
  function toggleSettings(gear){
    settingsOpen = !settingsOpen; renderSettings();
    if(settingsOpen){ var r=gear.getBoundingClientRect(); settings.style.display='block'; settings.style.top=(r.bottom+8)+'px'; settings.style.right=(window.innerWidth-r.right)+'px'; }
    else settings.style.display='none';
  }

  // ---------- Mission Control TV -> live Three.js NETWORK view (reuses the design's Network3D) ----------
  var tv = null, tvNetRoot = null, tvRendered = false, tvIdx = 0, tvTimer = null;
  var TV_SECTIONS = [
    { t:'NEURAL NETWORK', type:'net' },
    { t:'FLEET STATUS',   type:'fleet' },
    { t:'NEURAL MEMORY',  type:'memory' },
    { t:'SYSTEM VITALS',  type:'vitals' }
  ];
  function tvDataHTML(type){
    var D = window.DATA||{}, s = D.stats||{};
    if (type==='fleet'){
      return '<div style="padding:6px 6px;display:flex;flex-direction:column;gap:16px">'
        + (D.fleet||[]).map(function(f){ var ok=f.status==='online'; return '<div class="fleet-row" style="font-size:20px"><span class="blip" style="background:'+(ok?'var(--good,#3d5)':'var(--bad,#f55)')+';box-shadow:0 0 10px '+(ok?'var(--good,#3d5)':'var(--bad,#f55)')+'"></span><span class="nm" style="font-weight:700">'+esc(f.name)+'</span><span class="cpu" style="margin-left:auto;font-family:var(--font-mono,monospace);color:var(--text-dim,#9aa)">'+(f.cpu||0)+'% cpu · '+esc(f.status||'')+'</span></div>'; }).join('')
        + '</div>';
    }
    if (type==='memory'){
      return '<div style="padding:6px 6px;display:flex;flex-direction:column;gap:14px">'
        + (D.memories||[]).slice(0,6).map(function(m){ return '<div class="mem-item"><div class="mem-head">'+esc(m.region||'')+' · '+esc(m.side||'')+'<span class="wt" style="margin-left:auto">'+(m.weight||0)+'</span></div><div class="mem-text" style="font-size:15px">'+esc(m.text||'')+'</div></div>'; }).join('')
        + '</div>';
    }
    var tile=function(v,l){ return '<div class="stat-tile glow" style="text-align:center"><div class="big" style="font-size:48px">'+esc(String(v))+'</div><div class="lbl">'+l+'</div></div>'; };
    return '<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:18px;padding:8px 6px">'
      + tile(s.uptime||'—','System Uptime') + tile(s.neurons!=null?s.neurons:'—','Active Neurons')
      + tile(s.regions||'—','Active Regions') + tile((s.neuralActivity!=null?s.neuralActivity:0)+'%','Neural Activity') + '</div>';
  }
  function tvShow(){
    if (!tv) return;
    var sec = TV_SECTIONS[tvIdx % TV_SECTIONS.length];
    var head = tv.querySelector('#sp-tv-head');
    if (head) head.innerHTML = esc(sec.t)+' · LIVE NEURALIS <span class="mc-live"><span class="rec"></span>LIVE</span>'
      + '<span style="margin-left:auto;display:flex;gap:7px;align-items:center">'+TV_SECTIONS.map(function(_,i){return '<span style="width:9px;height:9px;border-radius:50%;background:'+(i===tvIdx?'var(--accent,#5b8cff)':'rgba(120,140,180,.3)')+';transition:.3s"></span>';}).join('')+'</span>';
    var net = tv.querySelector('#sp-tv-net'), data = tv.querySelector('#sp-tv-data');
    if (sec.type==='net'){ if(net)net.style.display='block'; if(data)data.style.display='none'; }
    else { if(net)net.style.display='none'; if(data){ data.style.display='block'; data.innerHTML = tvDataHTML(sec.type); } }
  }
  function buildTV(){
    if (!tv){
      tv = document.createElement('div'); tv.id='sp-tv';
      tv.style.cssText='position:fixed;display:none;z-index:50;flex-direction:column';
      tv.innerHTML = '<div class="panel mc-card mc-brain" style="flex:1;display:flex;flex-direction:column;min-height:0">'
        + '<div class="mc-card-h" id="sp-tv-head" style="display:flex;align-items:center;gap:10px"></div>'
        + '<div class="mc-brain-stage" style="flex:1;min-height:0;position:relative">'
        + '<div id="sp-tv-net" style="position:absolute;inset:0"></div>'
        + '<div id="sp-tv-data" style="position:absolute;inset:0;overflow:auto;padding:18px 22px;display:none"></div>'
        + '</div></div>';
      chatRoot().appendChild(tv);
    } else if (!tv.isConnected){ chatRoot().appendChild(tv); }
    if (!tvRendered && window.ReactDOM && window.ReactDOM.createRoot && window.Network3D){
      try {
        tvNetRoot = window.ReactDOM.createRoot(tv.querySelector('#sp-tv-net'));
        tvNetRoot.render(window.React.createElement(window.Network3D));
        tvRendered = true;
        tvShow();
        if (tvTimer) clearInterval(tvTimer);
        tvTimer = setInterval(function(){ tvIdx = (tvIdx+1) % TV_SECTIONS.length; tvShow(); }, 11000);
      } catch(e){}
    }
  }
  function positionTV(){
    if (!tv) return;
    var main = document.querySelector('.main'); if(!main){ tv.style.display='none'; return; }
    var ph = main.querySelector('.placeholder-screen');
    var nav = document.querySelector('.nav-item.active');
    var isTV = (ph && /MISSION CONTROL|\bTV\b/i.test(ph.textContent||'')) || (nav && /Mission Control/i.test(nav.textContent));
    if (ph && isTV) ph.classList.add('sp-tv');
    if (isTV){ var r=main.getBoundingClientRect(); tv.style.display='flex'; tv.style.left=(r.left+18)+'px'; tv.style.top=(r.top+18)+'px'; tv.style.width=(r.width-36)+'px'; tv.style.height=(r.height-36)+'px'; }
    else tv.style.display='none';
  }

  // ---------- topbar control delegation: bell / collapse / gear / clear / click-outside ----------
  document.addEventListener('click', function(e){
    var ib = e.target.closest && e.target.closest('.topbar .icon-btn');
    if (ib){
      if (ib.querySelector('.dot')){ e.preventDefault(); e.stopPropagation(); toggleNotif(ib); return; }
      var pd = (function(){ var p=ib.querySelector('svg path'); return p?(p.getAttribute('d')||''):''; })();
      if (/^M15 18/.test(pd)){ e.preventDefault(); e.stopPropagation(); var rt=document.getElementById('root'); if(rt) rt.classList.toggle('sp-navcol'); return; }  // collapse <
      if (/a3 3|M19\.4/.test(pd)){ e.preventDefault(); e.stopPropagation(); toggleSettings(ib); return; }  // gear
    }
    if (e.target.closest && e.target.closest('.sp-clear')){ e.preventDefault(); e.stopPropagation(); clearNotif(); return; }
    var inN = notif && notif.contains(e.target), inS = settings && settings.contains(e.target);
    if (!ib && !inN && !inS){
      if (notifOpen){ notifOpen=false; notif.style.display='none'; }
      if (settingsOpen){ settingsOpen=false; settings.style.display='none'; }
    }
  }, true);

  // topbar "Search anything…" box was dead -> Enter asks Sentinel Prime (it can search its brain/memory)
  document.addEventListener('keydown', function(e){
    if (e.key !== 'Enter') return;
    var t = e.target;
    if (t && t.tagName === 'INPUT' && t.closest && t.closest('.topbar') && !t.closest('#sp-chat')){
      var q = (t.value||'').trim(); if (q){ e.preventDefault(); e.stopImmediatePropagation(); t.value=''; t.blur(); sendText(q); }
    }
  }, true);

  // small toast for feedback
  function toast(msg){
    var t = document.createElement('div'); t.textContent = msg;
    t.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);z-index:200;background:var(--bg-1,#0e1424);border:1px solid var(--accent,#5b8cff);color:var(--text,#dde);padding:10px 18px;border-radius:8px;font-family:var(--font-mono,monospace);font-size:13px;box-shadow:0 10px 34px rgba(0,0,0,.55)';
    document.body.appendChild(t); setTimeout(function(){ try{t.remove();}catch(e){} }, 2200);
  }
  // Model Router "Scan" button was dead -> refresh providers/routes from the live feed
  document.addEventListener('click', function(e){
    var b = e.target.closest && e.target.closest('button,.btn,[class*="btn"]');
    if (b && /scan/i.test((b.textContent||'').trim()) && b.closest('.main')){
      e.preventDefault(); e.stopPropagation();
      toast('Scanning model providers…');
      try { window.HERMES && window.HERMES._tick(); } catch(err){}
      setTimeout(function(){ toast('Scan complete · providers + routes refreshed'); }, 1200);
    }
  }, true);

  function sweep(){ ensureCSS(); buildOverlay(); buildNotif(); buildSettings(); buildTV(); fillSelect(); position(); positionTV(); }
  (function enableHermes(){ if (window.HERMES){ try{ window.HERMES.baseUrl=''; window.HERMES.enabled=true; window.HERMES.endpoints.snapshot='/api/dashboard'; window.HERMES.start(); }catch(e){} } else setTimeout(enableHermes,400); })();
  loadModels(); sweep();
  new MutationObserver(function(){ sweep(); }).observe(document.documentElement, {childList:true, subtree:true});
  setInterval(sweep, 1200);
  window.addEventListener('resize', position);
})();
</script>
