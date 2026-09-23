"""Живая схема районов для экрана: цвет района — его балл, значки — 10 показателей, анимация «было → стало».

Ничего не считает: получает ответы движка (evaluate, baseline) и только рисует их.
"""

import json

ICONS = {"T1": "🚗", "T2": "🚌", "E1": "🌳", "E2": "💨", "S1": "🏫", "S2": "🏥",
         "B1": "🛡️", "B2": "🚦", "C1": "🔧", "C2": "📨"}
SHORT = {"T1": "Дороги", "T2": "Транс&shy;порт", "E1": "Зелень", "E2": "Воздух", "S1": "Школы",
         "S2": "Поли&shy;клиники", "B1": "Улицы", "B2": "Без ДТП", "C1": "ЖКХ", "C2": "Обра&shy;щения"}

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
                {"code": item["code"], "name": item["name"], "icon": ICONS[item["code"]], "short": SHORT[item["code"]],
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
  <div style="display:flex;flex-wrap:wrap;gap:6px 14px;font-size:13px;color:#3D5A6C;margin:8px 0 4px">
    <span><b>Цвет района на схеме</b> — его балл из 100:</span>
    <span><span style="display:inline-block;width:12px;height:12px;background:#E53935;border-radius:3px"></span> отстаёт</span>
    <span><span style="display:inline-block;width:12px;height:12px;background:#FFB300;border-radius:3px"></span> средне</span>
    <span><span style="display:inline-block;width:12px;height:12px;background:#43A047;border-radius:3px"></span> хорошо</span>
    <span style="color:#6B8595">· схема, не точная карта</span>
  </div>
  <div style="font-size:15px;font-weight:600;margin:12px 0 2px">Показатели районов: сейчас после ваших решений</div>
  <div style="display:flex;flex-wrap:wrap;gap:6px 14px;font-size:13px;color:#3D5A6C;margin:0 0 6px">
    <span>Все от 0 до 100, больше — лучше.</span>
    <span><span style="display:inline-block;width:12px;height:12px;background:#FDECEA;border:1px solid #E8A09A;border-radius:3px"></span> острая проблема — ниже 40</span>
    <span><span style="display:inline-block;width:12px;height:12px;background:#FFF4D6;border:1px solid #E6C66A;border-radius:3px"></span> на грани — 40–45</span>
    <span><b style="color:#1B7F4B">▲+10</b> — стало лучше</span>
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
const cols = DATA.districts[0].indicators;
const head = `<tr><th style="text-align:left;padding:2px 4px;font-size:12px;color:#3D5A6C">Район<br>балл: было → стало</th>` +
  cols.map(c => `<th title="${c.name}" style="padding:2px 1px"><div style="font-size:17px">${c.icon}</div>
    <div style="font-size:10.5px;color:#3D5A6C;font-weight:600;line-height:1.1;hyphens:manual;overflow-wrap:anywhere">${c.short}</div></th>`).join('') + `</tr>`;
const rows = order.map(d => {
  const delta = d.after-d.before;
  const cells = d.indicators.map(i => {
    const up = i.after-i.before; const [bg,fg] = level(i.after);
    const plain = i.after>45;
    return `<td title="${i.name}: ${short(i.before)}${up ? ' → '+short(i.after) : ''}" style="background:${plain?'#FFFFFF':bg};
      color:${plain?'#0B2545':fg};border:${up?'2px solid #2E7D32':'1px solid #E3EEF1'};border-radius:6px;text-align:center;
      padding:3px 1px;font-weight:${up?700:500};font-size:13px;line-height:1.15">${short(i.after)}${up ?
      `<div style="font-size:10.5px;color:#1B7F4B;font-weight:700;white-space:nowrap">▲+${short(up)}</div>` : ''}</td>`;
  }).join('');
  return `<tr><th style="text-align:left;padding:2px 4px;white-space:nowrap;font-size:14px">${d.name}<br>
    <span style="font-size:12px;font-weight:400">${fmt(d.before)} → <b>${fmt(d.after)}</b>
    <b style="color:${delta>0?'#1B7F4B':'#3D5A6C'}">${delta>=0?'+':'−'}${fmt(Math.abs(delta))}</b></span></th>${cells}</tr>`;
}).join('');
cards.innerHTML = `<table style="width:100%;border-collapse:separate;border-spacing:3px;table-layout:fixed">
  <colgroup><col style="width:22%">${cols.map(() => '<col>').join('')}</colgroup>${head}${rows}</table>`;
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
