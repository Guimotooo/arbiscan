/* Telegram webhook for ArbiiScan. All user-submitted prices are unverified. */
const BRAND = new Map(Object.entries({bet365:'Bet365', sportium:'Sportium',winamax:'Winamax',betfair:'Betfair',bwin:'bwin',codere:'Codere',luckia:'Luckia','william hill':'William Hill',betway:'Betway',retabet:'RETAbet',sportybet:'SportyBet'}));
const norm=s=>String(s).trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
const number=s=>{const n=Number(String(s).trim().replace(',','.'));if(!Number.isFinite(n))throw Error('Número o cuota no válidos');return n;};
const help='ArbiiScan: /start o /casas para seleccionar las casas. /estado consulta las preferencias; /stop cancela los avisos. La detección automática actual cubre fútbol 1X2 con Bet365 ES y Winamax ES.';
const template='/comparar\nDeporte: futbol\nPartido: Barcelona vs Real Madrid\nMercado: total goles 2.5 (90 minutos)\nCapital: 100\nBet365 ES | mas | 2.10\nSportium ES | menos | 2.05\n\n⚠️ Precios ficticios de ejemplo. Sustituye las cuotas.';
function outcomes(market,sport){
  const m=norm(market),s=norm(sport),soccer=s.includes('fut')||s.includes('soccer');
  const nba=s.includes('nba')||s.includes('basket')||s.includes('balonc'),tennis=s.includes('tenis')||s.includes('tennis');
  if(m.startsWith('1x2')){if(!soccer||!/(90|reglament)/.test(m))throw Error('1X2 exige fútbol (90 minutos)');return ['1','X','2'];}
  if(m.startsWith('ganador')){if(soccer)throw Error('En fútbol usa 1X2 e incluye empate');if(!tennis&&!nba)throw Error('Ganador: solo tenis o baloncesto');if(nba&&!/(prorroga|\bot\b)/.test(m))throw Error('Indica si incluye prórroga');return ['1','2'];}
  const match=m.match(/(?:total\s+(?:de\s+)?(?:goles|puntos|juegos)|mas\s*\/\s*menos)\s+(\d+(?:[.,]\d+)?)/);
  if(!match)throw Error('Mercado incompatible: usa 1X2, ganador o total x.5');
  const line=number(match[1]);if(!Number.isInteger(line*2)||Math.round(line*2)%2!==1)throw Error('Solo totales con línea x.5');
  if(soccer&&!/(90|reglament)/.test(m))throw Error('En fútbol indica 90 minutos');
  if(nba&&!/(prorroga|\bot\b)/.test(m))throw Error('En NBA indica si incluye prórroga');
  return ['MAS','MENOS'];
}
function parse(input){
  const lines=input.split(/\r?\n/).map(s=>s.trim()).filter(Boolean),fields=new Map(),quotes=[];
  for(const line of lines.slice(1)){
    if(line.includes('|')){
      const p=line.split('|').map(s=>s.trim());if(p.length!==3)throw Error('Formato: Casa ES | selección | cuota');
      let key=norm(p[0]).replace(/\s+espana$/,' es');const es=key.endsWith(' es');if(es)key=key.slice(0,-3).trim();
      if(key.includes('exchange'))throw Error('Exchange requiere ajuste de comisiones');
      const brand=BRAND.get(key);if(!brand)throw Error('Casa no admitida: '+p[0]);
      const price=number(p[2]);if(price<=1||price>=1000)throw Error('Cuota fuera de rango');
      quotes.push({brand,book:brand+(es?' ES':''),choice:norm(p[1]),price});
    }else{const i=line.indexOf(':');if(i>=0)fields.set(norm(line.slice(0,i)),line.slice(i+1).trim());}
  }
  for(const key of ['deporte','partido','mercado','capital'])if(!fields.get(key))throw Error('Falta '+key);
  const capital=number(fields.get('capital'));if(capital<=0||capital>100000)throw Error('Capital fuera de rango');
  const names={mas:'MAS',over:'MAS',menos:'MENOS',under:'MENOS','1':'1',home:'1',local:'1',x:'X',draw:'X',empate:'X','2':'2',away:'2',visitante:'2'};
  const possible=outcomes(fields.get('mercado'),fields.get('deporte'));
  if(quotes.length>24)throw Error('Máximo 24 cuotas');
  for(const quote of quotes){quote.outcome=names[quote.choice];if(!possible.includes(quote.outcome))throw Error('Selección incompatible: '+quote.choice);}
  return {capital,fields,possible,quotes};
}
function allocate(capital,chosen){
  const cents=Math.round(capital*100),inv=chosen.map(q=>1/q.price),den=inv.reduce((a,b)=>a+b,0);
  if(den>=1)return null;
  const desired=inv.map(x=>cents*x/den),stakes=desired.map(Math.floor);
  let remaining=cents-stakes.reduce((a,b)=>a+b,0);
  const byFraction=stakes.map((_,i)=>i).sort((a,b)=>(desired[b]-stakes[b])-(desired[a]-stakes[a]));
  for(let i=0;i<remaining;i++)stakes[byFraction[i]]++;
  const min=Math.min(...stakes.map((s,i)=>s*chosen[i].price/100));
  if(min<=capital)return null;
  return {stakes:stakes.map(v=>v/100),profit:min-capital,roi:(min/capital-1)*100};
}
function evaluate(parsed){
  const groups=parsed.possible.map(out=>parsed.quotes.filter(q=>q.outcome===out));
  const missing=parsed.possible.filter((_,i)=>groups[i].length===0);if(missing.length)throw Error('Falta cubrir: '+missing.join(', '));
  let best=null;
  const rec=(i,selected)=>{if(i===groups.length){
    if(new Set(selected.map(x=>x.brand)).size<2)return;
    const alloc=allocate(parsed.capital,selected);
    if(alloc&&(!best||alloc.profit>best.alloc.profit))best={selected:[...selected],alloc};return;
  }for(const q of groups[i])rec(i+1,[...selected,q]);};
  rec(0,[]);return best;
}
export function answerText(input){
  if(typeof input!=='string')return '';
  const command=norm(input.trim().split(/[\s\n]/)[0]).split('@')[0];
  if(command==='/plantilla')return template;
  if(['/start','/help','/ayuda'].includes(command))return help;
  if(command!=='/comparar')return '';
  try{
    const p=parse(input),best=evaluate(p);
    const intro='ARBIISCAN | COMPARACIÓN MANUAL\n⚠️ Cuotas NO verificadas\n\nEvento: '+p.fields.get('partido')+'\nMercado: '+p.fields.get('mercado')+'\nCapital: '+p.capital.toFixed(2)+' €\n\n';
    if(!best)return intro+'❌ Sin arbitraje matemático completo entre marcas distintas.';
    const detail=best.selected.map((q,i)=>'• '+q.book+': '+p.possible[i]+' @ '+q.price.toFixed(2)+' → '+best.alloc.stakes[i].toFixed(2)+' €').join('\n');
    return intro+detail+'\n\nBeneficio mínimo TEÓRICO: +'+best.alloc.profit.toFixed(2)+' € ('+best.alloc.roi.toFixed(2)+' %).\nAntes de apostar verifica precios, reglas y límites en las casas. No se han realizado apuestas.';
  }catch(err){return '⚠️ '+err.message+'\nEnvía /plantilla.';}
}
const AVAILABLE_BOOKS=Object.freeze({'bet365.es':'Bet365 ES','winamax.es':'Winamax ES'});
const pendingKey=id=>'pending:'+String(id);
function readBooks(value){
 if(!value)return [];
 try{const data=JSON.parse(value);return Array.isArray(data.books)?[...new Set(data.books.filter(b=>Object.hasOwn(AVAILABLE_BOOKS,b)))]:[];}
 catch{return Object.keys(AVAILABLE_BOOKS);}
}
function selectionMarkup(books){return {inline_keyboard:[
 ...Object.entries(AVAILABLE_BOOKS).map(([key,label])=>[{text:(books.includes(key)?'✅ ':'⬜ ')+label,callback_data:'books:toggle:'+key}]),
 [{text:'✅ Guardar selección',callback_data:'books:save'}]
]};}
function selectionMessage(){return '🏦 Elige las casas que utilizas y pulsa Guardar selección.\nPor ahora están conectadas Bet365 ES y Winamax ES. Para una oportunidad entre ambas debes tener las dos. Otros deportes y operadores siguen pendientes de validación.';}
const chatKey=id=>'subscriber:'+String(id);
const json=(obj,status=200)=>new Response(JSON.stringify(obj),{status,headers:{'content-type':'application/json'}});
async function telegramSend(env,chatId,text,replyMarkup){
  const reply=await fetch('https://api.telegram.org/bot'+env.TELEGRAM_BOT_TOKEN+'/sendMessage',{
    method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify({chat_id:chatId,text:text.slice(0,4000),...(replyMarkup?{reply_markup:replyMarkup}:{})})
  });
  // Do not swallow permanent or temporary delivery failures.
  return reply;
}
async function subscribers(store){
  const ids=[];let cursor;
  do{
    const page=await store.list({prefix:'subscriber:',limit:1000,...(cursor?{cursor}:{})});
    for(const item of page.keys)ids.push(item.name.slice('subscriber:'.length));
    cursor=page.list_complete?null:page.cursor;
  }while(cursor);
  return ids;
}
export default {
  async fetch(request,env){
    const path=new URL(request.url).pathname;
    if(request.method==='GET'&&path==='/health')return new Response('ArbiiScan webhook disponible');
    if(request.method==='POST'&&path==='/broadcast'){
      if(!env.WEBHOOK_SECRET||!env.TELEGRAM_BOT_TOKEN||!env.SUBSCRIBERS)
        return json({error:'Broadcast sin configurar'},503);
      if(request.headers.get('Authorization')!== 'Bearer '+env.WEBHOOK_SECRET)
        return json({error:'No autorizado'},403);
      let data;
      try{data=await request.json();}catch{return json({error:'JSON inválido'},400);}
      if(typeof data?.text!=='string'||data.text.length<10||data.text.length>4000||
         !/^[\w:.-]{4,160}$/.test(String(data?.event_key||'')))
        return json({error:'Alerta inválida'},400);
      const ids=await subscribers(env.SUBSCRIBERS);
      const required=Array.isArray(data.books)?data.books:[];
      if(required.length<2||required.some(b=>!Object.hasOwn(AVAILABLE_BOOKS,b)))return json({error:'Casas inválidas'},400);
      const report={subscribers:ids.length,sent:0,failed:0,duplicate:0};
      for(const id of ids){
        const selected=readBooks(await env.SUBSCRIBERS.get(chatKey(id)));
        if(!required.every(b=>selected.includes(b)))continue;
        const dedup='sent:'+data.event_key+':'+id;
        if(await env.SUBSCRIBERS.get(dedup)){report.duplicate++;continue;}
        try{
          const out=await telegramSend(env,id,data.text);
          if(out.ok){
            report.sent++;
            await env.SUBSCRIBERS.put(dedup,'1',{expirationTtl:86400});
          }else{
            report.failed++;
            // Remove chats that have explicitly blocked the bot (Telegram 403).
            if(out.status===403)await env.SUBSCRIBERS.delete(chatKey(id));
          }
        }catch{report.failed++;}
      }
      return json(report,report.failed?502:200);
    }
    if(request.method!=='POST'||path!=='/telegram')return new Response('Not found',{status:404});
    if(!env.WEBHOOK_SECRET||!env.TELEGRAM_BOT_TOKEN)return new Response('Worker sin configurar',{status:503});
    const secret=request.headers.get('X-Telegram-Bot-Api-Secret-Token');
    if(!secret||secret!==env.WEBHOOK_SECRET)return new Response('Forbidden',{status:403});
    let data;try{data=await request.json();}catch{return new Response('Bad JSON',{status:400});}
    const cb=data.callback_query;
    if(cb){
      const id=String(cb.message?.chat?.id||'');
      const key=String(cb.data||'');
      if(!id||cb.message?.chat?.type!=='private'||!key.startsWith('books:'))return new Response('OK');
      if(!env.SUBSCRIBERS)return new Response('Worker sin KV',{status:503});
      let selected=readBooks(await env.SUBSCRIBERS.get(pendingKey(id)));
      if(key.startsWith('books:toggle:')){
        const brand=key.slice('books:toggle:'.length);
        if(Object.hasOwn(AVAILABLE_BOOKS,brand)){
          selected=selected.includes(brand)?selected.filter(b=>b!==brand):[...selected,brand];
          await env.SUBSCRIBERS.put(pendingKey(id),JSON.stringify({books:selected}),{expirationTtl:1800});
          await telegramSend(env,id,selectionMessage(),selectionMarkup(selected));
        }
      }else if(key==='books:save'){
        await env.SUBSCRIBERS.put(chatKey(id),JSON.stringify({books:selected,updated_at:new Date().toISOString()}));
        await env.SUBSCRIBERS.delete(pendingKey(id));
        const names=selected.map(b=>AVAILABLE_BOOKS[b]).join(', ')||'ninguna';
        const note=selected.length<2?'No hay arbitraje disponible entre las casas elegidas: puedes cambiarlas con /casas.':'Te avisaremos solamente de oportunidades que utilicen tus casas seleccionadas.';
        await telegramSend(env,id,'✅ Preferencias guardadas: '+names+'.\n'+note);
      }
      await fetch('https://api.telegram.org/bot'+env.TELEGRAM_BOT_TOKEN+'/answerCallbackQuery',{
        method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({callback_query_id:cb.id})
      });
      return new Response('OK');
    }
    const msg=data.message;
    if(!msg||msg.chat?.type!=='private'||msg.chat?.id==null)return new Response('OK');
    const id=String(msg.chat.id);
    const command=norm(String(msg.text||'').trim().split(/[\s\n]/)[0]).split('@')[0];
    let text='',markup;
    if(command==='/start'||command==='/casas'){
      if(!env.SUBSCRIBERS)text='Las preferencias todavía no están disponibles.';
      else{
        const current=readBooks(await env.SUBSCRIBERS.get(chatKey(id)));
        const selected=current.length?current:Object.keys(AVAILABLE_BOOKS);
        await env.SUBSCRIBERS.put(pendingKey(id),JSON.stringify({books:selected}),{expirationTtl:1800});
        text=selectionMessage();markup=selectionMarkup(selected);
      }
    }else if(command==='/stop'){
      if(!env.SUBSCRIBERS)text='El registro todavía no está configurado.';
      else{
        await env.SUBSCRIBERS.delete(chatKey(id));
        await env.SUBSCRIBERS.delete(pendingKey(id));
        text='🔕 Alertas desactivadas. Envía /start para activarlas de nuevo.';
      }
    }else if(command==='/estado'){
      if(!env.SUBSCRIBERS)text='Almacenamiento no configurado.';
      else{
        const saved=await env.SUBSCRIBERS.get(chatKey(id));
        const selected=readBooks(saved);
        text=saved?'✅ Casas guardadas: '+(selected.map(b=>AVAILABLE_BOOKS[b]).join(', ')||'ninguna')+'. Puedes cambiarlas con /casas.':'🔕 No estás suscrito. Envía /start.';
      }
    }else{text=answerText(msg.text);}
    if(!text)return new Response('OK');
    const reply=await telegramSend(env,id,text,markup);
    if(!reply.ok)return new Response('Telegram send failed',{status:502});
    return new Response('OK');
  }
};
