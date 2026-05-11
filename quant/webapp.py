"""Local browser UI for Quant Lab workflows."""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlparse

from quant.workflow import workflow_status


PROJECT_ROOT = Path(__file__).resolve().parent.parent
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


@dataclass(frozen=True)
class Action:
    action_id: str
    title: str
    category: str
    description: str
    command_builder: Callable[[dict], list[str]]
    fields: list[dict]
    explanation: list[str]


def run_web_app(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    """Run the local browser UI."""
    server = ThreadingHTTPServer((host, port), QuantLabHandler)
    url = f"http://{host}:{server.server_port}"
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    print(f"Quant Lab web UI running at {url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Quant Lab web UI.")
    finally:
        server.server_close()


def actions_manifest() -> list[dict]:
    return [
        {
            "id": action.action_id,
            "title": action.title,
            "category": action.category,
            "description": action.description,
            "fields": action.fields,
            "explanation": action.explanation,
            "commandPreview": _display_command(action.command_builder({})),
        }
        for action in ACTIONS
    ]


def build_command(action_id: str, params: dict) -> list[str]:
    for action in ACTIONS:
        if action.action_id == action_id:
            return action.command_builder(params)
    raise ValueError(f"Unknown action: {action_id}")


def create_job(action_id: str, params: dict) -> dict:
    command = build_command(action_id, params)
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "action": action_id,
        "params": params,
        "command": command,
        "displayCommand": _display_command(command),
        "status": "queued",
        "createdAt": _now(),
        "startedAt": None,
        "finishedAt": None,
        "events": [{"time": _now(), "message": "Queued job."}],
        "output": "",
        "parsedJson": None,
        "returnCode": None,
    }
    with JOBS_LOCK:
        JOBS[job_id] = job
    thread = threading.Thread(target=_run_job, args=(job_id,), daemon=True)
    thread.start()
    return job


def get_job(job_id: str) -> dict | None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        return None if job is None else json.loads(json.dumps(job))


class QuantLabHandler(BaseHTTPRequestHandler):
    server_version = "QuantLabWeb/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._html(INDEX_HTML)
            return
        if parsed.path == "/api/actions":
            self._json({"actions": actions_manifest()})
            return
        if parsed.path == "/api/workflow":
            self._json({"workflow": workflow_status(), "blockedPhaseGuide": blocked_phase_guide()})
            return
        if parsed.path.startswith("/api/jobs/"):
            job_id = parsed.path.rsplit("/", 1)[-1]
            job = get_job(job_id)
            if job is None:
                self._json({"error": "job not found"}, HTTPStatus.NOT_FOUND)
                return
            self._json(job)
            return
        if parsed.path.startswith("/reports/"):
            self._serve_report(parsed.path)
            return
        self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/run":
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self._read_json()
            job = create_job(str(payload.get("action", "")), dict(payload.get("params") or {}))
            self._json(job, HTTPStatus.ACCEPTED)
        except Exception as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def log_message(self, fmt: str, *args) -> None:  # quieter terminal
        return

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def _json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _html(self, html: str) -> None:
        data = html.encode("utf-8")
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_report(self, request_path: str) -> None:
        relative = unquote(request_path.removeprefix("/reports/"))
        if ".." in Path(relative).parts:
            self._json({"error": "invalid path"}, HTTPStatus.BAD_REQUEST)
            return
        path = PROJECT_ROOT / "reports" / relative
        if not path.exists() or not path.is_file():
            self._json({"error": "report not found"}, HTTPStatus.NOT_FOUND)
            return
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _run_job(job_id: str) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id]
        job["status"] = "running"
        job["startedAt"] = _now()
        job["events"].append({"time": _now(), "message": f"Starting: {job['displayCommand']}"})
    command = get_job(job_id)["command"]
    output_parts: list[str] = []
    try:
        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            output_parts.append(line)
            with JOBS_LOCK:
                job = JOBS[job_id]
                job["output"] = "".join(output_parts)
                job["events"].append({"time": _now(), "message": line.rstrip()})
        return_code = process.wait()
        output = "".join(output_parts)
        with JOBS_LOCK:
            job = JOBS[job_id]
            job["returnCode"] = return_code
            job["finishedAt"] = _now()
            job["output"] = output
            job["parsedJson"] = _try_parse_json(output)
            job["status"] = "succeeded" if return_code == 0 else "failed"
            job["events"].append({"time": _now(), "message": f"Finished with exit code {return_code}."})
    except Exception as exc:
        with JOBS_LOCK:
            job = JOBS[job_id]
            job["status"] = "failed"
            job["finishedAt"] = _now()
            job["events"].append({"time": _now(), "message": f"Failed: {exc}"})


def _try_parse_json(output: str) -> Any:
    text = output.strip()
    if not text or text[0] not in "[{":
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _display_command(command: list[str]) -> str:
    if command[:3] == [sys.executable, "-m", "quant.cli"]:
        return "quant " + " ".join(command[3:])
    return " ".join(command[2:] if command[:2] == [sys.executable, "-m"] else command)


