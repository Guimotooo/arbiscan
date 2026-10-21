import test from 'node:test';
import assert from 'node:assert/strict';
import {answerText} from './arbiscan.mjs';
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