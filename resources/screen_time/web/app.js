(async()=>{
if(globalThis.FocuserI18n) await FocuserI18n.ready;
const t=globalThis.FocuserI18n?.t||(value=>value);
const $=id=>document.getElementById(id);
let state=null,draft=null,base='',view='today',sub='list',backTo='list',pickGroup=null,pickData=null;
const FIELDS=['id','name','mode','minutes','weekly_minutes','curfews','icon','enabled','color','domains','apps'];
const DAYS=[t('周日'),t('周一'),t('周二'),t('周三'),t('周四'),t('周五'),t('周六')],WEEK=[t('周一'),t('周二'),t('周三'),t('周四'),t('周五'),t('周六'),t('周日')];
const COLORS=['#5856d6','#007aff','#34c759','#ff9500','#ff375f','#af52de'];
const NAV_TITLES={today:t('今天'),limits:t('时间额度'),history:t('近两周'),setup:t('连接与设置')};

async function api(path,body,retried=false){const response=await fetch('/api/'+path,{cache:'no-store',...(body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})});const data=await response.json();if(data.challenge_required&&!retried){const token=await unlock(path,body);return api(path,{...body,token},true);}if(!response.ok)throw Error(t(data.error)||t('请求失败'));return data;}
const minutes=s=>s<60?t(`${Math.ceil(s)}秒`):t(`${Math.ceil(s/60)}分钟`);
const quota=m=>m>=60&&m%60===0?t(`${m/60}小时`):m>60?t(`${Math.floor(m/60)}小时${m%60}分钟`):t(`${m}分钟`);
function el(tag,text,cls){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;}
const GLYPHS={
 video:'<rect x="3.5" y="5.5" width="17" height="13" rx="3"/><path d="M10.2 9.5v5l4.3-2.5z"/>',
 social:'<path d="M4 6.5A2.5 2.5 0 016.5 4h11A2.5 2.5 0 0120 6.5v7a2.5 2.5 0 01-2.5 2.5H11l-4.5 4v-4A2.5 2.5 0 014 13.5z"/><path d="M8.5 8.5h7M8.5 11.5h4"/>',
 chat:'<path d="M4 5h11v8H9.5L6.5 15.5V13H4z"/><path d="M15 9h5v7h-2v2.5L15.5 16H11v-3"/>',
 game:'<path d="M7 8h10a4 4 0 014 4v1.5a2.5 2.5 0 01-4.3 1.7L15.5 14h-7l-1.2 1.2A2.5 2.5 0 013 13.5V12a4 4 0 014-4z"/><path d="M8 10v3M6.5 11.5h3M15.5 10.5h.01M17.5 12.5h.01"/>',
 book:'<path d="M12 6.5C10 5 7 4.5 4 5v13c3-.5 6 0 8 1.5 2-1.5 5-2 8-1.5V5c-3-.5-6 0-8 1.5zM12 6.5v13"/>',
 music:'<path d="M9 17V6l10-2v11"/><circle cx="6.5" cy="17.5" r="2.5"/><circle cx="16.5" cy="15.5" r="2.5"/>',
 shop:'<path d="M5 8h14l-1 12H6z"/><path d="M9 8V6.5a3 3 0 016 0V8"/>',
 work:'<rect x="3.5" y="7.5" width="17" height="12" rx="2.5"/><path d="M9 7.5V6a1.5 1.5 0 011.5-1.5h3A1.5 1.5 0 0115 6v1.5M3.5 13h17"/>',
 globe:'<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.5 2.5 3.5 5.5 3.5 8.5s-1 6-3.5 8.5c-2.5-2.5-3.5-5.5-3.5-8.5s1-6 3.5-8.5z"/>',
 block:'<circle cx="12" cy="12" r="8.5"/><path d="M6 6l12 12"/>',
 grid:'<rect x="4" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.5"/>'};
const GUESS=[['video',/douyin|tiktok|bilibili|b23\.tv|youtube|youtu\.be|netflix|iqiyi|youku|kuaishou|twitch|抖音|视频|b站|影视/i],
 ['chat',/weixin|wechat|telegram|discord|slack|whatsapp|(^|[^a-z])qq([^a-z]|$)|微信|聊天/i],
 ['social',/xiaohongshu|xhslink|twitter|(^|[.\s])x\.com|weibo|zhihu|reddit|instagram|facebook|xiaoheihe|heybox|社交|社区|小红书|知乎|微博/i],
 ['game',/steam|epicgames|game|battle\.net|riot|游戏/i],['music',/spotify|music|netease|163\.com|音乐/i],
 ['shop',/taobao|tmall|jd\.com|amazon|pinduoduo|购物|淘宝|京东/i],['book',/kindle|read|study|learn|notion|obsidian|学习|阅读|书/i],['work',/office|work|feishu|dingtalk|工作|办公/i]];
function guessIcon(g){if(g.icon&&GLYPHS[g.icon])return g.icon;const hay=[g.name,...(g.domains||[]),...(g.apps||[])].join(' ');for(const [id,re] of GUESS)if(re.test(hay))return id;return g.mode==='block'?'block':(g.domains?.length||g.apps?.length)?'globe':'grid';}
function paintIcon(node,g){node.innerHTML=`<svg viewBox="0 0 24 24" aria-hidden="true">${GLYPHS[guessIcon(g)]}</svg>`;}
function icon(g,small){const node=el('div',undefined,'appicon'+(small?' sm':''));paintIcon(node,g);return node;}
const clean=g=>Object.fromEntries(FIELDS.map(k=>[k,structuredClone(g[k]??(k==='curfews'?[]:null))]));
const dirty=()=>draft!==null&&JSON.stringify(draft)!==base;
function loadDraft(){draft=state.groups.map(clean);base=JSON.stringify(draft);}
function step(m,dir,min=1){const next=dir>0?(m<10?m+1:m<60?m+5:m+15):(m<=10?m-1:m<=60?m-5:m-15);return Math.max(min,Math.min(1440,next));}
const weekOf=g=>g.weekly_minutes||Array(7).fill(g.minutes);
function weekSummary(g){if(!g.weekly_minutes)return t('最多 ')+quota(g.minutes);const w=g.weekly_minutes,runs=[];for(let i=0;i<7;i++){const last=runs[runs.length-1];if(last&&last.v===w[i])last.to=i;else runs.push({v:w[i],from:i,to:i});}
 if(runs.length>3)return t(`每天不同 · ${quota(Math.min(...w))}–${quota(Math.max(...w))}`);return runs.map(r=>(r.from===r.to?WEEK[r.from]:r.from===0&&r.to===6?t('每天'):WEEK[r.from]+t('至')+(FocuserI18n.language==='en'?WEEK[r.to]:WEEK[r.to].slice(1)))+' '+(r.v?quota(r.v):t('禁用'))).join(' · ');}
const windowsText=g=>g.curfews.map(c=>`${c.start}–${c.end}`).join('、');
function scheduleText(g){if(!g.enabled)return t('已关闭');if(g.mode==='block')return t('默认禁用');const parts=[weekSummary(g)];if(g.curfews?.length)parts.push(t('停用 ')+windowsText(g));return parts.join(' · ');}
function switchBtn(on,label,fn){const b=el('button',undefined,'toggle'+(on?' on':''));b.type='button';b.setAttribute('role','switch');b.setAttribute('aria-checked',on);b.setAttribute('aria-label',label);b.onclick=fn;return b;}
let toastTimer=0;function toast(text,bad){const t=$('toast');t.textContent=text;t.classList.toggle('err',!!bad);t.hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>t.hidden=true,4200);}
function confirmBox(title,text,yes=t('好')){return new Promise(resolve=>{const d=$('confirm');$('confirm-title').textContent=title;$('confirm-text').textContent=text;$('confirm-text').hidden=!text;$('confirm-yes').textContent=yes;let done=false;const finish=v=>{if(done)return;done=true;d.close();resolve(v)};$('confirm-yes').onclick=()=>finish(true);$('confirm-no').onclick=()=>finish(false);d.oncancel=e=>{e.preventDefault();finish(false)};d.showModal();$('confirm-no').focus();});}