def _base_command() -> list[str]:
    return [sys.executable, "-m", "quant.cli"]


def _text(params: dict, name: str, default: str) -> str:
    value = str(params.get(name, default)).strip()
    return value or default


def _choice(params: dict, name: str, default: str, allowed: set[str]) -> str:
    value = _text(params, name, default)
    return value if value in allowed else default


def _int(params: dict, name: str, default: int, min_value: int = 1, max_value: int = 10_000) -> int:
    try:
        value = int(params.get(name, default))
    except (TypeError, ValueError):
        value = default
    return max(min_value, min(max_value, value))


def _float(params: dict, name: str, default: float, min_value: float = 0.0, max_value: float = 1_000_000.0) -> float:
    try:
        value = float(params.get(name, default))
    except (TypeError, ValueError):
        value = default
    return max(min_value, min(max_value, value))


def _tickers(params: dict, default: str) -> str:
    raw = _text(params, "tickers", default)
    values = [item.strip().upper() for item in raw.split(",") if item.strip()]
    return ",".join(values) or default


def blocked_phase_guide() -> list[dict]:
    return [
        {
            "phase": "Phase 1 - Data Integrity",
            "status": "blocked by external data",
            "whatYouNeedToDo": [
                "Choose a vendor/source for point-in-time constituents and delisted securities: Norgate, CRSP/WRDS, Sharadar/Nasdaq Data Link, Polygon, or another provider.",
                "Export a security master with permanent IDs, symbol history, listing dates, delisting dates, delisting returns, sectors, and corporate-action adjustment mode.",
                "Place point-in-time universe CSV files under data/universes/ using symbol,start_date,end_date,name,sector,source.",
                "Run paper-sim or future V2 scans with that universe, then confirm the status block moves beyond current-list warnings.",
            ],
        },
        {
            "phase": "Phase 4 - Model/Gate Decoupling",
            "status": "partially complete",
            "whatYouNeedToDo": [
                "Use the app in paper/shadow mode for at least three months and store each recommendation run.",
                "Compare pure model ranking vs legacy overlay ranking on realized 1d/5d/21d/63d active returns.",
                "Retire the overlay only if pure-model post-cost IC and drawdown behavior are no worse.",
            ],
        },
        {
            "phase": "Phase 8 - Orthogonal Data",
            "status": "partially complete",
            "whatYouNeedToDo": [
                "Add point-in-time fundamentals or analyst revisions from a licensed source before adding many more model features.",
                "For historical news, use article publication timestamps and lexicon/statistical sentiment unless the model training cutoff is safely before the article date.",
                "Do not use LLM historical sentiment as alpha unless leakage is controlled.",
            ],
        },
        {
            "phase": "Phase 10/11 - Monitoring and Broker Gating",
            "status": "requires time and evidence",
            "whatYouNeedToDo": [
                "Run paper/shadow recommendations repeatedly and keep the generated run manifests.",
                "Wait for realized labels before judging IC; incomplete forward windows should not be counted.",
                "Only after live/paper metrics match validation should IBKR move from manual approval to a small live sleeve.",
            ],
        },
    ]


def _run_process(_: dict) -> list[str]:
    return _base_command() + ["process"]


def _run_workflow(_: dict) -> list[str]:
    return _base_command() + ["workflow-report"]


def _run_llm(_: dict) -> list[str]:
    return _base_command() + ["llm-check"]


def _run_norgate_status(_: dict) -> list[str]:
    return _base_command() + ["norgate", "status", "--json-output"]


def _run_norgate_import(params: dict) -> list[str]:
    command = _base_command() + [
        "norgate",
        "import-ascii",
        "--path", _text(params, "path", "data/norgate/ascii"),
        "--json-output",
    ]
    market = _text(params, "market", "")
    if market:
        command += ["--market", market.upper()]
    return command


def _run_norgate_metadata(params: dict) -> list[str]:
    return _base_command() + [
        "norgate",
        "import-metadata",
        "--path", _text(params, "path", "data/norgate/export"),
        "--json-output",
    ]


def _run_norgate_bridge(_: dict) -> list[str]:
    return _base_command() + ["norgate", "write-windows-bridge"]


def _run_recommend(params: dict) -> list[str]:
    return _base_command() + [
        "recommend-v2",
        "--tickers", _tickers(params, "SPY,QQQ,AAPL,MSFT,NVDA"),
        "--from-date", _text(params, "start", "2018-01-01"),
        "--to-date", _text(params, "end", "2026-05-09"),
        "--benchmark", _text(params, "benchmark", "SPY").upper(),
        "--horizon", str(_int(params, "horizon", 63, 5, 252)),
        "--top-n", str(_int(params, "topN", 10, 1, 50)),
        "--json-output",
    ]


