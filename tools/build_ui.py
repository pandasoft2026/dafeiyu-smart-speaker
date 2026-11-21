# -*- coding: utf-8 -*-
"""生成自包含的大肥鱼主题对话界面 HTML（base64 内嵌立绘）。"""
import base64, os

AST = r"D:\workbuddy\2026-11-19-10-59-25\dafeiyu\assets"
OUT = r"D:\workbuddy\2026-11-19-10-59-25\dafeiyu\index.html"

def b64(path):
    return base64.b64encode(open(path, "rb").read()).decode()

char = b64(os.path.join(AST, "char_ui.png"))
avatar = b64(os.path.join(AST, "avatar_ui.png"))

html = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>大肥鱼</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{width:100%;height:100%;overflow:hidden;font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:linear-gradient(160deg,#eaf5ff 0%,#cfe6fb 45%,#a9d0ef 100%);color:#1b4b78;user-select:none}
.app{display:flex;flex-direction:column;height:100%;padding:18px 20px 20px}
/* 顶栏 */
.head{display:flex;align-items:center;gap:12px;flex:0 0 auto}
.head img{width:56px;height:56px;border-radius:50%;border:3px solid #fff;box-shadow:0 4px 12px rgba(40,100,160,.25)}
.head .tt{display:flex;flex-direction:column}
.head .tt b{font-size:27px;color:#155a94;letter-spacing:2px}
.head .tt small{font-size:14px;color:#5a8db8;margin-top:2px}
.status{margin-left:auto;font-size:13px;color:#3f7bab;display:flex;align-items:center;gap:6px}
.dot{width:9px;height:9px;border-radius:50%;background:#4caf50;box-shadow:0 0 6px #4caf50}
.dot.off{background:#bbb;box-shadow:none}
/* 角色区 */
.stage{flex:0 0 auto;display:flex;justify-content:center;align-items:flex-end;height:250px;position:relative}
.stage img{height:240px;filter:drop-shadow(0 8px 12px rgba(30,80,130,.2));transition:transform .25s}
.stage.talk img{transform:translateY(-6px) scale(1.03)}
.bubble{position:absolute;top:6px;right:12px;max-width:62%;background:#fff;border-radius:18px 18px 4px 18px;padding:12px 16px;font-size:20px;line-height:1.45;color:#1b4b78;box-shadow:0 6px 18px rgba(30,90,150,.18);display:none}
.bubble.show{display:block;animation:pop .25s ease}
.bubble.wait{color:#89a9c4;font-size:18px}
@keyframes pop{from{opacity:0;transform:scale(.9) translateY(8px)}to{opacity:1;transform:none}}
/* 字幕 */
.asr{flex:0 0 auto;min-height:44px;display:flex;align-items:center;justify-content:center;margin:6px 0}
.asr span{background:rgba(255,255,255,.75);border-radius:20px;padding:8px 20px;font-size:19px;color:#2c6a9e;min-width:60px;text-align:center}
/* 回答区 */
.answer{flex:1 1 auto;overflow-y:auto;background:rgba(255,255,255,.82);border-radius:22px;padding:20px 22px;font-size:25px;line-height:1.6;color:#123a60;box-shadow:inset 0 2px 10px rgba(40,100,160,.08)}
.answer:empty::before{content:"按住下面的按钮，和我说说话吧～";color:#9dbdd7;font-size:22px}
/* 底部按钮 */
.foot{flex:0 0 auto;margin-top:14px;display:flex;flex-direction:column;align-items:center;gap:8px}
.mic{width:150px;height:150px;border-radius:50%;border:6px solid #fff;background:linear-gradient(150deg,#4aa3e8,#2166ad);box-shadow:0 8px 26px rgba(30,100,170,.4),inset 0 -6px 14px rgba(0,0,0,.12);display:flex;flex-direction:column;align-items:center;justify-content:center;color:#fff;transition:transform .12s,box-shadow .12s}
.mic:active,.mic.rec{transform:scale(.94);box-shadow:0 4px 14px rgba(30,100,170,.5),inset 0 0 22px rgba(255,120,120,.6);background:linear-gradient(150deg,#ff8a8a,#e14b4b)}
.mic .ico{font-size:52px;line-height:1}
.mic .lb{font-size:17px;margin-top:4px;letter-spacing:1px}
.hint{font-size:14px;color:#5a8db8}
</style>
</head>
<body>
<div class="app">
  <div class="head">
    <img src="data:image/png;base64,__AVATAR__">
    <div class="tt"><b>大肥鱼</b><small>你的 AI 小伙伴</small></div>
    <div class="status"><span class="dot" id="dot"></span><span id="st">就绪</span></div>
  </div>
  <div class="stage" id="stage">
    <img src="data:image/png;base64,__CHAR__">
    <div class="bubble" id="bubble"></div>
  </div>
  <div class="asr"><span id="asr">点一下麦克风，跟我说话～</span></div>
  <div class="answer" id="answer"></div>
  <div class="foot">
    <div class="mic" id="mic"><div class="ico">🎤</div><div class="lb" id="miclb">按住说话</div></div>
    <div class="hint">松开即发送 · 静音键也可返回</div>
  </div>
</div>
<script>
const API='http://127.0.0.1:8899';
const mic=document.getElementById('mic'),miclb=document.getElementById('miclb');
const asr=document.getElementById('asr'),answer=document.getElementById('answer');
const bubble=document.getElementById('bubble'),stage=document.getElementById('stage');
const dot=document.getElementById('dot'),st=document.getElementById('st');
let recording=false, polling=null;

function setStatus(t,on){st.textContent=t;dot.className='dot'+(on?'':' off')}
function say(t,wait){bubble.textContent=t;bubble.className='bubble show'+(wait?' wait':'');stage.classList.add('talk');setTimeout(()=>stage.classList.remove('talk'),600)}

async function startRec(){
  if(recording)return; recording=true;
  mic.classList.add('rec'); miclb.textContent='聆听中…';
  asr.textContent='正在听…'; answer.textContent='';
  setStatus('录音中',true); say('我在听～',true);
  try{ await fetch(API+'/api/start',{method:'POST'}); }catch(e){}
  polling=setInterval(pollAsr,500);
}
async function stopRec(){
  if(!recording)return; recording=false;
  mic.classList.remove('rec'); miclb.textContent='按住说话';
  clearInterval(polling);
  asr.textContent='识别中…'; setStatus('识别中',true); say('让我想想…',true);
  try{
    const r=await fetch(API+'/api/stop',{method:'POST'});
    const j=await r.json();
    onResult(j);
  }catch(e){ onResult({text:'',error:'连接失败'}); }
}
async function pollAsr(){
  try{
    const r=await fetch(API+'/api/partial'); const j=await r.json();
    if(j.text) asr.textContent=j.text;
  }catch(e){}
}
function onResult(j){
  if(j.error){ asr.textContent='出错了'; say('呜…'+j.error,true); setStatus('错误',false); return; }
  asr.textContent=j.text||'（没听清）';
  setStatus('思考中',true); say('收到！',false);
  answer.textContent=j.answer||'…';
  setStatus('就绪',true);
  // 逐字显示
  if(j.answer){ const full=j.answer; answer.textContent=''; let i=0;
    const timer=setInterval(()=>{answer.textContent=full.slice(0,++i); if(i>=full.length)clearInterval(timer)},28);
  }
}
// 触摸事件（长按/点击切换）
let downT=null;
mic.addEventListener('touchstart',e=>{e.preventDefault();downT=Date.now();startRec()},{passive:false});
mic.addEventListener('touchend',e=>{e.preventDefault();stopRec()},{passive:false});
mic.addEventListener('mousedown',e=>{e.preventDefault();startRec()});
mic.addEventListener('mouseup',e=>{e.preventDefault();stopRec()});
// 静音键(已映射为BACK)在浏览器里无法拦截,由后端守护处理
setStatus('就绪',true);
</script>
</body></html>
'''

html = html.replace("__AVATAR__", avatar).replace("__CHAR__", char)
open(OUT, "w", encoding="utf-8").write(html)
print("created", OUT, len(html), "chars")
