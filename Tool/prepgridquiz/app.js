(()=>{"use strict";
const $=id=>document.getElementById(id);let questions=[],exam=[],answers={},current=0,seconds=0,clock=null,showInstant=false;
const sample=`Q4. બોહ્ર પરમાણુ મોડેલમાં ઇલેક્ટ્રોનની બીજી સ્થિર કક્ષાની ત્રિજ્યા R છે. ચોથી કક્ષાની ત્રિજ્યા ______ થાય.
(1) 2 R
(2) R
(3) 8 R
(4) 4 R
ANS: 4`;
const escapeHTML=s=>String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function parseMCQs(raw){
 const lines=raw.replace(/\r/g,"").split("\n"),items=[];let q=null,answerSection=false;
 const push=()=>{if(q&&q.text.trim()&&q.options.length>=2)items.push(q);q=null;};
 for(const rawLine of lines){const line=rawLine.trim();if(!line)continue;
  const answerHeader=/^(answer\s*key|answers|ઉત્તર કુંજી|જવાબ કુંજી)\s*:?$/i.test(line);if(answerHeader){push();answerSection=true;continue;}
  if(answerSection){const pairs=[...line.matchAll(/(?:Q\s*)?(\d+)\s*[-.:)]\s*([1-4A-D])/gi)];if(pairs.length){pairs.forEach(m=>{const target=items.find(x=>String(x.number)===m[1]);if(target)target.answerToken=m[2].toUpperCase();});continue;}}
  const qMatch=line.match(/^(?:Q(?:UESTION)?\s*)?(\d{1,4})\s*[.)\-:]\s*(.+)$/i);
  const optMatch=line.match(/^(?:\(([1-4A-D])\)|([1-4A-D])[.)])\s*(.+)$/i);
  const ansMatch=line.match(/^(?:ANS(?:WER)?|સાચો જવાબ|જવાબ)\s*[:.\-]?\s*\(?([1-4A-D])\)?\s*$/i);
  if(qMatch){push();answerSection=false;q={number:qMatch[1],text:qMatch[2],options:[],answerToken:null};continue;}
  if(optMatch&&q){q.options.push({key:(optMatch[1]||optMatch[2]).toUpperCase(),text:optMatch[3]});continue;}
  if(ansMatch&&q){q.answerToken=ansMatch[1].toUpperCase();continue;}
  if(q){if(q.options.length)q.options[q.options.length-1].text+=" "+line;else q.text+="\n"+line;}
 }
 push();
 return items.map(item=>{const token=item.answerToken;let answer=null;if(token){const index=/^[1-4]$/.test(token)?Number(token)-1:"ABCD".indexOf(token);if(index>=0&&index<item.options.length)answer=item.options[index].key;else if(item.options.some(o=>o.key===token))answer=token;}return {...item,correct:answer};});
}
function showMessage(msg,type="error"){$("parseMessage").textContent=msg;$("parseMessage").className="message "+type;}
function analyse(){const raw=$("mcqInput").value;if(!raw.trim()){showMessage("Pehle MCQs paste karo.");return;}questions=parseMCQs(raw);if(!questions.length){showMessage("MCQs detect nahi hue. Har question ko Q1. se start karo aur options (1)–(4) ya A–D mein do.");return;}
 const keyed=questions.filter(q=>q.correct).length,review=questions.length-keyed;
 $("reviewSummary").textContent=questions.length+" questions detected. Check the preview before starting.";
 $("reviewStats").innerHTML=stat(questions.length,"Detected")+stat(keyed,"Answer key found")+stat(review,"Needs review");
 $("reviewList").innerHTML=questions.map((q,i)=>'<article class="review-item"><div class="review-item-top"><span>QUESTION '+escapeHTML(q.number||i+1)+'</span><span class="tag '+(q.correct?"":"warn")+'">'+(q.correct?"Key: "+escapeHTML(q.correct):"Needs answer review")+'</span></div><p>'+escapeHTML(q.text)+'</p><small class="muted">'+q.options.length+' options detected</small></article>').join("");
 $("setupPanel").classList.add("hidden");$("reviewPanel").classList.remove("hidden");}