def _run_allocate(params: dict) -> list[str]:
    return _base_command() + [
        "allocate-budget",
        "--capital", str(_float(params, "capital", 20_000.0, 1, 100_000_000)),
        "--tickers", _tickers(params, "SPY,QQQ,AAPL,MSFT,NVDA,GOOGL,AMZN,META,AVGO,AMD,TXN,AMAT,CAT,CSCO,XLK"),
        "--engine", _choice(params, "engine", "v2", {"v1", "v2", "both"}),
        "--from-date", _text(params, "start", "2018-01-01"),
        "--to-date", _text(params, "end", "2026-05-09"),
        "--benchmark", _text(params, "benchmark", "SPY").upper(),
        "--top-n", str(_int(params, "topN", 12, 1, 50)),
        "--json-output",
    ]


def _run_record_trade(params: dict) -> list[str]:
    return _base_command() + [
        "record-trade",
        "--ticker", _text(params, "ticker", "AAPL").upper(),
        "--side", _choice(params, "side", "BUY", {"BUY", "SELL", "buy", "sell"}).upper(),
        "--quantity", str(_float(params, "quantity", 1.0, 0.000001, 1_000_000)),
        "--price", str(_float(params, "price", 100.0, 0.000001, 1_000_000)),
        "--trade-date", _text(params, "tradeDate", "2026-05-09"),
        "--fees", str(_float(params, "fees", 1.0, 0, 100_000)),
        "--notes", _text(params, "notes", ""),
        "--json-output",
    ]


def _run_research_prompt(params: dict) -> list[str]:
    return _base_command() + ["research-prompt", "--as-of", _text(params, "asOf", "2026-05-09")]


def _run_validate(params: dict) -> list[str]:
    return _base_command() + [
        "validate",
        "--ticker", _text(params, "ticker", "AAPL").upper(),
        "--from-date", _text(params, "start", "2020-01-01"),
        "--to-date", _text(params, "end", "2025-01-01"),
        "--strategy", _choice(params, "strategy", "momentum", {"sma_cross", "momentum", "buy_hold", "agent"}),
        "--train-bars", str(_int(params, "trainBars", 252, 20, 2000)),
        "--test-bars", str(_int(params, "testBars", 63, 5, 500)),
        "--json-output",
    ]


def _run_backtest(params: dict) -> list[str]:
    return _base_command() + [
        "backtest",
        "--tickers", _tickers(params, "AAPL,MSFT,NVDA"),
        "--from-date", _text(params, "start", "2020-01-01"),
        "--to-date", _text(params, "end", "2025-01-01"),
        "--strategy", _choice(params, "strategy", "momentum", {"sma_cross", "momentum", "buy_hold", "agent"}),
        "--commission-bps", str(_float(params, "commissionBps", 0.0, 0, 1000)),
        "--slippage-bps", str(_float(params, "slippageBps", 2.0, 0, 1000)),
        "--json-output",
    ]


def _run_optimize(params: dict) -> list[str]:
    return _base_command() + [
        "optimize",
        "--tickers", _tickers(params, "AAPL,MSFT,NVDA,SPY"),
        "--from-date", _text(params, "start", "2020-01-01"),
        "--to-date", _text(params, "end", "2025-01-01"),
        "--method", _choice(params, "method", "min_variance", {"equal_weight", "inverse_vol", "risk_parity", "min_variance", "max_sharpe"}),
        "--json-output",
    ]


def _run_paper_sim(params: dict) -> list[str]:
    command = _base_command() + [
        "paper-sim",
        "--from-date", _text(params, "start", "2020-01-01"),
        "--to-date", _text(params, "end", "2025-01-01"),
        "--strategy", _choice(params, "strategy", "momentum", {"sma_cross", "momentum", "buy_hold", "agent"}),
        "--capital", str(_float(params, "capital", 10_000.0, 0, 10_000_000)),
        "--monthly-contribution", str(_float(params, "monthlyContribution", 0.0, 0, 1_000_000)),
        "--commission-bps", str(_float(params, "commissionBps", 0.0, 0, 1000)),
        "--slippage-bps", str(_float(params, "slippageBps", 2.0, 0, 1000)),
        "--json-output",
    ]
    universe = str(params.get("universe", "")).strip()
    if universe:
        command += ["--universe", universe]
    else:
        command += ["--tickers", _tickers(params, "AAPL,MSFT,NVDA,GOOGL,TSLA")]
    return command


def _run_decision_audit(params: dict) -> list[str]:
    return _base_command() + [
        "decision-audit",
        "--ticker", _text(params, "ticker", "AAPL").upper(),
        "--from-date", _text(params, "start", "2018-01-01"),
        "--to-date", _text(params, "end", "2025-01-01"),
        "--strategy", _choice(params, "strategy", "momentum", {"sma_cross", "momentum", "buy_hold", "agent"}),
        "--horizon", str(_int(params, "horizon", 21, 1, 252)),
        "--step", str(_int(params, "step", 21, 1, 252)),
        "--json-output",
    ]


def _run_growth(params: dict) -> list[str]:
    return _base_command() + [
        "growth-report",
        "--tickers", _tickers(params, "AAPL,MSFT,NVDA,GOOGL,AMZN"),
        "--from-date", _text(params, "start", "2020-01-01"),
        "--to-date", _text(params, "end", "2025-01-01"),
    ]


