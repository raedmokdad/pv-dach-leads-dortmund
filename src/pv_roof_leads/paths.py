from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent

DATA = ROOT / "data"
RAW_DORTMUND = DATA / "raw" / "dortmund"
STAGING_DORTMUND = DATA / "staging" / "dortmund"
CURATED_DORTMUND = DATA / "curated" / "dortmund"
EXPORTS_DORTMUND = DATA / "exports" / "dortmund"
PROCESSED_DORTMUND = DATA / "processed" / "dortmund"
FINAL_DORTMUND = DATA / "final" / "dortmund"



def ensure_dirs() -> None:
    """ erstellt alle benoetigten Ordner Falls diese nicht existieren"""
    paths = [
        DATA,
        RAW_DORTMUND,
        STAGING_DORTMUND,
        CURATED_DORTMUND,
        EXPORTS_DORTMUND,
        PROCESSED_DORTMUND,
        FINAL_DORTMUND
    ]
    for p in paths:
        p.mkdir(parents = True, exist_ok = True)
        print(f"✅ {p.relative_to(ROOT)}") 
        
        
if __name__ == "__main__":
    ensure_dirs()
    print("Alle Ordner erstellt/überprüft")