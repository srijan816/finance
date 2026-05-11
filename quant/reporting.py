"""HTML research reports."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence


DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "AMD", "INTC",
    "ORCL", "CRM", "ADBE", "NFLX", "COST", "UNH", "JPM", "V", "MA", "HD",
    "PG", "KO", "PEP", "WMT", "XOM", "CVX", "LLY", "MRK", "ABBV", "JNJ",
]


def generate_growth_report(
    tickers: Sequence[str] | None = None,
    start: str = "2020-01-01",
    end: str = "2025-01-01",
    output_path: str | None = None,
    benchmark: str = "SPY",
    initial_value: float = 10_000.0,
) -> str:
    """Create a standalone animated HTML growth report."""
    from quant.data import fetch_bars
    from quant.research_status import research_grade_status

    selected = [ticker.upper() for ticker in (tickers or DEFAULT_UNIVERSE)]
    all_tickers = selected + ([benchmark] if benchmark and benchmark not in selected else [])
    close_maps = {}
    for ticker in all_tickers:
        bars = fetch_bars(ticker, start, end)
        if bars:
            close_maps[ticker] = {row[0]: float(row[4]) for row in bars}

    if not close_maps:
        raise ValueError("No price data available for report")

    common_dates = sorted(set.intersection(*(set(values) for values in close_maps.values())))
    if len(common_dates) < 2:
        raise ValueError("Not enough overlapping price history for report")

    series = []
    for ticker in all_tickers:
        values = close_maps[ticker]
        first = values[common_dates[0]]
        growth = [round(initial_value * values[date] / first, 2) for date in common_dates]
        total_return = growth[-1] / initial_value - 1
        series.append({
            "ticker": ticker,
            "values": growth,
            "totalReturn": round(total_return * 100, 2),
            "finalValue": growth[-1],
            "isBenchmark": ticker == benchmark,
        })

    series.sort(key=lambda item: item["finalValue"], reverse=True)
    payload = {
        "dates": common_dates,
        "series": series,
        "initialValue": initial_value,
        "start": common_dates[0],
        "end": common_dates[-1],
        "benchmark": benchmark,
        "researchGradeStatus": research_grade_status(
            data_source="yfinance",
            universe_name="current_or_user_supplied_ticker_list",
            validation_method="historical_growth_visualization",
            feature_sources=["price_volume"],
            notes=[
                "This report visualizes historical paths only; it is not a validated recommendation engine.",
            ],
        ),
    }

    if output_path is None:
        output_path = str(Path(__file__).parent.parent / "reports" / "growth_animation.html")
    path = Path(output_path)
    path.parent.mkdir(exist_ok=True)
    path.write_text(_render_growth_html(payload))
    return str(path)


def generate_workflow_report(output_path: str | None = None) -> str:
    """Create a visible HTML report explaining the full research workflow."""
    from quant.workflow import workflow_status

    payload = workflow_status()
    if output_path is None:
        output_path = str(Path(__file__).parent.parent / "reports" / "workflow.html")
    path = Path(output_path)
    path.parent.mkdir(exist_ok=True)
    path.write_text(_render_workflow_html(payload))
    return str(path)


def _render_workflow_html(payload: dict) -> str:
    data = json.dumps(payload, separators=(",", ":"))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Quant Lab Workflow</title>
  <style>
    body {{ margin: 0; font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0d1117; color: #e6edf3; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px; }}
    h1 {{ margin: 0; font-size: 28px; }}
    .summary {{ color: #8b949e; margin: 8px 0 22px; max-width: 900px; }}
    .flow {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; margin-bottom: 24px; }}
    .step, .phase {{ border: 1px solid #30363d; background: #151b23; border-radius: 8px; padding: 12px; }}
    .step b {{ color: #79c0ff; }}
    .phases {{ display: grid; gap: 10px; }}
    .phase {{ display: grid; grid-template-columns: 72px 220px 170px 1fr; gap: 12px; align-items: center; }}
    .num {{ color: #8b949e; font-variant-numeric: tabular-nums; }}
    .name {{ font-weight: 700; }}
    .status {{ display: inline-block; border-radius: 999px; padding: 4px 9px; width: max-content; font-size: 12px; }}
    .implemented {{ background: rgba(63,185,80,.16); color: #7ee787; }}
    .partial {{ background: rgba(242,204,96,.16); color: #f2cc60; }}
    .blocked_by_data, .blocked_by_validation {{ background: rgba(248,81,73,.16); color: #ff7b72; }}
    .detail {{ color: #c9d1d9; }}
    @media (max-width: 760px) {{ main {{ padding: 16px; }} .phase {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
<main>
  <h1 id="title"></h1>
  <div class="summary" id="summary"></div>
  <section class="flow" id="flow"></section>
  <section class="phases" id="phases"></section>
</main>
<script>
const workflow = {data};
document.getElementById("title").textContent = workflow.title;
document.getElementById("summary").textContent = workflow.summary;
document.getElementById("flow").innerHTML = workflow.decision_flow.map((item, idx) => `
  <div class="step"><b>${{idx + 1}}</b><div>${{item}}</div></div>
`).join("");
document.getElementById("phases").innerHTML = workflow.phases.map(phase => `
  <div class="phase">
    <div class="num">Phase ${{phase.phase}}</div>
    <div class="name">${{phase.name}}</div>
    <div><span class="status ${{phase.status}}">${{phase.status.replaceAll("_", " ")}}</span></div>
    <div class="detail">${{phase.detail}}</div>
  </div>
`).join("");
</script>
</body>
</html>
"""


