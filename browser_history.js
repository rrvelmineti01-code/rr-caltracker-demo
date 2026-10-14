// No network calls. Only explicit PDF export uses the Streamlit trigger.
export const STORAGE_KEY = 'rr-caltracker:diary:v1';
const DAY = 86400000;
const NAMES = ['Calories', 'Protein', 'Carbs', 'Fat'];
const CATEGORIES = ['Breakfast', 'Lunch', 'Dinner', 'Snack'];
export function localDate(now = new Date()) {
  return `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
}
export function earliest(days, now = new Date()) {
  const d = new Date(now); d.setDate(d.getDate() - days + 1); return localDate(d);
}
export function emptyState() { return {version:1, enabled:false, days:14, meals:[]}; }
export function prune(state, now = new Date()) {
  const min = earliest(state.days, now), max = localDate(now);
  return {...state, meals: !state.enabled ? [] : state.meals.filter(m =>
    m.date >= min && m.date <= max && Number.isFinite(m.savedAt) && m.savedAt <= now.getTime() &&
    now.getTime()-m.savedAt < state.days * DAY)};
}
export function read(storage, now = new Date()) {
  const raw = storage.getItem(STORAGE_KEY);
  if (raw === null) return emptyState();
  let s;
  try { s = JSON.parse(raw); } catch { throw new Error('Saved history is unreadable. You can clear it below and start again.'); }
  if (s.version !== 1 || typeof s.enabled !== 'boolean' || ![1,7,14].includes(s.days) || !Array.isArray(s.meals) ||
      s.meals.some(m => !m || typeof m.id !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(m.date) || !m.snapshot || !Array.isArray(m.snapshot.foods) || !m.snapshot.totals)) {
    throw new Error('Saved history is unreadable. You can clear it below and start again.');
  }
  const next = prune(s, now);
  if (JSON.stringify(next) !== JSON.stringify(s)) write(storage, next);
  return next;
}
export function write(storage, state) {
  try { storage.setItem(STORAGE_KEY, JSON.stringify(state)); }
  catch { throw new Error('This browser could not save history. Check browser storage permissions or free space. Your previous saved meals were not replaced.'); }
  return state;
}
export function save(state, token, snapshot, date, category, now = new Date()) {
  if (!state.enabled) throw new Error('Enable optional history before saving.');
  if (!token || !snapshot || snapshot.demo || !snapshot.foods?.length) throw new Error('Review a real meal before saving.');
  const parsed = new Date(`${date}T12:00:00`);
  if (Number.isNaN(parsed.getTime()) || localDate(parsed) !== date || !/^\d{4}-\d{2}-\d{2}$/.test(date) || date < earliest(state.days,now) || date > localDate(now) || !CATEGORIES.includes(category)) throw new Error('Choose a date within your history window and a meal type.');
  const old = state.meals.find(m => m.id === token);
  if (old && now.getTime() - old.savedAt >= state.days * DAY) throw new Error('This meal has expired. Analyze a new photo to log another meal.');
  // Snapshot comes from Python's field allowlist; never include image bytes or API keys.
  const next = prune(state,now);
  next.meals = next.meals.filter(m => m.id !== token);
  next.meals.push({id:token,date,category,savedAt:old?.savedAt ?? now.getTime(),snapshot});
  return next;
}
export function summarize(meals) {
  return Object.fromEntries(NAMES.map(n => [n, !meals.length || meals.some(m => !Number.isFinite(m.snapshot.totals[n])) ? null : meals.reduce((v,m)=>v+m.snapshot.totals[n],0)]));
}

export default function(component) {
  const {data, parentElement, setTriggerValue} = component;
  const root = parentElement.querySelector('#diary-root');
  let storage, state, failure='', notice='', confirming=false;
  try { storage=window.localStorage; state=read(storage); }
  catch(e) { state=emptyState(); failure=e.message || 'Browser history is unavailable.'; }
  const el=(tag,text,cls) => {const n=document.createElement(tag); if(text!==undefined) n.textContent=text; if(cls) n.className=cls; return n;};
  const button=(label,action,cls='')=>{const b=el('button',label,cls); b.type='button'; b.onclick=action; return b;};
  const run=(fn)=>{try {fn(); failure='';} catch(e) {failure=e.message;} draw();};
  const commit=(next)=>{state=write(storage,next);};
  const value=(n,k)=>Number.isFinite(n) ? `${Math.round(n).toLocaleString()} ${k==='Calories'?'kcal':'g'}` : 'Unavailable';
  function labeled(label,input) {const l=el('label',label); l.append(input); return l;}
  function select(options,initial) {const s=el('select'); for(const v of options) {const o=el('option',String(v));o.value=String(v);s.append(o);} s.value=String(initial);return s;}
  function draw() {
    root.replaceChildren();
    const box=el('section',undefined,'diary'); root.append(box);
    if (notice) {const n=el('p',notice,'notice');n.setAttribute('role','status');box.append(n);}
    if (failure) {const n=el('p',failure,'error');n.setAttribute('role','alert');box.append(n);}
    if (!state.enabled) {
      box.append(el('h3','A little history, only if you want it.'),el('p','History is off. Save reviewed meals on this browser for up to 14 days. No profile, photos, or cross-device sync.'));
      box.append(button('Enable history on this browser',()=>run(()=>{if(!storage)throw new Error('Browser storage is unavailable.');commit({...emptyState(),enabled:true});notice='History enabled. Meals are saved only when you choose Save.';}),'primary'));
    } else {
      if(data.mode==='save' && data.snapshot) {
        box.append(el('h3','Save this meal?'));
        const form=el('form'), date=el('input');date.type='date';date.min=earliest(state.days);date.max=localDate();
        const old=state.meals.find(m=>m.id===data.token);date.value=old?.date ?? localDate();
        const type=select(CATEGORIES,old?.category ?? 'Lunch'), fields=el('div',undefined,'fields');
        fields.append(labeled('Meal date',date),labeled('Meal type',type));form.append(fields);
        const submit=el('button',old?'Update saved meal':'Save meal on this browser','primary');submit.type='submit';form.append(submit);
        form.onsubmit=e=>{e.preventDefault();run(()=>{state=read(storage);commit(save(state,data.token,data.snapshot,date.value,type.value));notice='Saved on this browser. You can remove it in History.';});};box.append(form);
      } else if(data.mode==='status') {
        box.append(el('h3','History is on for this browser.'),el('p','Saved meals are in History. New meals are saved only when you choose Save.'));
      } else {
        box.append(el('h3','Your saved meals'));
        if (!state.meals.length) box.append(el('p','Nothing saved yet. Analyze a photo, review it, then choose Save.'));
        const groups=Object.groupBy ? Object.groupBy([...state.meals].sort((a,b)=>b.date.localeCompare(a.date)),m=>m.date) : state.meals.reduce((g,m)=>((g[m.date]??=[]).push(m),g),{});
        for(const date of Object.keys(groups).sort().reverse()) {
          const meals=groups[date], group=el('section',undefined,'day');group.append(el('h4',date));
          const totals=summarize(meals);group.append(el('p',`${value(totals.Calories,'Calories')} logged · ${meals.length} meal${meals.length===1?'':'s'}`,'day-total'));
          group.append(el('p', ['Protein','Carbs','Fat'].map(k=>`${k}: ${value(totals[k],k)}`).join(' · '),'small'));
          if(meals.some(m=>m.snapshot.partial)) group.append(el('p','Partial totals: unmatched foods are excluded.','small'));
          for(const m of meals.sort((a,b)=>b.savedAt-a.savedAt)) {
            const card=el('details');card.append(el('summary',`${m.category} · ${m.snapshot.foods.map(f=>f.name).join(', ')} · ${value(m.snapshot.totals.Calories,'Calories')}`));
            const macros=el('div',undefined,'macros');for(const k of NAMES)macros.append(el('span',`${k}: ${value(m.snapshot.totals[k],k)}`));card.append(macros);
            const list=el('ul');for(const f of m.snapshot.foods)list.append(el('li',`${f.name} · ${Math.round(f.grams)} g`));card.append(list);
            card.append(button('Download PDF',()=>{notice='Preparing PDF…';draw();setTriggerValue('export',{requestId:crypto.randomUUID(),snapshot:m.snapshot});}));
            card.append(button('Delete meal',()=>run(()=>{state=read(storage);commit({...state,meals:state.meals.filter(x=>x.id!==m.id)});notice='Meal deleted.';}),'danger'));
            group.append(card);
          }box.append(group);
        }
      }
      box.append(el('p',`Only this browser · ${state.days}-day window · Photos are never included`,'small'));
      const settings=el('details');settings.append(el('summary','History settings'));
      const days=select([1,7,14],state.days);days.onchange=()=>run(()=>{state=read(storage);commit(prune({...state,days:Number(days.value)}));notice='History window updated. Older meals removed.';});
      settings.append(labeled('Keep meals for this many days',days),el('p','Older meals expire. Cleanup runs while the app is open and on your next visit. Clearing browser data also removes this history.','small'));
      if(!confirming) settings.append(button('Turn off and clear history',()=>{confirming=true;draw();root.querySelector('details:last-child').open=true;},'danger'));
      else {settings.open=true;settings.append(el('p','Delete all meals saved on this browser?'),button('Yes, clear and turn off',()=>run(()=>{storage.removeItem(STORAGE_KEY);state=emptyState();confirming=false;notice='History cleared and turned off.';}),'danger'),button('Cancel',()=>{confirming=false;draw();}));}
      box.append(settings);
    }
    if (failure && storage) {
      const reset=button('Clear local history',()=>{reset.replaceWith(button('Confirm: delete local history',()=>run(()=>{storage.removeItem(STORAGE_KEY);state=emptyState();notice='Local history cleared.';}),'danger'));},'danger');box.append(reset);
    }
  }
  draw();
  if (data.pdf) {
    if(data.pdf.error){failure=data.pdf.error;draw();}
    else if(data.pdf.base64) {
      try {const bytes=Uint8Array.from(atob(data.pdf.base64),c=>c.charCodeAt(0));const url=URL.createObjectURL(new Blob([bytes],{type:'application/pdf'}));const a=el('a');a.href=url;a.download='RR_CalTracker_saved_meal.pdf';root.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);notice='PDF ready. Check your downloads.';draw();}
      catch {failure='PDF download failed. Try again.';draw();}
    }
  }
  const refresh=()=>{try{state=read(storage);failure='';}catch(e){failure=e.message;}draw();};
  const timer=setInterval(refresh,60000);
  const changed=e=>{if(e.key===STORAGE_KEY)refresh();};
  window.addEventListener('storage',changed);
  return ()=>{clearInterval(timer);window.removeEventListener('storage',changed);};
}
