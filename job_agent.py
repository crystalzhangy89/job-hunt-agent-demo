"""求职 Agent：自动对比简历和 jobs 文件夹里的所有岗位，更新匹配度排名。

用法：
  python job_agent.py              扫描一次（只处理新增/修改的岗位；简历改了就全部重评）
  python job_agent.py --watch      每 10 分钟自动扫描一次（Ctrl+C 停止）
  python job_agent.py --watch 30   每 30 分钟扫描一次
  python job_agent.py --force      强制全部重新评分

输出：results.csv（可用 Excel 打开）和 report.html（按匹配度排序的网页报告）
只用 Python 自带模块，不需要 pip 安装任何东西。
"""
import base64
import csv
import glob
import hashlib
import html
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
JOBS_DIR = os.path.join(HERE, "jobs")
STATE_FILE = os.path.join(HERE, "state.json")
CSV_OUT = os.path.join(HERE, "results.csv")
HTML_OUT = os.path.join(HERE, "report.html")

MODELS = ["gemini-3.6-flash", "gemini-3.8-flash"]  # 主模型 + 备用模型
RETRIES_PER_MODEL = 3
PAUSE_BETWEEN_JOBS = 2  # 秒，避免请求太快


def load_env(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def call_gemini(payload):
    """调用 Gemini；遇到 503/429 等临时错误自动重试，并自动换备用模型。返回文字。"""
    key = os.getenv("GEMINI_API_KEY")
    last = ""
    for model in MODELS:
        for attempt in range(1, RETRIES_PER_MODEL + 1):
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "x-goog-api-key": key},
            )
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.load(resp)
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code}: " + e.read().decode("utf-8", errors="replace")[:300]
                if e.code in (429, 500, 502, 503, 504):
                    wait = 5 * attempt
                    print(f"    {model} 暂时繁忙（HTTP {e.code}），{wait} 秒后重试 ({attempt}/{RETRIES_PER_MODEL})")
                    time.sleep(wait)
                    continue
                print(f"    {model} 不可用（HTTP {e.code}），换下一个模型")
                break
            except (urllib.error.URLError, TimeoutError) as e:
                last = str(e)
                print(f"    网络问题：{e}，5 秒后重试")
                time.sleep(5)
    raise RuntimeError(last or "所有模型都失败了")


def parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def score_job(resume_b64, jd_text):
    prompt = f"""你是严谨的求职顾问。根据附带的简历（PDF）和下面的岗位描述评估匹配度。
只依据简历中真实存在的内容，不要编造经历。只输出 JSON，不要任何其他文字，格式如下：
{{"title": "岗位名称（取自岗位描述，没有则写 未知）",
 "company": "公司名（没有则写 未知）",
 "score": 0到100的整数,
 "summary": "一句话理由（中文）",
 "strengths": ["最多3条，引用简历中的具体内容（中文）"],
 "gaps": ["最多3条，岗位要求但简历里没体现的（中文）"]}}

岗位描述：
{jd_text[:15000]}
"""
    payload = {
        "contents": [{"parts": [
            {"inline_data": {"mime_type": "application/pdf", "data": resume_b64}},
            {"text": prompt},
        ]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }
    r = parse_json(call_gemini(payload))
    r["score"] = max(0, min(100, int(r.get("score", 0))))
    r["strengths"] = [str(x) for x in r.get("strengths", [])][:3]
    r["gaps"] = [str(x) for x in r.get("gaps", [])][:3]
    return r


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"resume_hash": "", "jobs": {}}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def write_reports(jobs):
    rows = sorted(jobs.items(), key=lambda kv: kv[1].get("score", 0), reverse=True)
    with open(CSV_OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["匹配度", "岗位", "公司", "一句话理由", "优势", "差距", "文件", "更新时间"])
        for name, j in rows:
            w.writerow([j["score"], j.get("title", ""), j.get("company", ""), j.get("summary", ""),
                        "；".join(j.get("strengths", [])), "；".join(j.get("gaps", [])), name, j.get("updated", "")])

    def esc(s):
        return html.escape(str(s))

    body = []
    for name, j in rows:
        s = j["score"]
        color = "#2e7d32" if s >= 75 else "#f9a825" if s >= 50 else "#c62828"
        li = lambda items: "".join(f"<li>{esc(x)}</li>" for x in items)
        body.append(
            f"<tr><td><div class='score' style='background:{color}'>{s}</div></td>"
            f"<td><b>{esc(j.get('title',''))}</b><br><span class='muted'>{esc(j.get('company',''))} · {esc(name)}</span>"
            f"<p>{esc(j.get('summary',''))}</p></td>"
            f"<td><ul>{li(j.get('strengths', []))}</ul></td><td><ul>{li(j.get('gaps', []))}</ul></td>"
            f"<td class='muted'>{esc(j.get('updated',''))}</td></tr>"
        )
    page = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<title>岗位匹配报告</title><style>
body{{font-family:system-ui,"Microsoft YaHei",sans-serif;margin:24px;color:#222}}
table{{border-collapse:collapse;width:100%}}th,td{{border-bottom:1px solid #ddd;padding:10px;vertical-align:top;text-align:left}}
.score{{color:#fff;font-weight:700;border-radius:8px;padding:8px 12px;text-align:center;min-width:44px}}
.muted{{color:#777;font-size:12px}}ul{{margin:0;padding-left:18px}}p{{margin:6px 0 0}}
</style></head><body><h1>岗位匹配报告</h1>
<p class="muted">更新于 {time.strftime('%Y-%m-%d %H:%M')} · 共 {len(rows)} 个岗位 · 按匹配度从高到低</p>
<table><tr><th>匹配度</th><th>岗位</th><th>优势</th><th>差距</th><th>更新时间</th></tr>
{''.join(body)}</table></body></html>"""
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(page)


def run_once(force=False):
    if not os.getenv("GEMINI_API_KEY"):
        sys.exit("找不到 GEMINI_API_KEY，请先在 .env 文件中填入你的 key。")
    pdfs = sorted(glob.glob(os.path.join(HERE, "*.pdf")))
    if not pdfs:
        sys.exit("文件夹里没有找到 PDF 简历。")
    os.makedirs(JOBS_DIR, exist_ok=True)

    with open(pdfs[0], "rb") as f:
        resume_bytes = f.read()
    resume_hash = sha(resume_bytes)
    resume_b64 = base64.b64encode(resume_bytes).decode("ascii")

    state = load_state()
    if force or state.get("resume_hash") != resume_hash:
        if state.get("jobs"):
            print("简历有变化（或使用了 --force），所有岗位将重新评分。")
        state = {"resume_hash": resume_hash, "jobs": {}}
    jobs = state["jobs"]

    files = [p for p in sorted(glob.glob(os.path.join(JOBS_DIR, "*")))
             if p.lower().endswith((".txt", ".md")) and not os.path.basename(p).startswith("_")]
    names = {os.path.basename(p) for p in files}
    for gone in [n for n in jobs if n not in names]:
        del jobs[gone]  # 文件被删除了，就从排名里移除

    todo = []
    for p in files:
        with open(p, "rb") as f:
            raw = f.read()
        if jobs.get(os.path.basename(p), {}).get("hash") != sha(raw):
            todo.append((p, raw))

    print(f"[{time.strftime('%H:%M:%S')}] 简历：{os.path.basename(pdfs[0])} | 岗位 {len(files)} 个，需要评分 {len(todo)} 个")
    if not files:
        print("jobs 文件夹里还没有岗位。把岗位描述存成 .txt 文件放进去就行。")

    for i, (p, raw) in enumerate(todo, 1):
        name = os.path.basename(p)
        print(f"  ({i}/{len(todo)}) 评分中：{name}")
        text = raw.decode("utf-8-sig", errors="replace").strip()
        if len(text) < 50:
            print("    内容太短，已跳过。")
            continue
        try:
            r = score_job(resume_b64, text)
        except Exception as e:  # 单个岗位失败不影响其他的
            print(f"    失败：{e}")
            continue
        r.update(hash=sha(raw), updated=time.strftime("%Y-%m-%d %H:%M"))
        jobs[name] = r
        print(f"    匹配度 {r['score']}：{r.get('title','')} @ {r.get('company','')}")
        save_state(state)
        time.sleep(PAUSE_BETWEEN_JOBS)

    save_state(state)
    write_reports(jobs)
    if jobs:
        print("\n当前排名：")
        for n, j in sorted(jobs.items(), key=lambda kv: kv[1]["score"], reverse=True):
            print(f"  {j['score']:>3}  {j.get('title','')} @ {j.get('company','')}  ({n})")
        print("\n完整报告：report.html（浏览器打开）和 results.csv（Excel 打开）")


def main():
    load_env(os.path.join(HERE, ".env"))
    args = sys.argv[1:]
    force = "--force" in args
    if "--watch" in args:
        i = args.index("--watch")
        minutes = int(args[i + 1]) if i + 1 < len(args) and args[i + 1].isdigit() else 10
        print(f"监控模式：每 {minutes} 分钟扫描一次，按 Ctrl+C 停止。")
        while True:
            run_once(force)
            force = False
            print(f"\n下次扫描在 {minutes} 分钟后...\n")
            time.sleep(minutes * 60)
    else:
        run_once(force)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已停止。")
