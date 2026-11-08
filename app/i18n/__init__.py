"""New safety/status strings; the existing Tkinter UI remains Serbian Latin."""

STRINGS = {
    "sr_Latn": {
        "previous_page": "Prethodna",
        "scan_review_only": "Rezultati nepotpunog skeniranja služe za pregled. Ponovite uspešno skeniranje pre premeštanja.",
        "next_page": "Sledeća",
        "page_count": "Prikazano do {0} od {1} rezultata",
        "index_warning": "Privremeni ili nepotpun indeks: {0}",
        "scan_progress": "Analizirano {0} fotografija...",
        "operation_error": "Operacija je zaustavljena. Dnevnik je sačuvan; ponovite oporavak pre nove operacije.",
        "history_error": "Istorija je nedostupna. Skeniranje je dozvoljeno; premeštanje i vraćanje su blokirani.",
        "xmp_warning": "Pronađeni su XMP fajlovi. Ostaju na mestu; proverite vezu sa fotografijom.",
        "legacy_warning": "Stara istorija nema proverljiv raniji sadržaj. Potvrdite vraćanje sadašnjih bajtova pojedinačno.",
        "incomplete": "NEPOTPUNO skeniranje",
        "cancelled": "Skeniranje je zaustavljeno; nema kandidata za operacije.",
    },
    "en": {
        "previous_page": "Previous",
        "scan_review_only": "Incomplete scan results are for review. Complete a successful scan before moving files.",
        "next_page": "Next",
        "page_count": "Showing through {0} of {1} results",
        "index_warning": "Temporary or incomplete index: {0}",
        "scan_progress": "Inspected {0} photographs...",
        "operation_error": "Operation stopped. The journal is retained; run recovery before another operation.",
        "history_error": "History unavailable. Scanning is allowed; moves and restores are blocked.",
        "xmp_warning": "XMP sidecars found. They stay in place; review their relationship to the photograph.",
        "legacy_warning": "Legacy history cannot verify earlier content. Confirm restoring the current bytes individually.",
        "incomplete": "INCOMPLETE scan",
        "cancelled": "Scan cancelled; no operation candidates.",
    },
}


def tr(key: str, *args, language: str = "sr_Latn") -> str:
    return STRINGS.get(language, STRINGS["sr_Latn"]).get(key, STRINGS["en"].get(key, key)).format(*args)
