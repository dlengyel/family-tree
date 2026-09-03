import json, pathlib

data = json.load(open("data.json", encoding="utf-8"))
tpl = pathlib.Path("template.html").read_text(encoding="utf-8")
out = tpl.replace("/*__DATA__*/", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
pathlib.Path("index.html").write_text(out, encoding="utf-8")
print("index.html", len(out), "bytes")
