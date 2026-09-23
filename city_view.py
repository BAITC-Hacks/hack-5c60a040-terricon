"""Живая схема районов для экрана: цвет района — его балл, значки — 10 показателей, анимация «было → стало».

Ничего не считает: получает ответы движка (evaluate, baseline) и только рисует их.
"""

import json

ICONS = {"T1": "🚗", "T2": "🚌", "E1": "🌳", "E2": "💨", "S1": "🏫", "S2": "🏥",
         "B1": "🛡️", "B2": "🚦", "C1": "🔧", "C2": "📨"}

# Схема, а не точная карта: правый берег Есиля — север, левый — юг.
SHAPES = {
    "Сарыарка": ("24,18 252,18 244,152 30,162", 136, 86),
    "Байконур": ("262,18 424,18 432,150 254,152", 344, 82),
    "Алматы": ("442,18 584,18 584,342 446,334 440,176", 512, 176),
    "Нура": ("22,206 232,200 226,342 22,342", 124, 272),
    "Есиль": ("246,204 428,198 434,334 240,342", 338, 270),
}


def city_html(result: dict, base: dict, indicators: list[dict]) -> str:
    base_by_name = {district["name"]: district for district in base["districts"]}
    districts = []
    for name, (points, x, y) in SHAPES.items():
        before = base_by_name[name]
        after = next((d for d in result["districts"] if d["name"] == name), None) if result["valid"] else None
        values_after = after["values_after"] if after else before["values"]
        districts.append({
            "name": name, "points": points, "x": x, "y": y,
            "before": before["d"], "after": after["d_after"] if after else before["d"],
            "indicators": [
                {"code": item["code"], "name": item["name"], "icon": ICONS[item["code"]],
                 "before": before["values"][item["code"]], "after": values_after[item["code"]]}
                for item in indicators
            ],
        })
    payload = json.dumps({"districts": districts, "valid": result["valid"],
                          "scoreBefore": base["score"], "scoreAfter": result["score"]}, ensure_ascii=False)
    return TEMPLATE.replace("__DATA__", payload)


