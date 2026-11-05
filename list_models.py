"""列出你的 key 当前能用的 Gemini 模型（只用 Python 自带模块）。"""
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


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


load_env(os.path.join(HERE, ".env"))
key = os.getenv("GEMINI_API_KEY")
if not key:
    sys.exit("找不到 GEMINI_API_KEY，请先在 .env 文件中填入你的 key。")

req = urllib.request.Request(
    "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
    headers={"x-goog-api-key": key},
)
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
except urllib.error.HTTPError as e:
    sys.exit(f"请求失败（HTTP {e.code}）：\n" + e.read().decode("utf-8", errors="replace"))

print("可用于对话的模型（把名字填到 ask_gemini.py 后面即可）：")
for m in data.get("models", []):
    if "generateContent" in m.get("supportedGenerationMethods", []):
        print(" ", m["name"].replace("models/", ""))