def _field(name: str, label: str, value: str, field_type: str = "text", help_text: str = "") -> dict:
    return {"name": name, "label": label, "value": value, "type": field_type, "help": help_text}


ACTIONS = [
    Action("norgateStatus", "Norgate Status", "Data", "Show imported Norgate cache status and current limitations.", _run_norgate_status, [], [
        "Shows whether Quant Lab has imported Norgate ASCII data locally.",
        "Keeps the Mac ASCII limitation visible: daily OHLCV only until Windows API/export metadata is available.",
    ]),
    Action("norgateImport", "Import Norgate ASCII", "Data", "Import exported Norgate CSV/TXT files into the local Quant Lab cache.", _run_norgate_import, [
        _field("path", "Export folder", "data/norgate/ascii"),
        _field("market", "Market label", ""),
    ], [
        "Put Norgate exported CSV/TXT files in the folder, then run this.",
        "After import, set QUANT_DATA_SOURCE=norgate before running engines from the shell.",
    ]),
    Action("norgateMetadata", "Import Norgate Metadata", "Data", "Import security-master and constituent metadata from the Windows bridge output.", _run_norgate_metadata, [
        _field("path", "Bridge export folder", "data/norgate/export"),
    ], [
        "Use after running the Windows bridge with databases/watchlists/index arguments.",
        "This moves Quant Lab closer to PIT/security-master discipline when the subscription exposes those fields.",
    ]),
    Action("norgateBridge", "Write Windows Bridge", "Data", "Generate the Windows-side script for exporting from Norgate's full Python API.", _run_norgate_bridge, [], [
        "Use this on a Windows VM where Norgate Data Updater is installed and logged in.",
        "This is the path toward richer Norgate access beyond Mac ASCII price files.",
    ]),
    Action("process", "Explain The System", "Understand", "Print the full end-to-end process before running market workflows.", _run_process, [], [
        "Shows how data, signals, portfolio logic, execution, and caveats fit together.",
        "Use this first if you want the interactive README version of the app.",
    ]),
    Action("workflow", "Build Workflow UI Report", "Understand", "Generate the workflow phase map as an HTML report.", _run_workflow, [], [
        "Writes reports/workflow.html.",
        "Shows which phases are implemented, partial, or blocked.",
    ]),
    Action("recommend", "Run V2 Recommendations", "Research", "Scan a ticker universe with the calibrated technical V2 engine.", _run_recommend, [
        _field("tickers", "Tickers", "SPY,QQQ,AAPL,MSFT,NVDA"),
        _field("start", "From", "2018-01-01"),
        _field("end", "To", "2026-05-09"),
        _field("benchmark", "Benchmark", "SPY"),
        _field("horizon", "Forecast Horizon", "63", "number"),
        _field("topN", "Top N", "10", "number"),
    ], [
        "Fetches OHLCV data, builds V2 features, trains ridge, runs purged validation, and returns ranked candidates.",
        "Status remains DEMO unless PIT/delisted data is configured.",
    ]),
    Action("allocate", "Allocate Budget", "Portfolio", "Enter a budget and produce manual IBKR target orders with full limitations visible.", _run_allocate, [
        _field("capital", "Budget USD", "20000", "number"),
        _field("tickers", "Tickers", "SPY,QQQ,AAPL,MSFT,NVDA,GOOGL,AMZN,META,AVGO,AMD,TXN,AMAT,CAT,CSCO,XLK"),
        _field("engine", "Engine", "v2"),
        _field("start", "From", "2018-01-01"),
        _field("end", "To", "2026-05-09"),
        _field("benchmark", "Benchmark", "SPY"),
        _field("topN", "Top N", "12", "number"),
    ], [
        "Runs V2 by default because it has calibrated active-return estimates; V1 can be displayed as a baseline.",
        "Shows target notional, estimated shares, entry, stop, target, cash reserve, manual IBKR setup steps, and expectation scenarios.",
        "Compares the plan with recorded manual fills after you log real trades.",
    ]),
    Action("recordTrade", "Record Manual Trade", "Portfolio", "Log a real IBKR or paper fill so the app can compare intended vs actual exposure.", _run_record_trade, [
        _field("ticker", "Ticker", "AAPL"),
        _field("side", "Side", "BUY"),
        _field("quantity", "Quantity", "1", "number"),
        _field("price", "Fill Price", "100", "number"),
        _field("tradeDate", "Trade Date", "2026-05-09"),
        _field("fees", "Fees USD", "1", "number"),
        _field("notes", "Notes", ""),
    ], [
        "Use this after manually copying Quant Lab targets into IBKR.",
        "The journal is local SQLite and is used for paper-vs-real shadow comparison.",
    ]),
    Action("researchPrompt", "Manual Research Prompt", "Research", "Print the exact leakage-aware prompt for adding orthogonal news/fundamental context.", _run_research_prompt, [
        _field("asOf", "As-of date", "2026-05-09"),
    ], [
        "Use this when doing manual research outside the app.",
        "It forces source timestamps, fact/interpretation separation, confidence, and leakage controls.",
    ]),
    Action("validate", "Validate A Strategy", "Research", "Run rolling validation for one ticker/strategy.", _run_validate, [
        _field("ticker", "Ticker", "AAPL"),
        _field("start", "From", "2020-01-01"),
        _field("end", "To", "2025-01-01"),
        _field("strategy", "Strategy", "momentum"),
        _field("trainBars", "Train Bars", "252", "number"),
        _field("testBars", "Test Bars", "63", "number"),
    ], [
        "Runs rolling out-of-sample windows and reports the research status block.",
        "Use this for quick sanity checks, not final model promotion.",
    ]),
    Action("backtest", "Backtest Tickers", "Research", "Run lookahead-lagged backtests over a ticker list.", _run_backtest, [
        _field("tickers", "Tickers", "AAPL,MSFT,NVDA"),
        _field("start", "From", "2020-01-01"),
        _field("end", "To", "2025-01-01"),
        _field("strategy", "Strategy", "momentum"),
        _field("commissionBps", "Commission bps", "0", "number"),
        _field("slippageBps", "Slippage bps", "2", "number"),
    ], [
        "Signals are lagged one bar to avoid direct lookahead.",
        "Universe quality still determines whether the result is credible.",
    ]),
    Action("optimize", "Optimize Portfolio", "Portfolio", "Construct a static long-only research portfolio.", _run_optimize, [
        _field("tickers", "Tickers", "AAPL,MSFT,NVDA,SPY"),
        _field("start", "From", "2020-01-01"),
        _field("end", "To", "2025-01-01"),
        _field("method", "Method", "min_variance"),
    ], [
        "Uses covariance/risk methods in the standalone optimizer.",
        "This is separate from production V2 allocation unless explicitly integrated.",
    ]),
    Action("paperSim", "Paper Simulation", "Portfolio", "Simulate paper money with prior-information-only rebalances.", _run_paper_sim, [
        _field("tickers", "Tickers", "AAPL,MSFT,NVDA,GOOGL,TSLA"),
        _field("universe", "Universe name", ""),
        _field("start", "From", "2020-01-01"),
        _field("end", "To", "2025-01-01"),
        _field("strategy", "Strategy", "momentum"),
        _field("capital", "Initial Capital", "10000", "number"),
        _field("monthlyContribution", "Monthly Contribution", "0", "number"),
        _field("commissionBps", "Commission bps", "0", "number"),
        _field("slippageBps", "Slippage bps", "2", "number"),
    ], [
        "Uses only prior price history at each rebalance.",
        "A current ticker list can still create survivorship bias; use a PIT universe when available.",
    ]),
    Action("decisionAudit", "Decision Audit", "Diagnostics", "Replay BUY/HOLD decisions and score forward outcomes.", _run_decision_audit, [
        _field("ticker", "Ticker", "AAPL"),
        _field("start", "From", "2018-01-01"),
        _field("end", "To", "2025-01-01"),
        _field("strategy", "Strategy", "momentum"),
        _field("horizon", "Horizon", "21", "number"),
        _field("step", "Step", "21", "number"),
    ], [
        "Audits whether past decisions were directionally correct under prior-information rules.",
        "Useful for calibration and small-edge skepticism.",
    ]),
    Action("growth", "Growth Animation", "Reports", "Generate the animated growth chart report.", _run_growth, [
        _field("tickers", "Tickers", "AAPL,MSFT,NVDA,GOOGL,AMZN"),
        _field("start", "From", "2020-01-01"),
        _field("end", "To", "2025-01-01"),
    ], [
        "Creates reports/growth_animation.html.",
        "This is historical visualization, not a recommendation.",
    ]),
    Action("llm", "Check MiniMax", "System", "Verify that the configured MiniMax key can complete a tiny request.", _run_llm, [], [
        "Fails closed if the key is missing or rejected.",
        "The app does not fabricate LLM decisions when the provider is unavailable.",
    ]),
]


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Quant Lab</title>
  <style>
    :root {
      --bg: #0f1216;
      --panel: #171c22;
      --panel2: #1e242c;
      --line: #303844;
      --text: #e8edf2;
      --muted: #94a0ad;
      --accent: #58a6ff;
      --good: #63c174;
      --warn: #e7bd5b;
      --bad: #f07470;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    header { border-bottom: 1px solid var(--line); background: #11161c; }
    .top { max-width: 1500px; margin: 0 auto; padding: 18px 22px; display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
    h1 { margin: 0; font-size: 24px; }
    .sub { color: var(--muted); margin-top: 5px; max-width: 880px; }
    .shell { max-width: 1500px; margin: 0 auto; padding: 18px 22px 32px; display: grid; grid-template-columns: 330px minmax(0, 1fr); gap: 16px; align-items: start; }
    .result-panel { grid-column: 1 / -1; }
    .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; }
    .panel h2 { font-size: 15px; margin: 0; padding: 13px 14px; border-bottom: 1px solid var(--line); }
    .inside { padding: 13px 14px; }
    .phase { padding: 10px 0; border-bottom: 1px solid rgba(48,56,68,.7); cursor: pointer; }
    .phase:last-child { border-bottom: 0; }
    .phase-title { display: flex; justify-content: space-between; gap: 8px; font-weight: 700; }
    .phase-detail { color: var(--muted); margin-top: 4px; font-size: 12px; }
    .badge { display: inline-flex; align-items: center; border-radius: 999px; padding: 3px 8px; font-size: 11px; white-space: nowrap; }
    .implemented { background: rgba(99,193,116,.14); color: var(--good); }
    .partial { background: rgba(231,189,91,.14); color: var(--warn); }
    .blocked_by_data, .blocked_by_validation { background: rgba(240,116,112,.14); color: var(--bad); }
    .actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 12px; }
    .tabs { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }
    .tab { border: 1px solid var(--line); background: var(--panel); color: var(--text); }
    .tab.active { border-color: #2f81f7; background: #18365f; }
    .action { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 13px; }
    .action-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; margin-bottom: 8px; }
    .action-title { font-weight: 800; font-size: 15px; }
    .category { color: var(--accent); font-size: 12px; }
    .desc { color: var(--muted); margin-bottom: 10px; }
    .fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
    label { display: grid; gap: 4px; color: var(--muted); font-size: 12px; }
    input { width: 100%; border: 1px solid var(--line); border-radius: 6px; background: #0d1117; color: var(--text); padding: 8px; }
    button { border: 1px solid #2f81f7; background: #1f6feb; color: white; border-radius: 6px; padding: 8px 11px; cursor: pointer; font-weight: 700; }
    button.secondary { background: transparent; color: var(--accent); }
    .run-row { display: flex; justify-content: space-between; gap: 8px; align-items: center; margin-top: 11px; }
    code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    .cmd { color: var(--muted); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .run-layout { display: grid; grid-template-columns: 420px minmax(0, 1fr); gap: 14px; }
    .progress { min-height: 180px; max-height: 360px; overflow: auto; display: grid; gap: 7px; }
    .event { border-bottom: 1px solid rgba(48,56,68,.65); padding-bottom: 7px; color: var(--muted); }
    .event b { color: var(--text); }
    pre { white-space: pre-wrap; overflow: auto; background: #0d1117; border: 1px solid var(--line); border-radius: 8px; padding: 12px; max-height: 460px; }
    .json-grid { display: grid; gap: 8px; }
    .metric { border: 1px solid var(--line); border-radius: 8px; padding: 9px; background: var(--panel2); }
    .metric b { display: block; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th, td { border-bottom: 1px solid var(--line); padding: 7px 6px; text-align: left; vertical-align: top; }
    th { color: var(--muted); font-weight: 700; }
    .allocation-table { overflow: auto; border: 1px solid var(--line); border-radius: 8px; margin-top: 8px; }
    .scenario-chart { width: 100%; height: 150px; border: 1px solid var(--line); border-radius: 8px; margin-top: 8px; background: #0d1117; }
    .limitations { color: var(--warn); }
    .help-list { color: var(--muted); padding-left: 18px; }
    .links { display: flex; gap: 8px; flex-wrap: wrap; }
    @media (max-width: 1180px) { .shell, .run-layout { grid-template-columns: 1fr; } .fields { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <header>
    <div class="top">
      <div>
        <h1>Quant Lab</h1>
        <div class="sub">A local research cockpit for the same Quant Lab CLI. Pick a workflow, inspect what it will do, run it, and watch the exact command, progress, status, and output.</div>
      </div>
      <div class="links">
        <button class="secondary" onclick="runQuick('process')">Explain System</button>
        <button class="secondary" onclick="runQuick('workflow')">Build Workflow Report</button>
      </div>
    </div>
  </header>
  <main class="shell">
    <section class="panel">
      <h2>Workflow Phases</h2>
      <div class="inside" id="phases"></div>
    </section>
    <section>
      <div class="tabs" id="categoryTabs"></div>
      <div class="actions" id="actions"></div>
    </section>
    <aside class="panel result-panel">
      <h2>Run Transparency</h2>
      <div class="inside">
        <div class="run-layout">
          <div>
            <div id="selectedHelp" class="desc">Select a phase or run an action. This panel shows what is happening and why.</div>
            <div class="progress" id="events"></div>
          </div>
          <div>
            <h2 style="border:0;padding-left:0">Result</h2>
            <div id="summary"></div>
            <pre id="output">No run yet.</pre>
          </div>
        </div>
      </div>
    </aside>
  </main>
<script>
let actions = [];
let workflow = null;
let blockedGuides = {};
let selectedCategory = 'Portfolio';
let activeJob = null;
let pollTimer = null;

async function init() {
  const [a, w] = await Promise.all([fetch('/api/actions').then(r => r.json()), fetch('/api/workflow').then(r => r.json())]);
  actions = a.actions;
  workflow = w.workflow;
  renderPhases(w.blockedPhaseGuide);
  renderCategoryTabs();
  renderActions();
}

function categories() {
  const order = ['Portfolio', 'Data', 'Research', 'Diagnostics', 'Understand', 'Reports', 'System'];
  const found = [...new Set(actions.map(action => action.category))];
  return order.filter(item => found.includes(item)).concat(found.filter(item => !order.includes(item)));
}

function renderCategoryTabs() {
  const cats = categories();
  if (!cats.includes(selectedCategory)) selectedCategory = cats[0] || '';
  document.getElementById('categoryTabs').innerHTML = cats.map(cat => `
    <button class="tab ${cat === selectedCategory ? 'active' : ''}" onclick="selectCategory('${cat}')">${cat}</button>
  `).join('');
}

function selectCategory(category) {
  selectedCategory = category;
  renderCategoryTabs();
  renderActions();
}

function renderPhases(blockedGuide) {
  blockedGuides = Object.fromEntries(blockedGuide.map(item => [item.phase.split(' - ')[0], item]));
  document.getElementById('phases').innerHTML = workflow.phases.map(p => `
    <div class="phase" onclick='showPhase(${JSON.stringify(p).replaceAll("'", "&#39;")})'>
      <div class="phase-title"><span>Phase ${p.phase}: ${p.name}</span><span class="badge ${p.status}">${p.status.replaceAll('_',' ')}</span></div>
      <div class="phase-detail">${p.detail}</div>
    </div>
  `).join('');
}

function showPhase(phase) {
  const guide = blockedGuides[`Phase ${phase.phase}`];
  const needed = guide ? `<br><br><b>What you need to do</b><ul class="help-list">${guide.whatYouNeedToDo.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : '<br><br>This control is implemented in code.';
  document.getElementById('selectedHelp').innerHTML = `<b>Phase ${phase.phase}: ${phase.name}</b><br>${phase.detail}${needed}`;
}

function renderActions() {
  const visible = actions.filter(action => action.category === selectedCategory);
  document.getElementById('actions').innerHTML = visible.map(action => `
    <article class="action">
      <div class="action-head">
        <div><div class="action-title">${action.title}</div><div class="category">${action.category}</div></div>
        <button onclick="runAction('${action.id}')">Run</button>
      </div>
      <div class="desc">${action.description}</div>
      <ul class="help-list">${action.explanation.map(item => `<li>${item}</li>`).join('')}</ul>
      <div class="fields">${action.fields.map(field => `
        <label>${field.label}<input id="${action.id}-${field.name}" type="${field.type}" value="${field.value}" title="${field.help || ''}"></label>
      `).join('')}</div>
      <div class="run-row"><div class="cmd">${action.commandPreview}</div><button class="secondary" onclick="explainAction('${action.id}')">Explain</button></div>
    </article>
  `).join('');
}

function explainAction(id) {
  const action = actions.find(a => a.id === id);
  document.getElementById('selectedHelp').innerHTML = `<b>${action.title}</b><br>${action.description}<ul class="help-list">${action.explanation.map(item => `<li>${item}</li>`).join('')}</ul><code>${action.commandPreview}</code>`;
}

function paramsFor(action) {
  const params = {};
  action.fields.forEach(field => {
    const el = document.getElementById(`${action.id}-${field.name}`);
    params[field.name] = el ? el.value : field.value;
  });
  return params;
}

async function runQuick(id) { await runAction(id); }

async function runAction(id) {
  const action = actions.find(a => a.id === id);
  explainAction(id);
  document.getElementById('events').innerHTML = '<div class="event"><b>Now</b><br>Submitting job...</div>';
  document.getElementById('output').textContent = 'Waiting for output...';
  document.getElementById('summary').innerHTML = '';
  const response = await fetch('/api/run', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action: id, params: paramsFor(action)})});
  const job = await response.json();
  if (job.error) {
    document.getElementById('output').textContent = job.error;
    return;
  }
  activeJob = job.id;
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(pollJob, 700);
  pollJob();
}

async function pollJob() {
  if (!activeJob) return;
  const job = await fetch(`/api/jobs/${activeJob}`).then(r => r.json());
  document.getElementById('events').innerHTML = job.events.slice(-30).map(e => `<div class="event"><b>${e.time}</b><br>${escapeHtml(e.message)}</div>`).join('');
  document.getElementById('output').textContent = job.output || 'Running...';
  renderSummary(job);
  if (job.status === 'succeeded' || job.status === 'failed') clearInterval(pollTimer);
}

function renderSummary(job) {
  const parsed = job.parsedJson;
  if (!parsed) {
    document.getElementById('summary').innerHTML = `<div class="metric"><b>Status</b>${job.status}<br><span class="desc">${escapeHtml(job.displayCommand || '')}</span></div>`;
    return;
  }
  const status = Array.isArray(parsed) ? parsed.find(x => x && x.research_grade_status)?.research_grade_status : parsed.research_grade_status;
  if (parsed.plans) {
    renderAllocationSummary(job, parsed, status);
    return;
  }
  const metrics = [];
  if (status) metrics.push(['Research status', `[${status.level}] ${status.summary}`]);
  if (parsed.validation) metrics.push(['Validation', `folds=${parsed.validation.n_folds || 0}, avg IC=${parsed.validation.avg_rank_correlation ?? parsed.validation.avg_rank_ic ?? 'n/a'}`]);
  if (parsed.summary) metrics.push(['Summary', JSON.stringify(parsed.summary)]);
  if (parsed.final_equity) metrics.push(['Final equity', `$${Number(parsed.final_equity).toLocaleString()}`]);
  document.getElementById('summary').innerHTML = `<div class="json-grid">${metrics.map(([k,v]) => `<div class="metric"><b>${k}</b>${escapeHtml(String(v))}</div>`).join('')}</div>`;
}

function renderAllocationSummary(job, parsed, status) {
  const primary = parsed.plans.find(p => p.engine === parsed.primary_engine) || parsed.plans[0];
  const allocation = primary.allocation || {allocations: [], cash: 0};
  const rows = allocation.allocations || [];
  const limitations = status?.limitations || [];
  const setup = parsed.ibkr_manual_setup || {steps: [], orders: []};
  const tracking = parsed.manual_tracking || {comparisons: []};
  document.getElementById('summary').innerHTML = `
    <div class="json-grid">
      <div class="metric"><b>Research status</b>${escapeHtml(status ? `[${status.level}] ${status.summary}` : 'No status')}<br><span class="limitations">${limitations.map(escapeHtml).join(', ')}</span></div>
      <div class="metric"><b>Budget plan</b>primary=${escapeHtml(parsed.primary_engine)} | budget=$${Number(parsed.capital).toLocaleString()} | invest=$${Number(allocation.deployable_capital || 0).toLocaleString()} | cash=$${Number(allocation.cash || 0).toLocaleString()}</div>
      <div class="metric"><b>Manual IBKR setup</b><ol class="help-list">${setup.steps.map(step => `<li>${escapeHtml(step)}</li>`).join('')}</ol></div>
      <div class="metric"><b>Expectation path</b>${escapeHtml(primary.expectation_path?.basis || 'No expectation path available.')}${expectationChart(primary.expectation_path)}</div>
      <div class="metric"><b>Target allocation</b><div class="allocation-table">${allocationTable(rows)}</div></div>
      <div class="metric"><b>Recorded vs target</b><div class="allocation-table">${trackingTable(tracking.comparisons || [])}</div></div>
    </div>`;
}

function allocationTable(rows) {
  if (!rows.length) return '<div class="desc">No allocations passed the current gates.</div>';
  return `<table><thead><tr><th>Ticker</th><th>Notional</th><th>Shares</th><th>Entry</th><th>Stop</th><th>Target</th><th>Why</th></tr></thead><tbody>${rows.map(row => `
    <tr><td>${escapeHtml(row.ticker)}</td><td>$${Number(row.allocation || 0).toLocaleString()}</td><td>${escapeHtml(row.shares_at_entry ?? '')}</td><td>$${escapeHtml(row.entry ?? '')}</td><td>${escapeHtml(row.stop ?? '')}</td><td>${escapeHtml(row.target ?? '')}</td><td>${escapeHtml(row.why || '')}</td></tr>
  `).join('')}</tbody></table>`;
}

function trackingTable(rows) {
  if (!rows.length) return '<div class="desc">No matching recorded fills yet. Use Record Manual Trade after entering IBKR orders.</div>';
  return `<table><thead><tr><th>Ticker</th><th>Target</th><th>Recorded Qty</th><th>Gap</th><th>Status</th></tr></thead><tbody>${rows.map(row => `
    <tr><td>${escapeHtml(row.ticker)}</td><td>$${Number(row.target_notional || 0).toLocaleString()}</td><td>${escapeHtml(row.recorded_quantity || 0)}</td><td>$${Number(row.gap_notional || 0).toLocaleString()}</td><td>${escapeHtml(row.status)}</td></tr>
  `).join('')}</tbody></table>`;
}

function expectationChart(path) {
  if (!path || !path.series || !path.series.length) return '';
  const values = path.series.flatMap(s => s.values.map(v => v.value));
  const min = Math.min(...values), max = Math.max(...values);
  const width = 380, height = 130, pad = 18;
  const colors = {adverse:'#f07470', conservative:'#e7bd5b', base:'#58a6ff', upside:'#63c174'};
  const lines = path.series.map(s => {
    const points = s.values.map((v, i) => {
      const x = pad + i * ((width - pad * 2) / (s.values.length - 1));
      const y = height - pad - ((v.value - min) / Math.max(max - min, 1)) * (height - pad * 2);
      return `${x},${y}`;
    }).join(' ');
    return `<polyline points="${points}" fill="none" stroke="${colors[s.scenario] || '#94a0ad'}" stroke-width="2"><title>${escapeHtml(s.scenario)}</title></polyline>`;
  }).join('');
  const labels = path.series.map(s => `<span style="color:${colors[s.scenario] || '#94a0ad'}">${escapeHtml(s.scenario)}</span>`).join(' ');
  return `<svg class="scenario-chart" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">${lines}</svg><div class="desc">${labels}</div>`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[ch]));
}

init();
</script>
</body>
</html>"""
