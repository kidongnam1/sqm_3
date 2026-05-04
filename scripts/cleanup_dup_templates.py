import urllib.request, urllib.error, json

BASE = "http://127.0.0.1:8765"

def api(method, path, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": e.read().decode()}
    except Exception as e:
        return {"ok": False, "error": str(e)}

res = api("GET", "/api/inbound/templates")
if not res.get("ok"):
    print("조회 실패:", res)
    exit(1)

templates = res.get("templates", [])
print(f"전체 템플릿: {len(templates)}개")

# 이름 앞에 이모지가 붙은 중복 제거
to_delete = [t for t in templates if t.get("template_name","").startswith("🚢")]
print(f"삭제 대상: {len(to_delete)}개")

for t in to_delete:
    tid = t["template_id"]
    name = t["template_name"]
    r = api("DELETE", f"/api/inbound/templates/{tid}")
    if r.get("ok"):
        print(f"  ✅ 삭제: {name}")
    else:
        print(f"  ❌ 실패: {name} — {r.get('error','?')}")

# 최종 확인
final = api("GET", "/api/inbound/templates")
rows = final.get("templates", [])
print(f"\n최종 DB 템플릿 {len(rows)}개:")
for r in rows:
    print(f"  🚢 {r['carrier_id']:8s} | {r['bag_weight_kg']}kg | {r['template_name']}")