/* ---------- 今天 / 近两周 / 连接 ---------- */
function render(){
  $('date').textContent=state.date+' · '+(state.capabilities?.platform||t('这台电脑'));
  $('pause').textContent=state.paused?t('恢复限制'):t('暂停限制');
  $('connection').textContent=state.paused?t('限制已暂停。今日已用时间保留，恢复后继续计时。'):'';
  const total=state.groups.reduce((n,g)=>n+g.used_seconds,0);
  $('remaining').replaceChildren(document.createTextNode(Math.floor(total/60)),el('span',t('分钟')));
  $('stack').replaceChildren();$('legend').replaceChildren();
  for(const g of state.groups){if(g.used_seconds<=0)continue;const seg=el('i');seg.style.flexGrow=g.used_seconds;seg.style.background=g.color;seg.title=g.name;$('stack').append(seg);const key=el('span',`${g.name} ${minutes(g.used_seconds)}`);key.style.setProperty('--c',g.color);$('legend').append(key);}
  if(!total)$('stack').append(el('i'));
  $('cards').replaceChildren();
  for(const g of state.groups){
    const card=el('div',undefined,'card'),info=el('div',undefined,'cardinfo');
    info.append(el('strong',g.name),el('p',t(`${g.domains.length} 个网站 · ${g.apps.length} 个桌面 App`)));
    if(g.mode==='limit'&&g.enabled){const cap=g.minutes_today*60+g.bonus_seconds,meter=el('div',undefined,'meter'),fill=el('i');fill.style.width=Math.min(100,cap?g.used_seconds/cap*100:0)+'%';fill.style.setProperty('--c',g.blocked?'var(--red)':g.color);meter.append(fill);info.append(meter);}
    const pill=el('span',!g.enabled?t('已关闭'):state.paused?t('已暂停'):g.curfew_active?t('禁用时段'):g.mode==='block'&&g.blocked?t('已封印'):t(`剩余 ${minutes(g.remaining_seconds)}`),'pill'+(g.blocked?' block':''));
    const toggle=switchBtn(g.enabled,t(`${g.name}：${g.enabled?t('点按关闭'):t('点按开启')}限制`),async()=>{const groups=state.groups.map(x=>({...clean(x),enabled:x.id===g.id?!x.enabled:x.enabled}));try{state=await api('config',{groups});render();}catch(e){toast(t(e.message),true)}});
    card.append(icon(g),info,pill);
    if(g.bonus_available){const bonus=el('button',t('再使用 1 分钟'),'bonus');bonus.onclick=async()=>{try{state=await api('bonus',{group:g.id});render();toast(t('已领取 1 分钟，今天不能再领取'))}catch(e){toast(t(e.message),true)}};card.append(bonus)}
    else if(g.enabled&&g.blocked&&!g.curfew_active&&!state.paused)card.append(el('span',state.bonus_used?t('今天的额外 1 分钟已领取'):'','hint'));
    card.append(toggle);$('cards').append(card);
  }
  $('health').replaceChildren();for(const name of ['Chrome','Edge','Firefox','Brave','Opera','Chromium','Vivaldi']){const row=el('div',undefined,'health');row.append(el('b',name),el('span',state.browsers[name]?t('已连接'):t('未连接'),state.browsers[name]?'':'bad'));$('health').append(row);}
  if($('platform-support'))$('platform-support').textContent=state.capabilities?.native_apps?t('桌面 App 拦截已启用。'):(t(state.capabilities?.native_reason)||t('桌面适配层状态未知'));
  if(Object.keys(state.app_errors).length)$('connection').textContent=t('部分 App 拦截失败，请查看连接设置：')+Object.keys(state.app_errors).join('、');
  renderHistory();
}