TEMPLATE = """
<div id="city" style="font-family: 'Source Sans Pro', 'Segoe UI', sans-serif; color:#0B2545">
  <div style="display:flex;justify-content:space-between;align-items:center;margin:0 0 6px">
    <div id="state" style="font-size:15px;font-weight:600">Показано: город до ваших решений</div>
    <button id="replay" style="border:1px solid #007E99;background:#fff;color:#007E99;border-radius:8px;
      padding:4px 10px;font-size:14px;cursor:pointer">▶ Показать изменения ещё раз</button>
  </div>
  <svg viewBox="0 0 600 360" style="width:100%;height:auto;display:block;background:#F2FAFC;border-radius:12px">
    <path d="M0,184 C110,158 190,212 300,186 S480,150 600,190" stroke="#9ED9E6" stroke-width="18" fill="none"
      stroke-linecap="round"/>
    <text x="300" y="181" text-anchor="middle" font-size="12" fill="#2F7F92" font-style="italic">река Есиль</text>
    <g id="map"></g>
  </svg>
  <div style="font-size:13px;color:#3D5A6C;margin:6px 0 10px">
    Цвет района — его балл из 100: <b style="color:#C62828">красный</b> — отстаёт,
    <b style="color:#B7791F">жёлтый</b> — средне, <b style="color:#2E7D32">зелёный</b> — хорошо.
    Схема районов, не точная карта.<br>
    Значки: 🚗 дороги · 🚌 общественный транспорт · 🌳 зелень · 💨 воздух · 🏫 школы и детсады · 🏥 поликлиники ·
    🛡️ безопасность улиц · 🚦 безопасность на дорогах · 🔧 ЖКХ · 📨 ответы на обращения.
    🔴 — острая проблема (ниже 40), ▲ — стало лучше. Наведите на значок — будет «было → стало».
  </div>
  <div id="cards"></div>
</div>
<script>
const DATA = __DATA__;
const stops = [[45,[229,57,53]],[52,[255,179,0]],[60,[67,160,71]]];
function color(d){
  if(d<=stops[0][0]) return `rgb(${stops[0][1]})`;
  for(let i=1;i<stops.length;i++){ if(d<=stops[i][0]){ const [d0,c0]=stops[i-1],[d1,c1]=stops[i];
    const t=(d-d0)/(d1-d0); return `rgb(${c0.map((c,k)=>Math.round(c+(c1[k]-c)*t))})`; } }
  return `rgb(${stops[stops.length-1][1]})`;
}
const fmt = v => v.toFixed(2).replace('.', ',');
const short = v => (Math.round(v*100)/100).toString().replace('.', ',');
function level(v){ return v<40 ? ['#FDECEA','#8E1C1C'] : (v<=45 ? ['#FFF4D6','#7A5200'] : ['#EEF7F0','#1B5E3A']); }
const map = document.getElementById('map');
const svgNS = 'http://www.w3.org/2000/svg';
const nodes = DATA.districts.map(d => {
  const g = document.createElementNS(svgNS,'g');
  const poly = document.createElementNS(svgNS,'polygon');
  poly.setAttribute('points', d.points); poly.setAttribute('stroke','#FFFFFF'); poly.setAttribute('stroke-width','4');
  poly.setAttribute('stroke-linejoin','round');
  const name = document.createElementNS(svgNS,'text');
  name.setAttribute('x', d.x); name.setAttribute('y', d.y-10); name.setAttribute('text-anchor','middle');
  name.setAttribute('font-size','17'); name.setAttribute('font-weight','700'); name.setAttribute('fill','#0B2545');
  name.textContent = d.name;
  const val = document.createElementNS(svgNS,'text');
  val.setAttribute('x', d.x); val.setAttribute('y', d.y+18); val.setAttribute('text-anchor','middle');
  val.setAttribute('font-size','24'); val.setAttribute('font-weight','700'); val.setAttribute('fill','#0B2545');
  const crit = document.createElementNS(svgNS,'text');
  crit.setAttribute('x', d.x); crit.setAttribute('y', d.y+40); crit.setAttribute('text-anchor','middle');
  crit.setAttribute('font-size','13'); crit.setAttribute('fill','#8E1C1C'); crit.setAttribute('font-weight','600');
  g.append(poly,name,val,crit); map.append(g);
  return {d, poly, val, crit};
});
const cards = document.getElementById('cards');
const order = [...DATA.districts].sort((a,b)=>a.after-b.after);
cards.innerHTML = order.map(d => {
  const delta = d.after-d.before;
  const chips = d.indicators.map(i => {
    const [bg,fg] = level(i.after); const up = i.after>i.before;
    const tip = `${i.name}: ${short(i.before)}${i.after!==i.before ? ' → '+short(i.after) : ''}`;
    return `<span title="${tip}" style="display:inline-flex;align-items:center;gap:2px;background:${bg};color:${fg};
      border:1px solid ${up?'#2E7D32':'transparent'};border-radius:8px;padding:1px 5px;margin:2px;font-size:13px">
      ${i.icon}${i.after<40?'🔴':''}<b>${short(i.after)}</b>${up?'<span style="color:#2E7D32">▲</span>':''}</span>`;
  }).join('');
  return `<div style="background:#fff;border:1px solid #D5E9EE;border-radius:10px;padding:6px 10px;margin-bottom:6px">
    <div style="display:flex;justify-content:space-between;font-size:15px"><b>${d.name}</b>
    <span>${fmt(d.before)} → <b>${fmt(d.after)}</b> <span style="color:${delta>0?'#1B7F4B':'#3D5A6C'};font-weight:700">
    ${delta>=0?'+':'−'}${fmt(Math.abs(delta))}</span></span></div><div>${chips}</div></div>`;
}).join('');
function draw(t){
  nodes.forEach(({d,poly,val,crit}) => {
    const v = d.before + (d.after-d.before)*t;
    poly.setAttribute('fill', color(v)); poly.setAttribute('fill-opacity','0.88');
    val.textContent = fmt(v);
    const n = d.indicators.filter(i => (t<1 ? i.before : i.after) < 40).length;
    crit.textContent = n ? `острых проблем: ${n}` : '';
  });
}
function play(){
  const state = document.getElementById('state');
  draw(0); state.textContent = 'Показано: город до ваших решений';
  if(!DATA.valid){ state.textContent = 'Показан город сейчас — сценарий пока не проходит правила'; return; }
  const start = performance.now() + 700, dur = 1800;
  function step(now){
    const t = Math.min(Math.max((now-start)/dur,0),1); const e = t<.5 ? 2*t*t : 1-Math.pow(-2*t+2,2)/2;
    draw(e);
    if(t<1) requestAnimationFrame(step);
    else { const ds = DATA.scoreAfter-DATA.scoreBefore;
      state.textContent = `Показано: после ваших решений — индекс города ${fmt(DATA.scoreBefore)} → ${fmt(DATA.scoreAfter)} (${ds>=0?'+':'−'}${fmt(Math.abs(ds))})`; }
  }
  requestAnimationFrame(step);
}
document.getElementById('replay').onclick = play;
play();
</script>
"""
