import sys
sys.path.insert(0, "/app")

from db import get_supabase
from services.benner_classifier import classify

sb = get_supabase()

resp = sb.table("benner_erros").select("id,mensagem,tipo_erro").is_("rpa_categoria", "null").execute()
rows = resp.data or []
print(f"Sem categoria: {len(rows)}")

BATCH = 100
updated = 0
for i in range(0, len(rows), BATCH):
    batch = rows[i:i+BATCH]
    for r in batch:
        cat = classify(r.get("mensagem"), r.get("tipo_erro"))
        sb.table("benner_erros").update({"rpa_categoria": cat}).eq("id", r["id"]).execute()
        updated += 1
    print(f"  {updated}/{len(rows)}...")

print(f"Classificados: {updated}")