const openDays=new Set();
function renderHistory(){
  const bars=$('bars');bars.replaceChildren();
  const info=Object.fromEntries(state.groups.map(g=>[g.id,g])),days=Object.entries(state.history).sort().reverse();
  if(!days.length){bars.append(el('p',t('开始使用后，这里会显示分类总时长。'),'muted'));return;}
  const totals=days.map(([,u])=>Object.values(u).reduce((a,b)=>a+b,0)),top=Math.max(3600,...totals);
  days.forEach(([day,usage],i)=>{
    const entries=Object.entries(usage).filter(([,v])=>v>0).sort((a,b)=>b[1]-a[1]);
    const wrap=el('div',undefined,'day'),row=el('button',undefined,'barrow');row.type='button';row.setAttribute('aria-expanded',openDays.has(day));
    const weekday=DAYS[new Date(day+'T00:00:00').getDay()];
    const bar=el('div',undefined,'bar'),stack=el('div',undefined,'stackfill');stack.style.width=(totals[i]/top*100)+'%';
    for(const [id,sec] of entries){const seg=el('i');seg.style.flexGrow=sec;seg.style.background=info[id]?.color||'#8e8e93';seg.title=(info[id]?.name||t('已删除类别'))+' '+minutes(sec);stack.append(seg);}
    bar.append(stack);row.append(el('span',`${day.slice(5)} ${weekday}`),bar,el('b',minutes(totals[i])));wrap.append(row);
    if(openDays.has(day)){const list=el('div',undefined,'daydetail');if(!entries.length)list.append(el('small',t('当天没有使用记录')));for(const [id,sec] of entries){const line=el('div');const dot=el('i');dot.style.background=info[id]?.color||'#8e8e93';line.append(dot,el('span',info[id]?.name||t('已删除类别')),el('b',minutes(sec)));list.append(line);}wrap.append(list);}
    row.onclick=()=>{openDays.has(day)?openDays.delete(day):openDays.add(day);renderHistory();};
    bars.append(wrap);
  });
}

