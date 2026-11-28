#!/usr/bin/env node
// Measures the content and screen quality bars. Run from the repository root: node scripts/quality_check.js
// Needs Playwright and python3 (to serve docs/). Writes quality/report.json. Reading aid for the maintainer, not part of the record.
const fs=require("fs"),path=require("path"),{spawn}=require("child_process"),{chromium}=require("playwright");
const ROOT=path.resolve(__dirname,".."),D=JSON.parse(fs.readFileSync(path.join(ROOT,"docs/data.json"),"utf8"));
D.ko=JSON.parse(fs.readFileSync(path.join(ROOT,"docs/ko.json"),"utf8"));  // Korean card text is a separate file, fetched only in Korean
const out=[],add=(area,id,pass,now,bar)=>out.push({area,id,pass,now,bar});
const ev=D.events,live=ev.filter(e=>e.status!=="resolved"),day=864e5,today=Date.now();
// content
const twoSrc=ev.filter(e=>e.sources.length>=2).length;
add("content","sources_per_card",twoSrc===ev.length,`${twoSrc}/${ev.length} cards have 2+ sources`,"every card has 2 or more sources");
// source tiers (owner's rule, 2026-11-26): primary = government, central bank, regulator, statute, company filings and IR;
// allowed secondary = major wires and financial papers; everything else does not count as support.
const host=u=>new URL(u).hostname.replace(/^www\./,"");
const PRIMARY=/(\.gov$|\.gov\.[a-z]{2}$|federalreserve\.gov|stlouisfed\.org|federalreservehistory\.org|newyorkfed\.org|ecb\.europa\.eu|europa\.eu$|boj\.or\.jp|mof\.go\.jp|bankofengland\.co\.uk|imf\.org|bis\.org|stats\.gov\.cn|pbc\.gov\.cn|cao\.go\.jp|snb\.ch|finma\.ch)/;
const EXTRA=new Set((D.aids.primary_hosts||[]));  // company investor-relations hosts, listed by hand in aids/reading.json
const SECOND=/(^|\.)(reuters\.com|bloomberg\.com|ft\.com|wsj\.com|apnews\.com|nikkei\.com)$/;
const tier=u=>{const h=host(u);return PRIMARY.test(h)||EXTRA.has(h)?1:SECOND.test(h)?2:3};
const allSrc=[...ev.map(e=>[e.id,e.sources]),...(D.hindsight.cases||[]).map(c=>["case:"+c.id,c.sources])];
const noPrim=allSrc.filter(([,s])=>!s.some(u=>tier(u)===1)).length,weak=allSrc.flatMap(([,s])=>s).filter(u=>tier(u)===3);
add("content","primary_source_per_card",noPrim===0,`${allSrc.length-noPrim}/${allSrc.length} cards and cases have a primary source`,"every card and case has at least one primary source");
add("content","no_weak_sources",weak.length===0,`${weak.length} links from sources below the bar (${[...new Set(weak.map(host))].join(", ")})`,"0 (no Wikipedia, blogs, newsletters or fund commentary)");
const facts=ev.flatMap(e=>e.sourced_facts),linked=facts.filter(f=>typeof f==="object"&&f.url).length;
add("content","fact_links",linked===facts.length,`${linked}/${facts.length} facts carry their own link`,"every fact links to its article");
const fresh=live.filter(e=>(today-new Date(e.history[e.history.length-1].date+"T00:00:00Z"))/day<=8).length;
add("content","freshness",fresh===live.length,`${fresh}/${live.length} open cards reviewed in the last 7 days`,"all open cards");
const L=Object.values(D.aids.links||{}).flatMap(o=>Object.values(o)),unc=L.filter(l=>l.level==="unconfirmed").length;
add("content","judgment_only_share",unc/L.length<0.3,`${unc}/${L.length} (${Math.round(100*unc/L.length)}%)`,"under 30%");
const cs=(D.hindsight.cases||[]),ok=cs.filter(c=>c.outcome==="ok").length;
add("content","hindsight_cases",cs.length>=8&&ok>=2,`${cs.length} cases, ${ok} counter-examples`,"8 cases, 2 counter-examples");
const ko=ev.filter(e=>D.ko[e.id]).length;
add("content","korean_cards",ko===ev.length,`${ko}/${ev.length}`,"all cards translated");
const watch=ev.filter(e=>(e.resolution_conditions.resolved_when_all||[]).length&&(e.resolution_conditions.worsened_when_any||[]).length).length;
add("content","conditions_present",watch===ev.length,`${watch}/${ev.length} cards have both resolution and worsening conditions`,"all cards");
const gl=Object.keys((D.aids.glossary)||{}).length;
add("content","glossary",gl>=8,`${gl} terms explained`,"8 or more terms");
// wording: phrases that read as advice, unless negated in the same sentence
const BAD=[/\b(you should|we recommend|strong buy|buy now|sell now|time to (buy|sell)|price target)\b/i,/(매수하세요|매도하세요|사세요|파세요|사야 합니다|팔아야 합니다|매수 추천|매도 추천|목표가)/];
const texts=[];const walk=(v)=>{if(typeof v==="string")texts.push(v);else if(v&&typeof v==="object")Object.values(v).forEach(walk)};walk(D.events);walk(D.ko);walk(D.hindsight);walk(D.aids.history||[]);
texts.push(fs.readFileSync(path.join(ROOT,"docs/odds.html"),"utf8").replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>|<[^>]+>/g," "));
texts.push(fs.readFileSync(path.join(ROOT,"docs/selection.html"),"utf8").replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>|<[^>]+>/g," "));
for(const f of fs.readdirSync(path.join(ROOT,"docs/weekly")))texts.push(fs.readFileSync(path.join(ROOT,"docs/weekly",f),"utf8").replace(/<[^>]+>/g," "));
const hits=texts.flatMap(t=>t.split(/(?<=[.!?。])\s+/)).filter(s=>BAD.some(r=>r.test(s))&&!/\b(not|no|never)\b|아닙니다|않습니다|금지/.test(s));
add("content","advice_wording",hits.length===0,`${hits.length} sentences flagged${hits.length?": "+hits.slice(0,3).join(" | ").slice(0,300):""}`,"0 sentences");
// screen
(async()=>{
  const srv=spawn("python3",["-m","http.server","8791"],{cwd:path.join(ROOT,"docs"),stdio:"ignore"});await new Promise(r=>setTimeout(r,900));
  const b=await chromium.launch();let errs=0,scroll=0,missing=[],broken=[],lowc=[],kbd=[];
  try{
    for(const [w,loc] of [[390,"ko-KR"],[390,"en-US"],[1200,"en-US"]]){
      const c=await b.newContext({viewport:{width:w,height:900},locale:loc});const p=await c.newPage();p.on("pageerror",()=>errs++);
      for(const u of ["/","/#risks","/#sectors","/#past","/#record","/#method","/#weekly","/weekly/1.html","/weekly/1.ko.html","/odds.html","/selection.html"]){await p.goto("http://localhost:8791"+u);await p.waitForTimeout(500);
        if(u==="/#sectors")await p.evaluate(()=>document.querySelector("#secs button")?.click());
        if(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth))scroll++;
        if(w===390){const r=await p.evaluate(()=>{document.querySelectorAll(".det").forEach(d=>d.hidden=false);document.querySelectorAll("details").forEach(d=>d.open=true);
          const P=s=>s.match(/[\d.]+/g).map(Number),L=c=>{const a=c.map(v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)});return .2126*a[0]+.7152*a[1]+.0722*a[2]};
          const root=P(getComputedStyle(document.body).backgroundColor).slice(0,3);
          const bgOf=el=>{for(let e=el;e;e=e.parentElement){const c=P(getComputedStyle(e).backgroundColor);if(c.length<4||c[3]>.99)return c.slice(0,3);if(c[3]>0)return c.slice(0,3).map((v,i)=>v*c[3]+root[i]*(1-c[3]))}return root};
          const low=[],w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let n;
          while(n=w.nextNode()){const t=n.textContent.trim(),el=n.parentElement;if(!t||!el.offsetParent)continue;const cs=getComputedStyle(el),bg=bgOf(el);let fg=P(cs.color);if(fg.length>3&&fg[3]<1)fg=fg.slice(0,3).map((v,i)=>v*fg[3]+bg[i]*(1-fg[3]));fg=fg.slice(0,3);
            const a=L(fg),b=L(bg),cr=(Math.max(a,b)+.05)/(Math.min(a,b)+.05),sz=parseFloat(cs.fontSize),big=sz>=24||(sz>=18.66&&+cs.fontWeight>=700);if(cr<(big?3:4.5))low.push(cr.toFixed(2)+" "+t.slice(0,24))}
          const kb=[];document.querySelectorAll("[aria-expanded]").forEach(e=>{if(e.tabIndex<0)kb.push("row not focusable")});
          document.querySelectorAll("input,select").forEach(i=>{if(!(i.labels&&i.labels.length)&&!i.getAttribute("aria-label"))kb.push("no label: "+i.id)});
          document.querySelectorAll("button").forEach(x=>{if(!x.textContent.trim()&&!x.getAttribute("aria-label"))kb.push("unnamed button")});
          document.querySelectorAll("img:not([alt])").forEach(()=>kb.push("image without alt"));document.querySelectorAll("#tabs a").forEach(x=>{if(x.getBoundingClientRect().height<44)kb.push("tab too small to tap")});if(document.querySelector("#tabs")&&document.querySelectorAll("#tabs a[aria-current=page]").length!==1)kb.push("current tab not marked");if(!document.documentElement.lang)kb.push("no page language");if(document.querySelector("#tabs")){const h1=[...document.querySelectorAll("h1")].filter(h=>h.getClientRects().length&&h.textContent.trim()).length;if(h1!==1)kb.push(h1+" page headings (h1)");if(!document.querySelector("a.skip"))kb.push("no skip link");[...document.querySelectorAll("main a,main button,main select,main input,main summary,.bar a,.lang button")].filter(e=>e.getClientRects().length&&!(e.tagName==="A"&&getComputedStyle(e).display==="inline")&&e.getBoundingClientRect().height<44).forEach(e=>kb.push("small tap target: "+(e.textContent||e.id).trim().slice(0,20)))}
          return {low,kb}});lowc.push(...r.low.map(x=>u+" "+x));kbd.push(...r.kb.map(x=>u+" "+x))}
        for(const h of await p.evaluate(()=>[...document.querySelectorAll("a[href]")].map(a=>a.getAttribute("href")).filter(h=>!/^(https?:|mailto:|#)/.test(h)))){
          const r=await p.request.get(new URL(h,"http://localhost:8791"+u).href);if(!r.ok())broken.push(u+" -> "+h)}}
      if(w===390&&loc==="ko-KR"){await p.goto("http://localhost:8791/");await p.waitForTimeout(400);
        missing=await p.evaluate(()=>{const f=(o,pre="")=>Object.entries(o).flatMap(([k,v])=>v&&typeof v==="object"&&!Array.isArray(v)?f(v,pre+k+"."):[pre+k]);const a=new Set(f(T.en)),k=new Set(f(T.ko));return [...a].filter(x=>!k.has(x)).map(x=>"ko:"+x).concat([...k].filter(x=>!a.has(x)&&!x.startsWith("comp.")).map(x=>"en:"+x))}).catch(()=>["could not read strings"]);
      }
      await c.close()}
  }finally{await b.close();srv.kill()}
  add("screen","no_script_errors",errs===0,`${errs} errors`,"0");
  add("screen","no_sideways_scroll",scroll===0,`${scroll} pages scroll sideways`,"0");
  add("screen","internal_links",broken.length===0,`${broken.length} broken${broken.length?": "+[...new Set(broken)].slice(0,3).join(", "):""}`,"0 (links inside the site; outside links are not checked)");
  add("screen","text_contrast",lowc.length===0,`${lowc.length} texts below the AA contrast ratio${lowc.length?": "+[...new Set(lowc)].slice(0,3).join("; "):""}`,"0 (4.5:1 for normal text, 3:1 for large)");
  add("screen","keyboard_and_labels",kbd.length===0,`${kbd.length} problems${kbd.length?": "+[...new Set(kbd)].slice(0,3).join("; "):""}`,"0 (every card opens by keyboard; inputs, buttons and images are named)");
  add("screen","two_languages_match",missing.length===0,`${missing.length} strings missing${missing.length?": "+missing.slice(0,5).join(", "):""}`,"0");
  const size=f=>fs.statSync(path.join(ROOT,"docs",f)).size,kb=Math.round((size("index.html")+size("data.json"))/1024),kbKo=Math.round((size("index.html")+size("data.json")+size("ko.json"))/1024);
  add("screen","page_weight",kb<=300,`${kb} KB in English, ${kbKo} KB in Korean (adds ko.json)`,"300 KB or less in English, the default");
  const rep={checked_at_utc:new Date().toISOString().slice(0,16)+"Z",passed:out.filter(x=>x.pass).length,total:out.length,checks:out,
    not_automated:["numbers on cards checked against sources","each resolution condition decidable by one public fact","accessibility contrast and keyboard","friends' feedback bars"]};
  fs.mkdirSync(path.join(ROOT,"quality"),{recursive:true});fs.writeFileSync(path.join(ROOT,"quality/report.json"),JSON.stringify(rep,null,1)+"\n");
  for(const x of out)console.log((x.pass?"PASS ":"FAIL ")+x.area+"/"+x.id+": "+x.now+"  [bar: "+x.bar+"]");
  console.log(`${rep.passed}/${rep.total} automated checks pass`);
})();