function stat(n,label){return '<div class="stat"><strong>'+n+'</strong><span>'+label+'</span></div>';}
function start(){exam=[...questions];if($("shuffleToggle").checked)exam.sort(()=>Math.random()-.5);answers={};current=0;seconds=0;showInstant=$("instantToggle").checked;$("reviewPanel").classList.add("hidden");$("examPanel").classList.remove("hidden");clearInterval(clock);clock=setInterval(()=>{seconds++;$("timer").textContent=fmt(seconds);},1000);renderQuestion();}
function fmt(s){return String(Math.floor(s/60)).padStart(2,"0")+":"+String(s%60).padStart(2,"0");}
function renderQuestion(){const q=exam[current],chosen=answers[current];$("examCounter").textContent="Question "+(current+1)+" of "+exam.length;$("progressBar").style.width=((current+1)/exam.length*100)+"%";
 $("examQuestion").innerHTML='<h3>'+escapeHTML(q.text)+'</h3>'+q.options.map(o=>'<label class="option '+(chosen===o.key?"chosen":"")+'"><input type="radio" name="answer" value="'+escapeHTML(o.key)+'" '+(chosen===o.key?"checked":"")+'><span><b>'+escapeHTML(o.key)+'.</b> '+escapeHTML(o.text)+'</span></label>').join("")+(showInstant&&chosen&&q.correct?'<div class="message success">Correct answer: '+escapeHTML(q.correct)+'</div>':"");
 $("examQuestion").querySelectorAll('input').forEach(input=>input.addEventListener("change",()=>{answers[current]=input.value;renderQuestion();}));
 $("prevBtn").disabled=current===0;$("nextBtn").textContent=current===exam.length-1?"Review & submit":"Next question →";$("answeredCount").textContent=Object.keys(answers).length+" / "+exam.length+" answered";
 $("questionMap").innerHTML=exam.map((_,i)=>'<button class="map-btn '+(answers[i]?"done ":"")+(i===current?"current":"")+'" data-jump="'+i+'">'+(i+1)+'</button>').join("");$("questionMap").querySelectorAll("button").forEach(b=>b.onclick=()=>{current=Number(b.dataset.jump);renderQuestion();});}
function finish(){if(!confirm("Submit this test and view your result?"))return;clearInterval(clock);$("examPanel").classList.add("hidden");$("resultPanel").classList.remove("hidden");const scored=exam.filter(q=>q.correct),right=scored.filter((q)=>answers[exam.indexOf(q)]===q.correct),wrong=scored.filter(q=>answers[exam.indexOf(q)]&&answers[exam.indexOf(q)]!==q.correct),unanswered=exam.filter((q,i)=>!answers[i]).length,unkeyed=exam.filter(q=>!q.correct).length,score=right.length;
 $("scoreValue").textContent=score+"/"+scored.length;$("scoreRing").style.setProperty("--score",(scored.length?score/scored.length*100:0)+"%");$("resultSummary").textContent="Completed in "+fmt(seconds)+". Questions without a detected answer key are not included in the score.";
 $("resultStats").innerHTML=stat(right.length,"Correct")+stat(wrong.length,"Wrong")+stat(unanswered,"Unanswered")+stat(unkeyed,"Needs review")+stat(scored.length,"Scored")+stat(fmt(seconds),"Time");
 const issues=[...wrong.map(q=>({q,type:"Wrong",your:answers[exam.indexOf(q)]})),...exam.filter(q=>!q.correct).map(q=>({q,type:"Answer key missing",your:answers[exam.indexOf(q)]||"Not answered"})),...exam.filter((q,i)=>!answers[i]&&q.correct).map(q=>({q,type:"Unanswered",your:"Not answered"}))];
 $("wrongList").innerHTML=issues.length?issues.map(({q,type,your})=>'<article class="wrong-card"><h4>Q'+escapeHTML(q.number)+' · '+type+'</h4><p>'+escapeHTML(q.text)+'</p><p>Your answer: '+escapeHTML(your)+' · Answer: '+escapeHTML(q.correct||"Needs manual review")+'</p><div class="wrong-actions"><button class="copy-btn" data-copy="'+exam.indexOf(q)+'">Copy question</button></div></article>').join(""):'<div class="stat">Excellent — no mistakes or pending questions.</div>';
 $("wrongList").querySelectorAll("[data-copy]").forEach(btn=>btn.onclick=async()=>{const q=exam[Number(btn.dataset.copy)],txt="Q"+q.number+". "+q.text+"\n"+q.options.map(o=>"("+o.key+") "+o.text).join("\n")+"\nANS: "+(q.correct||"Review");try{await navigator.clipboard.writeText(txt);btn.textContent="Copied ✓";}catch{btn.textContent="Select and copy unavailable";}});
}
function reset(){clearInterval(clock);questions=[];exam=[];answers={};$("resultPanel").classList.add("hidden");$("setupPanel").classList.remove("hidden");$("reviewPanel").classList.add("hidden");$("examPanel").classList.add("hidden");$("mcqInput").value="";showMessage("");window.scrollTo({top:0,behavior:"smooth"});}
$("parseBtn").addEventListener("click",analyse);$("sampleBtn").addEventListener("click",()=>{$("mcqInput").value=sample;showMessage("Sample loaded. Tap Analyse MCQs.","success");});$("clearBtn").addEventListener("click",()=>{$("mcqInput").value="";showMessage("");});$("editInputBtn").addEventListener("click",()=>{$("reviewPanel").classList.add("hidden");$("setupPanel").classList.remove("hidden");});$("startBtn").addEventListener("click",start);$("prevBtn").addEventListener("click",()=>{if(current>0){current--;renderQuestion();}});$("nextBtn").addEventListener("click",()=>{if(current<exam.length-1){current++;renderQuestion();}else finish();});$("submitBtn").addEventListener("click",finish);$("newTestBtn").addEventListener("click",reset);$("year").textContent=new Date().getFullYear();
})();