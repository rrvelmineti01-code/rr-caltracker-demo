// DOM integration: RR_JSDOM_MODULE=/path/to/jsdom/lib/api.js node --test tests/test_history_dom.mjs
// jsdom is a developer-only dependency, never required by the deployed app.
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import test from 'node:test';
const {JSDOM}=await import(process.env.RR_JSDOM_MODULE || 'jsdom');
const code=await readFile(new URL('../browser_history.js',import.meta.url),'utf8');
const m=await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
const snapshot={demo:false,foods:[{name:'<script>alert(1)</script> Rice',grams:150}],totals:{Calories:195,Protein:4,Carbs:42,Fat:.5},partial:false};
function mount(data,seed=null) {
  const dom=new JSDOM('<div id="host"></div>',{url:'https://rr-caltracker.example'});
  globalThis.window=dom.window;globalThis.document=dom.window.document;
  if(seed)window.localStorage.setItem(m.STORAGE_KEY,JSON.stringify(seed));
  const root=document.querySelector('#host').attachShadow({mode:'open'});const child=document.createElement('div');child.id='diary-root';root.append(child);
  const triggers=[];const dispose=m.default({data,parentElement:root,setTriggerValue:(...args)=>triggers.push(args)});
  return {dom,root,triggers,dispose};
}
function press(ctx,label) {const b=[...ctx.root.querySelectorAll('button')].find(b=>b.textContent===label);assert.ok(b,`Missing ${label}`);b.click();}
test('opt in, explicit save, reload, local totals, safe text, PDF trigger, deletion and opt out',()=>{
  let c=mount({mode:'save',snapshot,token:'one'});
  try {
    assert.equal(window.localStorage.length,0);assert.equal(c.triggers.length,0);
    press(c,'Enable history on this browser');
    assert.equal(JSON.parse(window.localStorage.getItem(m.STORAGE_KEY)).meals.length,0);
    const form=c.root.querySelector('form');form.dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true}));
    let saved=JSON.parse(window.localStorage.getItem(m.STORAGE_KEY));assert.equal(saved.meals.length,1);assert.equal(c.triggers.length,0);
    c.root.querySelector('form').dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true}));
    saved=JSON.parse(window.localStorage.getItem(m.STORAGE_KEY));assert.equal(saved.meals.length,1);c.dispose();c.dom.window.close();
    c=mount({mode:'history'},saved);
    assert.ok(c.root.textContent.includes('195 kcal logged'));assert.ok(c.root.textContent.includes('Protein: 4 g'));
    assert.equal(c.root.querySelectorAll('script').length,0);assert.ok(c.root.textContent.includes('<script>alert(1)</script> Rice'));
    press(c,'Download PDF');assert.equal(c.triggers.length,1);assert.equal(c.triggers[0][0],'export');assert.deepEqual(c.triggers[0][1].snapshot,snapshot);
    press(c,'Delete meal');assert.equal(JSON.parse(window.localStorage.getItem(m.STORAGE_KEY)).meals.length,0);
    press(c,'Turn off and clear history');assert.ok(window.localStorage.getItem(m.STORAGE_KEY));press(c,'Yes, clear and turn off');assert.equal(window.localStorage.getItem(m.STORAGE_KEY),null);
  } finally {c.dispose();c.dom.window.close();}
});
test('expiry is persisted on mount and the 1 day setting removes older meals',()=>{
  const now=new Date(), yesterday=new Date();yesterday.setDate(now.getDate()-1);
  const state={...m.emptyState(),enabled:true,meals:[{id:'one',date:m.localDate(yesterday),category:'Lunch',savedAt:now.getTime()-86400000,snapshot}]};
  const c=mount({mode:'history'},state);
  try {const select=c.root.querySelector('select');select.value='1';select.dispatchEvent(new window.Event('change'));assert.equal(JSON.parse(window.localStorage.getItem(m.STORAGE_KEY)).meals.length,0);assert.equal(c.triggers.length,0);}
  finally {c.dispose();c.dom.window.close();}
});
test('storage events synchronize another open tab without sending diary to server',()=>{
  const c=mount({mode:'history'},{...m.emptyState(),enabled:true});
  try {window.localStorage.removeItem(m.STORAGE_KEY);window.dispatchEvent(new window.StorageEvent('storage',{key:m.STORAGE_KEY}));assert.ok(c.root.textContent.includes('History is off'));assert.equal(c.triggers.length,0);}
  finally {c.dispose();c.dom.window.close();}
});
test('today widget synchronizes save, corrected save, deletion and opt out in the same page',()=>{
  const c=mount({mode:'today'});const extras=[];
  function add(data) {
    const host=document.createElement('div');document.body.append(host);
    const root=host.attachShadow({mode:'open'}), child=document.createElement('div');child.id='diary-root';root.append(child);
    const triggers=[];const dispose=m.default({data,parentElement:root,setTriggerValue:(...args)=>triggers.push(args)});
    const ctx={root,triggers,dispose};extras.push(ctx);return ctx;
  }
  function submit(ctx){ctx.root.querySelector('form').dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true}));}
  try {
    assert.ok(c.root.textContent.includes('History is off'));
    press(c,'Enable daily log on this browser');assert.ok(c.root.textContent.includes('0 kcal'));
    const a=add({mode:'save',snapshot,token:'breakfast'});
    assert.ok(c.root.textContent.includes('0 kcal')); // analysis alone never counts
    submit(a);assert.ok(c.root.textContent.includes('195 kcal'));
    const lunch={...snapshot,totals:{Calories:405,Protein:26,Carbs:50,Fat:10}};
    const b=add({mode:'save',snapshot:lunch,token:'lunch'});submit(b);
    assert.ok(c.root.textContent.includes('600 kcal'));assert.ok(c.root.textContent.includes('30 g'));
    const correction=add({mode:'save',snapshot:{...lunch,totals:{...lunch.totals,Calories:305}},token:'lunch'});submit(correction);
    assert.ok(c.root.textContent.includes('500 kcal'));assert.ok(c.root.textContent.includes('2 meals'));
    const h=add({mode:'history'});press(h,'Delete meal');
    assert.ok(c.root.textContent.includes('195 kcal'));assert.ok(c.root.textContent.includes('1 meal'));
    press(h,'Turn off and clear history');press(h,'Yes, clear and turn off');
    assert.ok(c.root.textContent.includes('History is off'));
    assert.equal(c.triggers.length,0);for(const e of extras)assert.equal(e.triggers.length,0);
  } finally {for(const e of extras)e.dispose();c.dispose();c.dom.window.close();}
});
