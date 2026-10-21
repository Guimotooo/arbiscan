import test from 'node:test';
import assert from 'node:assert/strict';
import worker,{answerText} from './arbiscan.mjs';
const starter=['/comparar','Deporte: futbol','Partido: Barcelona vs Real Madrid','Mercado: total goles 2.5 (90 minutos)','Capital: 100'];
const msg=(...odds)=>[...starter,...odds].join('\n');
test('example arbitrage correctly accepts Bet365 ES and Sportium ES',()=>{
  const out=answerText(msg('Bet365 ES | mas | 2.10','Sportium ES | menos | 2.05'));
  assert.match(out,/Bet365 ES/);assert.match(out,/Sportium ES/);assert.match(out,/3\.73/);assert.match(out,/NO verificadas/i);
});
test('missing result is rejected',()=>assert.match(answerText(msg('Bet365 ES | mas | 2.10')),/Falta cubrir/));
test('non arb is not reported as a success',()=>assert.match(answerText(msg('Bet365 ES | mas | 1.80','Sportium ES | menos | 1.80')),/Sin arbitraje/));
test('soccer winner two-way rejected',()=>assert.match(answerText(msg('Bet365 ES | mas | 2.10','Sportium ES | menos | 2.05').replace('total goles 2.5 (90 minutos)','ganador')),/En fútbol usa 1X2/));
test('whole-number total with push rejected',()=>assert.match(answerText(msg('Bet365 ES | mas | 2.10','Sportium ES | menos | 2.05').replace('2.5 (90','3 (90')),/Solo totales/));
test('NBA total without extra time rejected',()=>assert.match(answerText(msg('Bet365 ES | mas | 2.10','Sportium ES | menos | 2.05').replace('futbol','nba').replace('total goles 2.5 (90 minutos)','total puntos 220.5')),/prórroga/));
test('no arbitrage within same brand',()=>assert.match(answerText(msg('Bet365 ES | mas | 2.10','Bet365 ES | menos | 2.05')),/Sin arbitraje/));
test('template and help',()=>{assert.match(answerText('/plantilla'),/Bet365 ES/);assert.match(answerText('/start'),/ArbiiScan/);});
function fakeKV(){
 const values=new Map();
 return {values,async put(k,v){values.set(k,v);},async get(k){return values.get(k)||null;},
   async delete(k){values.delete(k);},
   async list({prefix}){return {keys:[...values.keys()].filter(k=>k.startsWith(prefix)).map(name=>({name})),list_complete:true};}};
}
test('Telegram user selects bookmakers and only receives matching alerts',async()=>{
 const kv=fakeKV(),env={WEBHOOK_SECRET:'testsecret',TELEGRAM_BOT_TOKEN:'testtoken',SUBSCRIBERS:kv};
 const previous=globalThis.fetch,delivered=[];
 globalThis.fetch=async(url,init)=>{delivered.push({url,body:JSON.parse(init.body)});return new Response('{"ok":true}',{status:200});};
 const req=(id,text)=>new Request('https://arbiscan.test/telegram',{method:'POST',headers:{'X-Telegram-Bot-Api-Secret-Token':'testsecret','content-type':'application/json'},body:JSON.stringify({message:{text,chat:{type:'private',id}}})});
 const cb=(id,data)=>new Request('https://arbiscan.test/telegram',{method:'POST',headers:{'X-Telegram-Bot-Api-Secret-Token':'testsecret','content-type':'application/json'},body:JSON.stringify({callback_query:{id:'cb1',from:{id},data,message:{chat:{id,type:'private'}}}})});
 const broadcast=(key)=>new Request('https://arbiscan.test/broadcast',{method:'POST',headers:{Authorization:'Bearer testsecret','content-type':'application/json'},body:JSON.stringify({event_key:key,text:'Posible arbitraje no confirmado: partido de prueba',books:['bet365.es','winamax.es']})});
 try{
  assert.equal((await worker.fetch(req(17,'/start'),env)).status,200);
  assert.ok(!kv.values.has('subscriber:17'));
  assert.ok(delivered.at(-1).body.reply_markup);
  assert.equal((await worker.fetch(cb(17,'books:save'),env)).status,200);
  assert.ok(kv.values.has('subscriber:17'));
  await worker.fetch(req(18,'/start'),env);
  await worker.fetch(cb(18,'books:toggle:winamax.es'),env);
  await worker.fetch(cb(18,'books:save'),env);
  const sent=await (await worker.fetch(broadcast('1x2:choice001'),env)).json();
  assert.equal(sent.sent,1);assert.equal(sent.subscribers,2);
  assert.equal((await (await worker.fetch(broadcast('1x2:choice001'),env)).json()).duplicate,1);
  await worker.fetch(req(17,'/stop'),env);
  assert.ok(!kv.values.has('subscriber:17'));
  assert.equal((await (await worker.fetch(broadcast('1x2:choice002'),env)).json()).sent,0);
  assert.equal(delivered.filter(x=>x.body.text?.startsWith('Posible')).length,1);
 }finally{globalThis.fetch=previous;}
});
test('broadcast rejects unauthenticated calls',async()=>{
  const env={WEBHOOK_SECRET:'s',TELEGRAM_BOT_TOKEN:'t',SUBSCRIBERS:fakeKV()};
  const response=await worker.fetch(new Request('https://arbiscan.test/broadcast',{method:'POST'}),env);
  assert.equal(response.status,403);
});
