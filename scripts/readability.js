#!/usr/bin/env node
// Measures how readable each tab is on a phone (390x844, Korean and English). Run from the repository root:
//   node scripts/readability.js [label]     -> writes quality/readability.json (and screenshots to $SHOTS if set)
// Reading aid for the maintainer, not part of the record.
const fs=require("fs"),path=require("path"),{spawn}=require("child_process"),{chromium}=require("playwright");
const ROOT=path.resolve(__dirname,".."),TABS=["home","risks","sectors","past","record","method","weekly"],SHOTS=process.env.SHOTS;
// words a general reader is unlikely to know
const JARGON={ko:["SHA-256","OpenTimestamps","블록체인","스프레드","VIX","중간값","%p","거래일","금리 곡선","금융 여건","낙폭","변동성","사후 검증","ETF","FRED","커밋","해시","지문"],
  en:["SHA-256","OpenTimestamps","blockchain","spread","VIX","median","points against","trading day","yield curve","financial conditions","drawdown","volatility","hindsight","ETF","FRED","commit","hash","fingerprint"]};
(async()=>{
  const srv=spawn("python3",["-m","http.server","8793"],{cwd:path.join(ROOT,"docs"),stdio:"ignore"});await new Promise(r=>setTimeout(r,900));
  const b=await chromium.launch(),res={};
  try{for(const lang of ["ko","en"]){
    const c=await b.newContext({viewport:{width:390,height:844},deviceScaleFactor:SHOTS?2:1,locale:lang==="ko"?"ko-KR":"en-US"}),p=await c.newPage();res[lang]={};
    for(const t of TABS){await p.goto("http://localhost:8793/?lang="+lang+"#"+t);await p.waitForTimeout(500);
      if(SHOTS&&lang==="ko"){await p.screenshot({path:SHOTS+"/"+t+"-first.png"});await p.screenshot({path:SHOTS+"/"+t+"-full.png",fullPage:true})}
      res[lang][t]=await p.evaluate(J=>{
        const vis=e=>{const r=e.getBoundingClientRect();return e.offsetParent!==null&&r.width>0&&r.height>0};
        let chars=0,small=0,tiny=0,min=99;const w=document.createTreeWalker(document.querySelector("main"),NodeFilter.SHOW_TEXT);let n;const body=[];
        while(n=w.nextNode()){const s=n.textContent.trim(),el=n.parentElement;if(!s||!vis(el))continue;const z=parseFloat(getComputedStyle(el).fontSize);chars+=s.length;if(z<13)small+=s.length;if(z<12)tiny+=s.length;min=Math.min(min,z);body.push(s)}
        // tap targets: links and buttons that stand alone (links inside a sentence are exempt, as in WCAG 2.5.8)
        const inline=e=>e.tagName==="A"&&getComputedStyle(e).display==="inline"&&e.parentElement.textContent.trim().length>e.textContent.trim().length+2;
        const tg=[...document.querySelectorAll("main a,main button,main input,main select,main summary,#tabs a,.bar a,.lang button")].filter(vis).filter(e=>!inline(e));
        const lowT=tg.filter(e=>e.getBoundingClientRect().height<44).map(e=>(e.textContent||e.id).trim().slice(0,20)+" "+Math.round(e.getBoundingClientRect().height));
        // a term counts as explained when the glossary has it and this tab shows the glossary or links to it
        const gl=(document.getElementById("gl")||{}).textContent||"",reach=vis(document.getElementById("gl"))||[...document.querySelectorAll('main a[href="#glossary"]')].some(vis);
        const text=body.join(" "),jar=J.filter(x=>text.includes(x)&&!(reach&&gl.includes(x)));
        const hs=[...document.querySelectorAll("h1,h2,h3")].filter(vis).map(h=>+h.tagName[1]);let skip=0;for(let i=1;i<hs.length;i++)if(hs[i]>hs[i-1]+1)skip++;
        return {screens:+(document.documentElement.scrollHeight/innerHeight).toFixed(1),chars,small_pct:Math.round(100*small/chars),tiny_pct:Math.round(100*tiny/chars),min_px:min,targets:tg.length,small_targets:lowT.length,small_target_list:[...new Set(lowT)].slice(0,8),jargon:jar,
          h1:hs.filter(x=>x===1).length,heading_skips:skip,first_heading:hs[0]||null,landmarks:["header","nav","main","footer"].filter(x=>document.querySelector(x)).length,skip_link:!!document.querySelector("a.skip"),title:document.title}},JARGON[lang]);
      if(lang==="ko"&&t==="risks"){await p.click("#events button.row");await p.waitForSelector("#events .det>.closebtn");await p.waitForTimeout(200);res[lang][t].first_card_open_screens=await p.evaluate(()=>+(document.querySelector("#events .det:not([hidden])").getBoundingClientRect().height/innerHeight).toFixed(1))}}
    await c.close()}}finally{await b.close();srv.kill()}
  const out={measured_at_utc:new Date().toISOString().slice(0,16)+"Z",label:process.argv[2]||"",viewport:"390x844",tabs:res};
  fs.writeFileSync(path.join(ROOT,"quality/readability.json"),JSON.stringify(out,null,1)+"\n");
  for(const t of TABS){const k=res.ko[t];console.log(t.padEnd(8),"screens",String(k.screens).padEnd(5),"small<13px",(k.small_pct+"%").padEnd(4),"<12px",(k.tiny_pct+"%").padEnd(4),"min",k.min_px,"small targets",k.small_targets+"/"+k.targets,"jargon",k.jargon.length,"h1",k.h1,"skips",k.heading_skips,k.small_target_list.join(" | "))}
})();