/* ---------- 时间额度（列表 / 管理类别 / 类别详情） ---------- */
const current=()=>draft.find(g=>g.id===sub);
const SUBS=['list','manage','downtime'];
function openSub(next,from){backTo=from;sub=next;renderLimits();window.scrollTo(0,0);}
function renderLimits(){
  if(!state)return;if(!draft)loadDraft();
  if(!SUBS.includes(sub)&&!current())sub='manage';
  const body=$('limits-body');body.replaceChildren();
  $('back').hidden=view!=='limits'||sub==='list';
  if(sub==='list')limitsList(body);else if(sub==='manage')manageList(body);else if(sub==='downtime')downtimeList(body);else detail(body,current());
  $('savebar').hidden=!dirty();
  document.querySelector('nav [data-view=limits]').classList.toggle('pending',dirty());
  if(!dirty()){$('saved').textContent='';$('saved').classList.remove('err');}
  if(view==='limits')$('title').textContent=sub==='list'?t('时间额度'):sub==='manage'?t('管理类别'):sub==='downtime'?t('停用时间'):current().name;
}
function stepperFor(g,label,key='minutes',min=1,index=null){
  const get=()=>index===null?g[key]:g[key][index],put=v=>{if(index===null)g[key]=v;else g[key][index]=v;};
  const box=el('div',undefined,'stepper'),minus=el('button','−'),plus=el('button','+');
  minus.type=plus.type='button';
  minus.setAttribute('aria-label',t(`减少${label}额度`));plus.setAttribute('aria-label',t(`增加${label}额度`));
  minus.disabled=g.mode==='block'||get()<=min;plus.disabled=g.mode==='block'||get()>=1440;
  minus.onclick=()=>{put(step(get(),-1,min));renderLimits();};plus.onclick=()=>{put(step(get(),1,min));renderLimits();};
  box.append(minus,plus);return box;
}
function curfewSummary(){const n=draft.filter(g=>g.mode==='limit'&&g.curfews?.length).length;return n?t(`${n} 个类别已设置`):t('未设置');}
function limitsList(body){
  const intro=el('div',undefined,'intro');
  const down=el('button',undefined,'navrow'),moon=el('span',undefined,'navicon');moon.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19.5 14.5A8 8 0 019.5 4.5a8 8 0 1010 10z"/></svg>';
  const dtext=el('span',undefined,'grow');dtext.append(el('b',t('停用时间')),el('small',t('在设定的时段内禁用类别')));
  down.append(moon,dtext,el('span',curfewSummary(),'val'),el('span','›','chev'));down.onclick=()=>openSub('downtime','list');
  const manage=el('button',undefined,'navrow'),stack=el('div',undefined,'stack');for(const g of draft.slice(0,4))stack.append(icon(g,true));manage.append(el('span',t('管理类别'),'grow'),stack,el('span','›','chev'));manage.onclick=()=>openSub('manage','list');
  intro.append(down,manage);body.append(intro);
  body.append(el('div',t('每日额度'),'group-label'));
  for(const g of draft){
    const row=el('div',undefined,'row'),open=el('button',undefined,'link rowinfo');
    open.append(el('b',g.name),el('small',scheduleText(g)));open.onclick=()=>openSub(g.id,'list');
    row.append(icon(g),open,g.weekly_minutes||g.mode==='block'?el('span','›','chev'):stepperFor(g,g.name));body.append(row);
  }
  body.append(el('p',t('点按类别可按星期单独设置额度、添加网站与 App。'),'note'));
}
function manageList(body){
  for(const g of draft){const row=el('div',undefined,'row'),open=el('button',undefined,'link rowinfo');open.append(el('b',g.name),el('small',t(`${g.domains.length} 个网站 · ${g.apps.length} 个 App`)));open.onclick=()=>openSub(g.id,'manage');row.append(icon(g),open,el('span','›','chev'));body.append(row);}
  const add=el('button',t('＋ 新分类'),'light addcat');add.onclick=()=>{if(draft.length>=20){toast(t('最多 20 个分类'),true);return;}const g={id:'group_'+Date.now(),name:t('新分类'),mode:'limit',minutes:30,weekly_minutes:null,curfews:[],enabled:true,color:COLORS[draft.length%COLORS.length],domains:[],apps:[]};draft.push(g);openSub(g.id,'manage');const n=document.querySelector('.detailhead input');if(n){n.focus();n.select();}};body.append(add);
}
function downtimeList(body){
  body.append(el('p',t('在停用时间内，所选类别的网站与桌面 App 会被禁用，即使当天额度还有剩余。可跨午夜，例如 22:00 到 06:00。'),'note'));
  const items=draft.filter(g=>g.mode==='limit');
  if(!items.length)body.append(el('p',t('没有可设置的类别（“默认禁用”的类别始终禁用）。'),'note'));
  for(const g of items){
    const card=el('div',undefined,'group-card'),head=el('div',undefined,'row flat'),info=el('div',undefined,'rowinfo');
    info.append(el('b',g.name),el('small',g.curfews.length?t('每天 ')+windowsText(g):t('未设置')));
    head.append(icon(g,true),info,switchBtn(g.curfews.length>0,t(`${g.name} 停用时间`),()=>toggleCurfew(g)));
    card.append(head);curfewRows(card,g);body.append(card);
  }
}
function toggleCurfew(g){g.curfews=g.curfews.length?[]:[{start:'22:00',end:'06:00'}];renderLimits();}
const PRESETS=[[t('上午'),'08:00','12:00'],[t('下午'),'14:00','18:00'],[t('晚间'),'22:00','06:00'],[t('深夜'),'00:00','06:00']];
const pad=n=>String(n).padStart(2,'0');
function timePick(value,label,onChange){
  const [h,m]=value.split(':').map(Number),box=el('span',undefined,'timepick'),hs=el('select'),ms=el('select');
  for(let i=0;i<24;i++)hs.append(new Option(pad(i),pad(i)));
  for(const v of [...new Set([...Array(12).keys()].map(i=>i*5).concat(m))].sort((x,y)=>x-y))ms.append(new Option(pad(v),pad(v)));
  hs.value=pad(h);ms.value=pad(m);hs.setAttribute('aria-label',label+t('小时'));ms.setAttribute('aria-label',label+t('分钟'));
  const fire=()=>onChange(`${hs.value}:${ms.value}`);hs.onchange=ms.onchange=fire;
  box.append(hs,el('span',':'),ms);return box;
}
function timeline(g){
  const bar=el('div',undefined,'timeline');bar.setAttribute('role','img');bar.setAttribute('aria-label',t(`${g.name} 的停用时间：${windowsText(g)}`));
  const clock=t=>+t.slice(0,2)*60+ +t.slice(3);
  for(const c of g.curfews){const a=clock(c.start),b=clock(c.end);for(const [from,to] of b>a?[[a,b]]:[[a,1440],[0,b]]){if(to<=from)continue;const seg=el('i');seg.style.left=from/14.4+'%';seg.style.width=(to-from)/14.4+'%';bar.append(seg);}}
  const wrap=el('div',undefined,'timelinewrap'),ticks=el('div',undefined,'ticks');for(const t of ['0','6','12','18','24'])ticks.append(el('span',t));wrap.append(bar,ticks);return wrap;
}
function toggleCurfew(g){g.curfews=g.curfews.length?[]:[{start:'22:00',end:'06:00'}];renderLimits();}
function curfewRows(box,g){
  if(g.curfews.length)box.append(timeline(g));
  const note=el('p',undefined,'bad small');
  g.curfews.forEach((w,i)=>{
    const row=el('div',undefined,'row flat sub winrow');
    const x=el('button',t('移除'),'x');x.type='button';x.setAttribute('aria-label',t(`移除时段${i+1}`));x.onclick=()=>{g.curfews.splice(i,1);renderLimits();};
    const body=el('div',undefined,'wintimes');
    for(const [key,text] of [['start',t('从')],['end',t('到')]]){
      const field=el('label',undefined,'timefield');field.append(el('small',text),timePick(w[key],t(`${g.name} 时段${i+1}${text}`),v=>{if(v===w[key==='start'?'end':'start']){note.textContent=t('开始和结束时间不能相同');renderLimits();return;}w[key]=v;renderLimits();}));body.append(field);
    }
    if(clockOf(w.end)<=clockOf(w.start))body.append(el('small',t('次日'),'nextday'));
    row.append(body,x);box.append(row);
  });
  if(g.curfews.length<6){
    const chips=el('div',undefined,'chips');chips.append(el('small',t('快速添加')));
    for(const [name,start,end] of PRESETS){const c=el('button',`${name} ${start.slice(0,2)}–${end.slice(0,2)}`,'chip');c.type='button';c.disabled=g.curfews.some(w=>w.start===start&&w.end===end);c.onclick=()=>{g.curfews.push({start,end});renderLimits();};chips.append(c);}
    const custom=el('button',t('＋ 自定义'),'chip');custom.type='button';custom.onclick=()=>{const last=g.curfews[g.curfews.length-1]||{end:'20:00'},m=Math.min(1439,clockOf(last.end)+120),end=pad(Math.floor(m/60))+':'+pad(m%60);g.curfews.push({start:last.end,end:end===last.end?'23:59':end});renderLimits();};chips.append(custom);box.append(chips);
  }
  box.append(note);
}
const clockOf=t=>+t.slice(0,2)*60+ +t.slice(3);
function detail(body,g){
  const head=el('div',undefined,'detailhead'),badge=icon(g),name=el('input');name.value=g.name;name.maxLength=50;name.setAttribute('aria-label',t('分类名称'));
  name.oninput=()=>{g.name=name.value;paintIcon(badge,g);$('title').textContent=name.value||t('未命名');$('savebar').hidden=!dirty();};
  const colors=el('div',undefined,'colors');for(const c of COLORS){const b=el('button',undefined,g.color===c?'on':'');b.type='button';b.style.background=c;b.setAttribute('aria-label',t('颜色 ')+c);b.setAttribute('aria-pressed',g.color===c);b.onclick=()=>{g.color=c;renderLimits();};colors.append(b);}
  const glyphRow=el('div',undefined,'glyphs'),current=guessIcon(g);
  for(const id of Object.keys(GLYPHS)){const b=el('button',undefined,'glyph'+(id===current?' on':''));b.type='button';b.innerHTML=`<svg viewBox="0 0 24 24" aria-hidden="true">${GLYPHS[id]}</svg>`;b.setAttribute('aria-label',t('图标 ')+id);b.setAttribute('aria-pressed',id===current);b.onclick=()=>{g.icon=g.icon===id?null:id;renderLimits();};glyphRow.append(b);}
  head.append(badge,name,glyphRow,colors);body.append(head);

  const seg=el('div',undefined,'segment');for(const [mode,text] of [['limit',t('每日额度')],['block',t('默认禁用')]]){const b=el('button',text,g.mode===mode?'on':'');b.type='button';b.setAttribute('aria-pressed',g.mode===mode);b.onclick=()=>{g.mode=mode;g.minutes=mode==='block'?0:(g.minutes||30);if(mode==='block'){g.weekly_minutes=null;g.curfews=[];}renderLimits();};seg.append(b);}body.append(seg);
  if(g.mode==='limit'){
    body.append(el('div',t('每日额度'),'group-label'));
    if(!g.weekly_minutes){const row=el('div',undefined,'row'),info=el('div',undefined,'rowinfo');info.append(el('b',t('每天共享额度')),el('small',t('最多 ')+quota(g.minutes)+t('，网站与 App 合计')));row.append(info,stepperFor(g,g.name));body.append(row);}
    const each=el('div',undefined,'row'),ei=el('div',undefined,'rowinfo');ei.append(el('b',t('按星期单独设置')),el('small',g.weekly_minutes?t('周一到周日各自的额度，0 表示当天禁用'):t('关闭时每天使用同一额度')));
    each.append(ei,switchBtn(!!g.weekly_minutes,t('按星期单独设置额度'),()=>{g.weekly_minutes=g.weekly_minutes?null:Array(7).fill(g.minutes);renderLimits();}));body.append(each);
    if(g.weekly_minutes){const card=el('div',undefined,'group-card');WEEK.forEach((day,i)=>{const row=el('div',undefined,'row flat sub'),info=el('div',undefined,'rowinfo'),v=g.weekly_minutes[i];info.append(el('b',day),el('small',v?quota(v):t('当天禁用')));row.append(info,stepperFor(g,day,'weekly_minutes',0,i));card.append(row);});body.append(card);}

    body.append(el('div',t('停用时间'),'group-label'));
    const cf=el('div',undefined,'group-card'),ch=el('div',undefined,'row flat'),ci=el('div',undefined,'rowinfo');
    ci.append(el('b',t('启用停用时间')),el('small',g.curfews.length?t('每天 ')+windowsText(g)+t(' 禁用'):t('未设置，可添加多个时段')));ch.append(ci,switchBtn(g.curfews.length>0,t('设置停用时间'),()=>toggleCurfew(g)));cf.append(ch);curfewRows(cf,g);body.append(cf);
  }
  body.append(el('div',t('状态'),'group-label'));
  const en=el('div',undefined,'row'),eninfo=el('div',undefined,'rowinfo');eninfo.append(el('b',t('启用限制')),el('small',g.enabled?t('正在限制此类别'):t('已关闭，此类别不受限制')));en.append(eninfo,switchBtn(g.enabled,g.enabled?t('关闭此类别限制'):t('开启此类别限制'),()=>{g.enabled=!g.enabled;renderLimits();}));body.append(en);

  body.append(el('div',t('网站'),'group-label'));
  const sites=el('div',undefined,'list');
  if(!g.domains.length)sites.append(el('div',t('还没有网站'),'empty'));
  for(const d of g.domains){const li=el('div',undefined,'li'),x=el('button',t('移除'),'x');x.type='button';x.setAttribute('aria-label',t('移除 ')+d);x.onclick=()=>{g.domains=g.domains.filter(v=>v!==d);renderLimits();};li.append(el('span',d,'grow'),x);sites.append(li);}
  body.append(sites);
  const form=el('form',undefined,'addrow'),input=el('input');input.placeholder='youtube.com';input.setAttribute('aria-label',t('添加网站'));const add=el('button',t('添加'),'light');add.type='submit';
  const err=el('p',undefined,'bad small');
  form.onsubmit=async e=>{e.preventDefault();err.textContent='';try{await addDomain(g,input.value);input.value='';renderLimits();}catch(ex){err.textContent=t(ex.message);}};
  form.append(input,add);body.append(form,err);

  body.append(el('div',t('桌面 App'),'group-label'));
  const apps=el('div',undefined,'list');
  if(!g.apps.length)apps.append(el('div',state.capabilities?.native_apps?t('还没有 App'):t('当前系统仅支持浏览器限制'),'empty'));
  for(const a of g.apps){const li=el('div',undefined,'li'),x=el('button',t('移除'),'x');x.type='button';x.setAttribute('aria-label',t('移除 ')+a);x.onclick=()=>{g.apps=g.apps.filter(v=>v!==a);renderLimits();};li.append(el('span',a,'grow'),x);apps.append(li);}
  body.append(apps);
  if(state.capabilities?.native_apps){const choose=el('button',t('＋ 添加 App'),'light');choose.type='button';choose.onclick=()=>openPicker(g);choose.style.marginBottom='22px';body.append(choose);}

  const del=el('button',t('删除“')+g.name+t('”类别'),'danger');del.type='button';del.style.display='block';del.style.width='100%';del.disabled=draft.length<=1;
  del.onclick=async()=>{if(await confirmBox(t('删除“')+g.name+t('”类别？'),'',t('删除'))){draft=draft.filter(x=>x.id!==g.id);sub='manage';backTo='list';renderLimits();}};body.append(del);
}
function ownerOf(kind,value,except){return draft.find(x=>x.id!==except.id&&x[kind].includes(value));}
async function moveIn(kind,g,value){
  if(g[kind].includes(value))throw Error(t('已在此类别中'));
  const other=ownerOf(kind,value,g);
  if(other){if(!await confirmBox(t(`将“${value}”移到${g.name}？`),t('此项目将从其当前类别（')+other.name+t('）移出。')))return false;other[kind]=other[kind].filter(v=>v!==value);}
  g[kind].push(value);return true;
}
async function addDomain(g,raw){
  const value=raw.trim().toLowerCase().replace(/^[a-z]+:\/\//,'').replace(/[/?#].*$/,'').replace(/^www\./,'').replace(/\.$/,'');
  if(!value)throw Error(t('请输入域名'));
  if(!/^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$/.test(value)||!value.includes('.')||value.includes('..'))throw Error(t('请输入纯域名，例如 youtube.com'));
  await moveIn('domains',g,value);
}

/* ---------- App 选择器 ---------- */
async function openPicker(g){
  pickGroup=g;$('pickersearch').value='';$('pickererror').textContent='';$('applist').replaceChildren(el('p',t('正在读取运行中的 App…'),'muted'));$('picker').showModal();
  try{pickData=await api('apps');}catch(e){pickData={apps:[],supported:false};$('pickererror').textContent=t(e.message);}
  renderPicker();
}
function renderPicker(){
  const g=pickGroup,q=$('pickersearch').value.trim().toLowerCase();
  const names=[...new Set([...(pickData?.apps||[]),...draft.flatMap(x=>x.apps)])].sort((a,b)=>a.localeCompare(b,'zh'));
  const shown=names.filter(n=>!q||n.toLowerCase().includes(q));
  $('pickercount').textContent=g.apps.length?t(`已选择 ${g.apps.length} 个 · 共 ${names.length} 个 App`):t(`${names.length} 个 App`);
  const list=$('applist');list.replaceChildren();
  if(!shown.length){list.append(el('p',names.length?t('没有匹配的 App'):t('没有可选的 App'),'muted'));return;}
  let letter='',group=null;
  for(const name of shown){
    const first=name[0].toUpperCase(),key=/[A-Z]/.test(first)?first:'#';
    if(key!==letter){letter=key;list.append(el('div',key,'letter'));group=el('div');list.append(group);}
    const on=g.apps.includes(name),other=on?null:ownerOf('apps',name,g);
    const row=el('button',undefined,'pickrow'+(on?' on':''));row.type='button';row.setAttribute('aria-pressed',on);
    row.append(el('span','✓','check'),el('span',name,'grow'),el('small',other?other.name:''));
    row.onclick=async()=>{$('pickererror').textContent='';
      if(on)g.apps=g.apps.filter(v=>v!==name);else{try{if(!await moveIn('apps',g,name))return;}catch(e){$('pickererror').textContent=t(e.message);return;}}
      renderPicker();};
    group.append(row);
  }
}
$('pickersearch').oninput=renderPicker;
$('manualform').onsubmit=async e=>{e.preventDefault();const v=$('manualname').value.trim().toLowerCase();$('pickererror').textContent='';
  if(!/^[^\\/:*?"<>|]{1,100}\.exe$/.test(v)){$('pickererror').textContent=t('请输入程序文件名，例如 douyin.exe');return;}
  try{if(await moveIn('apps',pickGroup,v)){$('manualname').value='';renderPicker();}}catch(ex){$('pickererror').textContent=t(ex.message);}};
$('closepicker').onclick=()=>$('picker').close();
$('picker').addEventListener('close',()=>{pickGroup=null;renderLimits();});

/* ---------- 导航与操作 ---------- */
function showView(name){
  view=name;
  document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('selected',x.dataset.view===name));
  document.querySelectorAll('.view').forEach(x=>x.hidden=x.id!==name);
  $('title').textContent=NAV_TITLES[name];$('back').hidden=true;
  if(name==='limits'&&state){if(!dirty())loadDraft();sub='list';renderLimits();}
  window.scrollTo(0,0);
}
document.querySelectorAll('nav button').forEach(button=>button.onclick=()=>showView(button.dataset.view));
$('back').onclick=()=>{sub=SUBS.includes(sub)||backTo==='list'?'list':backTo;backTo='list';renderLimits();};
$('discard').onclick=()=>{draft=JSON.parse(base);renderLimits();};
$('save').onclick=async()=>{const status=$('saved');status.classList.remove('err');status.textContent=t('正在保存…');
  try{state=await api('config',{groups:draft});loadDraft();render();renderLimits();$('savebar').hidden=false;status.textContent=t('已保存，立即生效');setTimeout(()=>{if(!dirty())$('savebar').hidden=true;},2200);}
  catch(error){status.classList.add('err');status.textContent=t(error.message);}};
$('pause').onclick=async()=>{try{state=await api('pause',{paused:!state.paused});render()}catch(e){toast(t(e.message),true)}};
$('quit').onclick=async()=>{if(await confirmBox(t('退出并恢复访问？'),t('今日已用额度会保留；退出期间网站与 App 不受限制。'),t('退出'))){try{await api('quit',{});$('connection').textContent=t('已退出。双击桌面“屏幕使用时间 Local”入口后可恢复限制。')}catch(e){toast(t(e.message),true)}}};
window.addEventListener('beforeunload',e=>{if(dirty()){e.preventDefault();e.returnValue='';}});
async function refresh(){try{state=await api('status');render()}catch{$('connection').textContent=t('本地服务未连接，请启动 Focuser 服务后刷新。')}}
setInterval(refresh,1500);refresh();

async function unlock(action,payload){
 const challenge=await api('challenge',{action,payload});
 return new Promise((resolve,reject)=>{
  const dialog=el('dialog'),heading=el('h2',t('先完成定积分验证')),operation=el('p',t('本次操作：')+({pause:t('暂停限制'),quit:t('退出并恢复访问'),config:t('放宽规则')}[action]||action));
  dialog.className='challenge';const formula=el('p',challenge.expression,'formula'),instructions=el('p',t(challenge.instructions)),reason=el('textarea');reason.placeholder=t('写出你的推导过程，至少80字');reason.maxLength=4000;reason.setAttribute('aria-label',t('定积分推导'));
  const answer=el('input');answer.placeholder=t('数值结果，保留6位小数');answer.setAttribute('aria-label',t('定积分结果'));answer.inputMode='decimal';
  const waiting=el('p'),error=el('p',undefined,'bad'),submit=el('button',t('验算并执行')),cancel=el('button',t('保留限制，取消'),'light'),row=el('div');row.append(submit,cancel);
  dialog.append(heading,operation,formula,instructions,reason,answer,waiting,error,row);document.body.append(dialog);
  const start=performance.now();let finished=false;
  function update(){const left=Math.max(0,Math.ceil(challenge.wait_seconds-(performance.now()-start)/1000));waiting.textContent=left?t('至少再思考 ')+left+t(' 秒'):t('可以提交验算');submit.disabled=left>0||reason.value.trim().length<80||!answer.value.trim();}
  function cleanup(){clearInterval(timer);dialog.remove();}
  function abort(){if(finished)return;finished=true;cleanup();reject(Error(t('已取消，限制保持原样')));}
  const timer=setInterval(update,250);reason.oninput=answer.oninput=update;cancel.onclick=abort;dialog.oncancel=e=>{e.preventDefault();abort();};
  submit.onclick=async()=>{submit.disabled=true;try{const result=await api('verify',{id:challenge.id,answer:answer.value,reasoning:reason.value});finished=true;cleanup();resolve(result.token);}catch(e){error.textContent=t(e.message);update();}};
  dialog.showModal();update();reason.focus();
 });
}

})();
