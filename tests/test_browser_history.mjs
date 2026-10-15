// node --test tests/test_browser_history.mjs (no npm dependencies)
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
import test from 'node:test';
const code=await readFile(new URL('../browser_history.js',import.meta.url),'utf8');
const m=await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
const snapshot={demo:false,foods:[{name:'Rice',grams:150}],totals:{Calories:195,Protein:4,Carbs:42,Fat:.5}};
const now=new Date(2026,9,13,12);
class Storage {constructor(){this.data=new Map();this.writes=0;}getItem(k){return this.data.get(k)??null;}setItem(k,v){this.writes++;this.data.set(k,v);}removeItem(k){this.data.delete(k);}}
const enabled=()=>({...m.emptyState(),enabled:true});
test('history off by default, opening does not write or save',()=>{const s=new Storage();assert.equal(m.read(s,now).enabled,false);assert.equal(s.writes,0);assert.throws(()=>m.save(m.emptyState(),'one',snapshot,m.localDate(now),'Lunch',now),/Enable/);});
test('explicit saving survives restart; updating same meal does not duplicate or reset TTL',()=>{const s=new Storage();const first=m.save(enabled(),'one',snapshot,m.localDate(now),'Lunch',now);m.write(s,first);let next=m.read(s,now);const later=new Date(now.getTime()+3600000);next=m.save(next,'one',{...snapshot,totals:{...snapshot.totals,Calories:260}},m.localDate(now),'Dinner',later);assert.equal(next.meals.length,1);assert.equal(next.meals[0].savedAt,now.getTime());assert.equal(next.meals[0].snapshot.totals.Calories,260);});
test('separate browser stores never see each other',()=>{const a=new Storage(),b=new Storage();m.write(a,m.save(enabled(),'one',snapshot,m.localDate(now),'Lunch',now));assert.equal(m.read(b,now).meals.length,0);});
test('date window and TTL both enforced at 14 days',()=>{let s=m.save(enabled(),'today',snapshot,'2026-10-13','Lunch',now);s=m.save(s,'old',snapshot,'2026-09-30','Lunch',now);const tomorrow=new Date(2026,9,14,12);assert.deepEqual(m.prune(s,tomorrow).meals.map(x=>x.id),['today']);const boundary=new Date(now.getTime()+14*86400000);assert.equal(m.prune(s,boundary).meals.length,0);assert.throws(()=>m.save(s,'old',snapshot,'2026-10-27','Lunch',boundary),/expired/);});
test('next visit persists removal of expired entries',()=>{const store=new Storage();m.write(store,m.save(enabled(),'one',snapshot,'2026-10-13','Lunch',now));assert.equal(m.read(store,new Date(2026,9,28)).meals.length,0);assert.equal(JSON.parse(store.getItem(m.STORAGE_KEY)).meals.length,0);});
test('shortening to 1 or 7 days prunes, never permits future or invalid date',()=>{let s=m.save(enabled(),'one',snapshot,'2026-10-07','Lunch',now);assert.equal(m.prune({...s,days:7},now).meals.length,1);assert.equal(m.prune({...s,days:1},now).meals.length,0);for(const date of ['2026-10-14','2026-09-29','bad'])assert.throws(()=>m.save(s,'two',snapshot,date,'Lunch',now));const nov=new Date(2026,10,3);assert.throws(()=>m.save(s,'two',snapshot,'2026-10-32','Lunch',nov));});
test('local date handles timezone/day boundary without UTC conversions',()=>{assert.equal(m.localDate(new Date(2026,9,13,23,59)),'2026-10-13');assert.equal(m.earliest(14,now),'2026-09-30');});
test('unavailable nutrient is not silently treated as zero',()=>{assert.equal(m.summarize([]).Calories,null);assert.equal(m.summarize([{snapshot}]).Calories,195);assert.equal(m.summarize([{snapshot},{snapshot:{...snapshot,totals:{Calories:null}}}]).Calories,null);});
test('quota and corruption failures preserve original data',()=>{const s=new Storage();m.write(s,enabled());const before=s.getItem(m.STORAGE_KEY);s.setItem=()=>{throw Error('QuotaExceeded');};assert.throws(()=>m.write(s,m.save(enabled(),'one',snapshot,'2026-10-13','Lunch',now)),/could not save/);assert.equal(s.getItem(m.STORAGE_KEY),before);s.data.set(m.STORAGE_KEY,'broken');assert.throws(()=>m.read(s,now),/unreadable/);assert.equal(s.getItem(m.STORAGE_KEY),'broken');});
test('clearing removes all local diary data; demo cannot be saved',()=>{const s=new Storage();m.write(s,enabled());s.removeItem(m.STORAGE_KEY);assert.deepEqual(m.read(s,now),m.emptyState());assert.throws(()=>m.save(enabled(),'demo',{...snapshot,demo:true},'2026-10-13','Lunch',now));});
test('frontend contains no network clients or unsafe HTML insertion',()=>{assert.doesNotMatch(code,/\bfetch\s*\(|XMLHttpRequest|innerHTML\s*=/);});
test('today sums only its date, resets at midnight and keeps earlier history separate',()=>{
  let s=m.save(enabled(),'yesterday',snapshot,'2026-10-12','Dinner',now);
  assert.equal(m.todaySummary(s,now).totals.Calories,0);
  s=m.save(s,'breakfast',snapshot,'2026-10-13','Breakfast',now);
  s=m.save(s,'lunch',{...snapshot,totals:{...snapshot.totals,Calories:405,Protein:26}},'2026-10-13','Lunch',now);
  assert.equal(m.todaySummary(s,now).totals.Calories,600);
  assert.equal(m.todaySummary(s,now).totals.Protein,30);
  assert.equal(m.todaySummary(s,now).count,2);
  const midnight=new Date(2026,9,14,0,0);
  assert.equal(m.todaySummary(s,midnight).totals.Calories,0);
  assert.equal(m.prune(s,midnight).meals.length,3);
});
test('today updates same meal, excludes deletion, respects opt out and missing nutrition',()=>{
  let s=m.save(enabled(),'one',snapshot,'2026-10-13','Lunch',now);
  s=m.save(s,'one',{...snapshot,totals:{...snapshot.totals,Calories:260,Protein:null},partial:true},'2026-10-13','Lunch',now);
  const total=m.todaySummary(s,now);
  assert.equal(total.count,1);assert.equal(total.totals.Calories,260);assert.equal(total.totals.Protein,null);assert.equal(total.partial,true);
  assert.equal(m.todaySummary({...s,meals:[]},now).totals.Calories,0);
  assert.equal(m.todaySummary({...s,enabled:false},now).totals.Calories,null);
});
