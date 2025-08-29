import json

SRC = "dados_backup.json"
DST = "dados_backup.cleaned.json"

def main() -> None:
    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    seen = set()
    clean = []

    for obj in data:
        if obj.get("model") == "ai_marketing_agent.marketingdata":
            flds = obj.get("fields", {})
            key = (
                flds.get("data"),
                (flds.get("campaign_name") or "").strip().lower(),
                (flds.get("platform") or "").strip().lower(),
                flds.get("empresa"),
            )
            if key in seen:
                continue
            seen.add(key)
        clean.append(obj)

    with open(DST, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)

    print("Gerado:", DST, "| Registros:", len(clean))

if __name__ == "__main__":
    main()


