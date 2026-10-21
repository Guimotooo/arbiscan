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
test('new Telegram chat subscribes and receives automatic broadcast, stop removes it',async()=>{
  const kv=fakeKV(), env={WEBHOOK_SECRET:'testsecret',TELEGRAM_BOT_TOKEN:'testtoken',SUBSCRIBERS:kv};
  const old=globalThis.fetch,delivered=[];
  globalThis.fetch=async(url,init)=>{delivered.push(JSON.parse(init.body));return new Response('{"ok":true}',{status:200});};
  const req=(cmd,id)=>new Request('https://arbiscan.test/telegram',{method:'POST',
    headers:{'X-Telegram-Bot-Api-Secret-Token':'testsecret','content-type':'application/json'},
    body:JSON.stringify({message:{text:cmd,chat:{type:'private',id}}})});
  const send=()=>new Request('https://arbiscan.test/broadcast',{method:'POST',
    headers:{Authorization:'Bearer testsecret','content-type':'application/json'},
    body:JSON.stringify({event_key:'1x2:test001',text:'Posible arbitraje no confirmado: partido de prueba'})});
  try{
    assert.equal((await worker.fetch(req('/start',17),env)).status,200);
    assert.equal((await worker.fetch(req('/start',18),env)).status,200);
    assert.ok(kv.values.has('subscriber:17'));assert.ok(kv.values.has('subscriber:18'));
    const sent=await (await worker.fetch(send(),env)).json();
    assert.equal(sent.sent,2);assert.equal(sent.subscribers,2);
    assert.equal((await (await worker.fetch(send(),env)).json()).duplicate,2);
    assert.equal((await worker.fetch(req('/stop',18),env)).status,200);
    assert.ok(!kv.values.has('subscriber:18'));
    assert.equal((await (await worker.fetch(send(),env)).json()).sent,0);
    assert.equal(delivered.filter(x=>x.text.startsWith('Posible')).length,2);
  }finally{globalThis.fetch=old;}
});
test('broadcast rejects unauthenticated calls',async()=>{
  const env={WEBHOOK_SECRET:'s',TELEGRAM_BOT_TOKEN:'t',SUBSCRIBERS:fakeKV()};
  const response=await worker.fetch(new Request('https://arbiscan.test/broadcast',{method:'POST'}),env);
  assert.equal(response.status,403);
});
