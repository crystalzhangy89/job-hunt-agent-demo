"""用法：python gemini.py [模型名] [问题]
例如：python gemini.py gemini-3.6-flash 你好
不写模型名就用默认模型。"""
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MODEL = "gemini-3.6-flash"


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

args = sys.argv[1:]
model = args[0] if args else DEFAULT_MODEL
prompt = " ".join(args[1:]) if len(args) > 1 else "你好，请用一句话回复，说明连接成功。"

req = urllib.request.Request(
    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
    data=json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8"),
    headers={"Content-Type": "application/json", "x-goog-api-key": key},
)
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    print(f"[{model}]")
    print(data["candidates"][0]["content"]["parts"][0]["text"])
except urllib.error.HTTPError as e:
    print(f"请求失败（HTTP {e.code}）：")
    print(e.read().decode("utf-8", errors="replace"))