def _render_growth_html(payload: dict) -> str:
    data = json.dumps(payload, separators=(",", ":"))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Quant Lab Growth Animation</title>
	  <style>
    :root {{
      --bg: #0d1117;
      --panel: #151b23;
      --text: #e6edf3;
      --muted: #8b949e;
      --grid: rgba(139, 148, 158, 0.18);
      --accent: #2f81f7;
      --good: #3fb950;
      --line: #30363d;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{ max-width: 1440px; margin: 0 auto; padding: 24px; }}
    header {{
      display: flex;
      gap: 16px;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 18px;
    }}
    h1 {{ margin: 0 0 6px; font-size: 24px; font-weight: 700; }}
	    .sub {{ color: var(--muted); }}
	    .badge {{ display: inline-block; margin-top: 8px; border: 1px solid #f2cc60; color: #f2cc60; border-radius: 6px; padding: 4px 8px; font-size: 12px; }}
	    .stats {{ display: flex; gap: 12px; flex-wrap: wrap; justify-content: flex-end; }}
    .stat {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 12px;
      min-width: 140px;
    }}
    .stat b {{ display: block; font-size: 18px; }}
    .stat span {{ color: var(--muted); font-size: 12px; }}
    .wrap {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 300px;
      gap: 16px;
      align-items: stretch;
    }}
    .chart, aside {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      min-height: 620px;
    }}
    .chart {{ padding: 14px; }}
    canvas {{ width: 100%; height: 540px; display: block; }}
    .controls {{
      display: grid;
      grid-template-columns: auto 1fr auto;
      gap: 10px;
      align-items: center;
      border-top: 1px solid var(--line);
      padding-top: 12px;
    }}
    button {{
      appearance: none;
      border: 1px solid #388bfd;
      background: #1f6feb;
      color: white;
      border-radius: 6px;
      padding: 8px 12px;
      cursor: pointer;
      font-weight: 600;
    }}
    input[type="range"] {{ width: 100%; }}
    aside {{ padding: 14px; overflow: hidden; }}
    aside h2 {{ margin: 0 0 10px; font-size: 15px; }}
    .leaderboard {{ display: grid; gap: 7px; max-height: 555px; overflow: auto; padding-right: 4px; }}
    .row {{
      display: grid;
      grid-template-columns: 64px 1fr 76px;
      gap: 8px;
      align-items: center;
      border-bottom: 1px solid rgba(48,54,61,.7);
      padding: 5px 0;
    }}
    .ticker {{ font-weight: 700; }}
    .bar {{ height: 8px; background: #21262d; border-radius: 999px; overflow: hidden; }}
    .fill {{ height: 100%; background: var(--accent); border-radius: inherit; }}
    .value {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .note {{ margin-top: 12px; color: var(--muted); font-size: 12px; }}
    @media (max-width: 980px) {{
      main {{ padding: 14px; }}
      header {{ display: block; }}
      .stats {{ justify-content: flex-start; margin-top: 12px; }}
      .wrap {{ grid-template-columns: 1fr; }}
      .chart, aside {{ min-height: auto; }}
      canvas {{ height: 420px; }}
    }}
  </style>
</head>
<body>
<main>
  <header>
    <div>
	      <h1>Growth of $10,000 by Stock</h1>
	      <div class="sub">Animated normalized growth from <span id="start"></span> to <span id="end"></span>. Data source: yfinance/Yahoo, retail-grade and possibly delayed.</div>
	      <div class="badge" id="qualityBadge"></div>
	    </div>
    <div class="stats">
      <div class="stat"><b id="dateNow">-</b><span>Current frame</span></div>
      <div class="stat"><b id="leader">-</b><span>Leader</span></div>
      <div class="stat"><b id="leaderValue">-</b><span>Leader value</span></div>
    </div>
  </header>
  <section class="wrap">
    <div class="chart">
      <canvas id="canvas"></canvas>
      <div class="controls">
        <button id="play">Pause</button>
        <input id="slider" type="range" min="0" max="1" value="1" />
        <span id="progress"></span>
      </div>
    </div>
    <aside>
      <h2>Current Ranking</h2>
      <div class="leaderboard" id="leaderboard"></div>
      <div class="note">Lines are normalized to $10,000 at the first common trading date. This is not a recommendation; it is a technical visualization of historical price paths.</div>
    </aside>
  </section>
</main>
<script>
const report = {data};
const colors = ["#f778ba","#79c0ff","#56d364","#ffa657","#d2a8ff","#ff7b72","#a5d6ff","#7ee787","#f2cc60","#c9d1d9","#ffab70","#bc8cff","#39c5cf","#db6d28","#8ddb8c"];
const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");
const slider = document.getElementById("slider");
const playBtn = document.getElementById("play");
const dateNow = document.getElementById("dateNow");
const leader = document.getElementById("leader");
const leaderValue = document.getElementById("leaderValue");
const progress = document.getElementById("progress");
const board = document.getElementById("leaderboard");
document.getElementById("start").textContent = report.start;
document.getElementById("end").textContent = report.end;
const quality = report.researchGradeStatus || {{}};
document.getElementById("qualityBadge").textContent = `[${{quality.level || "DEMO"}}] ${{quality.summary || "Demo-grade visualization."}}`;
slider.max = report.dates.length - 1;
slider.value = 0;
let frame = 0;
let playing = true;
function money(v) {{ return "$" + Math.round(v).toLocaleString(); }}
function resize() {{
  const rect = canvas.getBoundingClientRect();
  const scale = window.devicePixelRatio || 1;
  canvas.width = Math.floor(rect.width * scale);
  canvas.height = Math.floor(rect.height * scale);
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
  draw();
}}
function drawGrid(w, h, pad, minY, maxY) {{
  ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue("--grid");
  ctx.fillStyle = "#8b949e";
  ctx.font = "12px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 5; i++) {{
    const y = pad.t + (h - pad.t - pad.b) * i / 5;
    const val = maxY - (maxY - minY) * i / 5;
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(w - pad.r, y); ctx.stroke();
    ctx.fillText(money(val), 8, y + 4);
  }}
}}
function yScale(value, h, pad, minY, maxY) {{
  return pad.t + (maxY - value) / (maxY - minY) * (h - pad.t - pad.b);
}}
function xScale(i, w, pad) {{
  const n = report.dates.length - 1;
  return pad.l + i / n * (w - pad.l - pad.r);
}}
function draw() {{
  const w = canvas.clientWidth, h = canvas.clientHeight;
  ctx.clearRect(0, 0, w, h);
  const pad = {{l: 74, r: 24, t: 24, b: 34}};
  const visible = report.series.map(s => Math.max(...s.values.slice(0, frame + 1)));
  const maxY = Math.max(12000, ...visible) * 1.04;
  const minY = Math.min(8500, ...report.series.map(s => Math.min(...s.values.slice(0, frame + 1)))) * 0.98;
  drawGrid(w, h, pad, minY, maxY);
  report.series.forEach((s, idx) => {{
    ctx.beginPath();
    ctx.lineWidth = s.isBenchmark ? 3 : 1.6;
    ctx.globalAlpha = s.isBenchmark ? 1 : 0.82;
    ctx.strokeStyle = s.isBenchmark ? "#ffffff" : colors[idx % colors.length];
    for (let i = 0; i <= frame; i++) {{
      const x = xScale(i, w, pad);
      const y = yScale(s.values[i], h, pad, minY, maxY);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }}
    ctx.stroke();
    if (frame > 5 && (idx < 8 || s.isBenchmark)) {{
      const x = xScale(frame, w, pad), y = yScale(s.values[frame], h, pad, minY, maxY);
      ctx.globalAlpha = 1;
      ctx.fillStyle = s.isBenchmark ? "#fff" : colors[idx % colors.length];
      ctx.fillText(s.ticker, Math.min(x + 5, w - 50), y + 4);
    }}
  }});
  ctx.globalAlpha = 1;
  ctx.fillStyle = "#8b949e";
  ctx.fillText(report.dates[0], pad.l, h - 10);
  ctx.fillText(report.dates[frame], Math.max(pad.l, xScale(frame, w, pad) - 36), h - 10);
  updateSide();
}}
function updateSide() {{
  const rows = report.series.map((s, idx) => ({{...s, color: s.isBenchmark ? "#ffffff" : colors[idx % colors.length], current: s.values[frame]}}))
    .sort((a,b) => b.current - a.current);
  const top = rows[0];
  dateNow.textContent = report.dates[frame];
  leader.textContent = top.ticker;
  leaderValue.textContent = money(top.current);
  progress.textContent = `${{frame + 1}} / ${{report.dates.length}}`;
  const max = top.current;
  board.innerHTML = rows.map(r => `
    <div class="row">
      <div class="ticker" style="color:${{r.color}}">${{r.ticker}}</div>
      <div class="bar"><div class="fill" style="width:${{Math.max(2, r.current / max * 100)}}%; background:${{r.color}}"></div></div>
      <div class="value">${{money(r.current)}}</div>
    </div>`).join("");
}}
function tick() {{
  if (playing) {{
    frame = Math.min(report.dates.length - 1, frame + 2);
    slider.value = frame;
    if (frame >= report.dates.length - 1) {{ playing = false; playBtn.textContent = "Replay"; }}
    draw();
  }}
  requestAnimationFrame(tick);
}}
playBtn.onclick = () => {{
  if (frame >= report.dates.length - 1) frame = 0;
  playing = !playing;
  playBtn.textContent = playing ? "Pause" : "Play";
  draw();
}};
slider.oninput = () => {{ frame = Number(slider.value); playing = false; playBtn.textContent = "Play"; draw(); }};
window.addEventListener("resize", resize);
resize();
requestAnimationFrame(tick);
</script>
</body>
</html>
"""
