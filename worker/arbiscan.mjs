/* Telegram webhook for ArbiiScan. All user-submitted prices are unverified. */
const BRAND = new Map(Object.entries({bet365:'Bet365', sportium:'Sportium',winamax:'Winamax',betfair:'Betfair',bwin:'bwin',codere:'Codere',luckia:'Luckia','william hill':'William Hill',betway:'Betway',retabet:'RETAbet',sportybet:'SportyBet'}));
const norm=s=>String(s).trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
const number=s=>{const n=Number(String(s).trim().replace(',','.'));if(!Number.isFinite(n))throw Error('Número o cuota no válidos');return n;};
const help='ArbiiScan: envía /plantilla para copiar el formato. Las cuotas enviadas NO se verifican. No se realizan apuestas.';
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
export default {
  async fetch(request,env){
    const path=new URL(request.url).pathname;
    if(request.method==='GET'&&path==='/health')return new Response('ArbiiScan webhook disponible');
    if(request.method!=='POST'||path!=='/telegram')return new Response('Not found',{status:404});
    if(!env.WEBHOOK_SECRET||!env.TELEGRAM_BOT_TOKEN||!env.TELEGRAM_CHAT_ID)return new Response('Worker sin configurar',{status:503});
    const secret=request.headers.get('X-Telegram-Bot-Api-Secret-Token');
    if(!secret||secret!==env.WEBHOOK_SECRET)return new Response('Forbidden',{status:403});
    let data;try{data=await request.json();}catch{return new Response('Bad JSON',{status:400});}
    const msg=data.message;
    if(!msg||msg.chat?.type!=='private'||String(msg.chat.id)!==String(env.TELEGRAM_CHAT_ID))return new Response('OK');
    const text=answerText(msg.text);if(!text)return new Response('OK');
    const reply=await fetch('https://api.telegram.org/bot'+env.TELEGRAM_BOT_TOKEN+'/sendMessage',{
      method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({chat_id:msg.chat.id,text:text.slice(0,4000)})
    });
    if(!reply.ok)return new Response('Telegram send failed',{status:502});
    return new Response('OK');
  }
};