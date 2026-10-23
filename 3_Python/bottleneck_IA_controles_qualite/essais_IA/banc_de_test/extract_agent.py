"""Extrait la réponse finale (texte brut) d'un transcript JSONL de sous-agent."""
import json, sys
src, dst = sys.argv[1], sys.argv[2]
last = None
for line in open(src, encoding="utf-8"):
    try: o = json.loads(line)
    except Exception: continue
    msg = o.get("message") or {}
    if o.get("type") == "assistant" or msg.get("role") == "assistant":
        c = msg.get("content")
        if isinstance(c, list):
            t = "".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
        else:
            t = c or ""
        if t.strip(): last = t
open(dst, "w", encoding="utf-8").write(last or "")
print(len(last or ""), "caractères ;", "&gt;" in (last or ""), "entités HTML ;", (last or "").count("```"), "clôtures de code")
