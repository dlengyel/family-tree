# -*- coding: utf-8 -*-
"""Read the MyHeritage GEDCOM export and emit just what the two visuals need.

Deliberately excludes all personal contact data (EMAIL / PHON / ADDR / physical
description). Keeps names, years and places only.
"""
import re, json, sys, collections, unicodedata

# The .ged itself is never committed, so pass its path in:
#   python3 extract.py ~/Desktop/<export>.ged
GED = sys.argv[1] if len(sys.argv) > 1 else "family-tree.ged"
ROOT = "I2"  # David Lengyel — the person the direct line is traced from

# ---------------------------------------------------------------- GEDCOM read

def parse(path):
    indi, fam = {}, {}
    cur = curtype = ev = None
    for raw in open(path, encoding="utf-8", errors="replace"):
        line = raw.rstrip("\r\n")
        m = re.match(r"^(\d+) (.*)$", line)
        if not m:
            continue
        lvl, rest = int(m.group(1)), m.group(2)
        if lvl == 0:
            mm = re.match(r"^@(\S+)@ (\w+)", rest)
            cur = mm.group(1) if mm else None
            curtype = mm.group(2) if mm else None
            ev = None
            if curtype == "INDI":
                indi[cur] = {"id": cur, "name": "", "sex": "", "famc": [], "fams": [],
                             "birt": None, "deat": None, "bplac": "", "dplac": "",
                             "bplac_raw": "", "dplac_raw": ""}
            elif curtype == "FAM":
                fam[cur] = {"husb": None, "wife": None, "chil": [], "marr": None, "mplac": ""}
            continue
        if curtype == "INDI" and cur in indi:
            r = indi[cur]
            if lvl == 1:
                tag = rest.split(" ")[0]
                ev = tag
                if tag == "NAME" and not r["name"]:
                    r["name"] = rest[5:].replace("/", "").strip()
                elif tag == "SEX":
                    r["sex"] = rest[4:].strip()
                elif tag == "FAMC":
                    r["famc"].append(rest.split("@")[1])
                elif tag == "FAMS":
                    r["fams"].append(rest.split("@")[1])
            elif lvl == 2 and ev in ("BIRT", "DEAT", "BURI", "CHR"):
                key = {"BIRT": "b", "CHR": "b", "DEAT": "d", "BURI": "d"}[ev]
                if rest.startswith("DATE"):
                    y = re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", rest)
                    slot = "birt" if key == "b" else "deat"
                    if y and not r[slot]:
                        r[slot] = int(y.group(1))
                elif rest.startswith("PLAC"):
                    slot = "bplac_raw" if key == "b" else "dplac_raw"
                    if not r[slot]:
                        r[slot] = rest[5:].strip()
        elif curtype == "FAM" and cur in fam:
            if lvl == 1:
                t = rest.split(" ")[0]
                ev = t
                if t in ("HUSB", "WIFE"):
                    fam[cur][t.lower()] = rest.split("@")[1]
                elif t == "CHIL":
                    fam[cur]["chil"].append(rest.split("@")[1])
            elif lvl == 2 and ev == "MARR":
                if rest.startswith("DATE"):
                    y = re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", rest)
                    if y and not fam[cur]["marr"]:
                        fam[cur]["marr"] = int(y.group(1))
                elif rest.startswith("PLAC") and not fam[cur]["mplac"]:
                    fam[cur]["mplac"] = rest[5:].strip()
    return indi, fam


# --------------------------------------------------------------- place merging
# Each entry: canonical czech/historic label, modern local label, lat, lon,
# region, whether the coordinate is approximate, and the spelling keys that
# identify it. Keys are matched against an accent-stripped, letters-only fold.
# Order matters: the first match wins, so narrower entries come first.

GAZETTEER = [
 # label,                     modern,                          lat,     lon,  region, approx, keys
 ("Malý Friedrichův Tábor", "Tabor Mały, Poland",            51.290,  17.780, "SIL", 1, ["kleinfriedrichs","malyfriedrichuvtabor","tabormaly"]),
 ("Velký Friedrichův Tábor","Tabor Wielki, Poland",          51.302,  17.752, "SIL", 1, ["grosfriedrichs","grossfriedrichs","grofriedrichs","taborwielki","velkyfriedrichuvtabor","velkyfriedrichuvtabor","friedrichuvtabor"]),
 ("Friedrichův Hradec",     "Poland",                        51.310,  17.740, "SIL", 1, ["friedrichuvhradec"]),
 ("Velemín",                "Velemín, Czechia",              50.545,  13.955, "BOH", 0, ["velemin"]),
 ("Litoměřice",             "Litoměřice, Czechia",           50.534,  14.132, "BOH", 0, ["litomerice","litomierzyce"]),
 ("Mirotín",                "Myrotyn, Rivne obl., Ukraine",  50.450,  26.135, "VOL", 1, ["mirotin","mirotyn","myrotyn"]),
 ("Michalovka",             "Mykhailivka, Rivne obl., Ukraine",50.470, 26.190, "VOL", 1, ["michalovka","mykhailivka"]),
 ("Zelów",                  "Zelów, Łódź, Poland",           51.466,  19.221, "SIL", 0, ["zelow","zelov"]),
 ("Kleszczów",              "Kleszczów, Poland",             51.207,  19.298, "SIL", 0, ["kleszczow"]),
 ("Lovosice",               "Lovosice, Czechia",             50.515,  14.050, "BOH", 0, ["lovosice"]),
 ("Sulejovice",             "Sulejovice, Czechia",           50.492,  14.020, "BOH", 0, ["sulejovice"]),
 ("Lipník nad Bečvou",      "Lipník n. Bečvou, Czechia",     49.527,  17.586, "MOR", 0, ["lipnik"]),
 ("Glenside (Australia)",   "Glenside, South Australia",    -34.960, 138.640, "OTH", 0, ["glensidesouthaustralia"]),
 ("Glenside",               "Glenside, Saskatchewan",        51.437,-106.630, "CAN", 0, ["glenside"]),
 ("Beroun",                 "Beroun, Czechia",               49.964,  14.072, "BOH", 0, ["beroun"]),
 ("Čermín",                 "Czermin, Poland",               51.325,  17.700, "SIL", 1, ["cermin","czermin","tschermin"]),
 ("Minitonas",              "Minitonas, Manitoba",           52.073,-101.030, "CAN", 0, ["minitonas"]),
 ("Marienberg",             "Mykolaiv obl., Ukraine",        47.720,  30.290, "KHE", 1, ["marienberg","marienburg"]),
 ("Prostějov",              "Prostějov, Czechia",            49.472,  17.107, "MOR", 0, ["prostejov","prosejov"]),
 ("Bruntál",                "Bruntál, Czechia",              49.988,  17.465, "MOR", 0, ["bruntal"]),
 ("Český Háj",              "Rivne obl., Ukraine",           50.330,  26.520, "VOL", 1, ["ceskyhaj"]),
 ("Husinec",                "Poland (Kępno area)",           51.290,  17.850, "SIL", 1, ["husinec","toppendorf"]),
 ("Odessa",                 "Odesa, Ukraine",                46.482,  30.723, "KHE", 0, ["odessa","odesa"]),
 ("Winnipeg",               "Winnipeg, Manitoba",            49.895, -97.138, "CAN", 0, ["winnipeg"]),
 ("Bohemka",                "Mykolaiv obl., Ukraine",        47.830,  30.600, "KHE", 1, ["bohemka"]),
 ("Praha",                  "Prague, Czechia",               50.075,  14.437, "BOH", 0, ["praha"]),
 ("Cheb",                   "Cheb, Czechia",                 50.079,  12.370, "BOH", 0, ["cheb"]),
 ("Vancouver",              "Vancouver area, BC",            49.283,-123.121, "CAN", 0, ["vancouver","langley","surrey","newwestminster"]),
 ("Outlook",                "Outlook, Saskatchewan",         51.497,-107.052, "CAN", 0, ["outlook","strongfield","broderick","lastmountain"]),
 ("Saskatoon",              "Saskatoon, Saskatchewan",       52.134,-106.647, "CAN", 0, ["saskatoon"]),
 ("Regina",                 "Regina, Saskatchewan",          50.445,-104.619, "CAN", 0, ["regina"]),
 ("Swan River",             "Swan River, Manitoba",          52.106,-101.267, "CAN", 0, ["swanriver"]),
 ("Medicine Hat",           "Alberta, Canada",               50.041,-110.677, "CAN", 0, ["medicinehat","calgary"]),
 ("Toronto",                "Ontario, Canada",               43.653, -79.383, "CAN", 0, ["toronto","mississauga","londonontario","canora"]),
 ("Šumperk",                "Šumperk area, Czechia",         49.965,  16.971, "MOR", 0, ["sumperk","petrovnaddesnou","rapotin","bohdikov","vikyrovice"]),
 ("Starý Jičín",            "Starý Jičín, Czechia",          49.573,  17.965, "MOR", 1, ["katzendorf","staryjicin","starojicka","kocicilhota","senovunjicina"]),
 ("Smidary",                "Smidary, Czechia",              50.283,  15.500, "BOH", 0, ["smidary"]),
 ("Namysłów",               "Namysłów area, Poland",         51.075,  17.700, "SIL", 1, ["namslau","bachwitz","sophienthal","bachovice"]),
 ("Syców",                  "Syców, Poland",                 51.297,  17.717, "SIL", 0, ["groswartenberg","grosswartenberg","growartenberg","sycow","kempen","kepno"]),
 ("Teplice",                "Teplice, Czechia",              50.640,  13.825, "BOH", 0, ["teplice"]),
 ("Straklov",               "Rivne obl., Ukraine",           50.400,  25.900, "VOL", 1, ["straklov","strakliv"]),
 ("Jadvipol",               "Rivne obl., Ukraine",           50.590,  26.180, "VOL", 1, ["jadvipol","jadwipol"]),
 ("Dembrovka",              "Volhynia, Ukraine",             50.600,  26.000, "VOL", 1, ["dembrovka"]),
 ("Dombrovka (Bashkiria)",  "Bashkortostan, Russia",         54.900,  54.500, "OTH", 1, ["dombrovka","dobrovka"]),
 ("Svatá Helena",           "Sfânta Elena, Romania",         44.650,  21.720, "OTH", 0, ["svatahelena","sfantaelena"]),
 ("Ústí nad Labem",         "Ústí n. Labem, Czechia",        50.661,  14.032, "BOH", 0, ["ustinadlabem"]),
 ("Most",                   "Most, Czechia",                 50.503,  13.636, "BOH", 0, ["most"]),
 ("Liberec",                "Liberec, Czechia",              50.767,  15.056, "BOH", 0, ["liberec"]),
 ("Chomutov",               "Chomutov, Czechia",             50.460,  13.418, "BOH", 0, ["chomutov","vejprty","bilina"]),
 ("Olomouc",                "Olomouc, Czechia",              49.594,  17.251, "MOR", 0, ["olomouc","verovany","cisarov","polkovice","dubnmorave","predmosti","prerov"]),
 ("Brno",                   "Brno, Czechia",                 49.195,  16.608, "MOR", 0, ["brno","jevicko","boskovic","vazany"]),
 ("Hradec Králové",         "Hradec Králové, Czechia",       50.209,  15.832, "BOH", 0, ["hradeckralove","cernilov","litomysl"]),
 ("Uherské Hradiště",       "Uherské Hradiště, Czechia",     49.070,  17.460, "MOR", 0, ["uherskehradiste","tlumacov","jankovice","uherskyostroh","hranicenamorave","krasnoumezirici","otaslavice"]),
 ("Central Bohemia",        "villages nr. Kolín & Beroun",   50.028,  15.200, "BOH", 1, ["losany","kostelecnadcernymilesy","cercany","karlstejn","zbisov","novedvory","zednik"]),
 ("Vídeň",                  "Vienna, Austria",               48.208,  16.373, "OTH", 0, ["viden","vienna","limbergrakousko"]),
 ("Mauthausen",             "Mauthausen, Austria",           48.244,  14.522, "OTH", 0, ["mauthausen"]),
 ("Kherson",                "Kherson, Ukraine",              46.635,  32.616, "KHE", 0, ["kherson","cherson","choroschowa","hofustal"]),
 ("Krym",                   "Crimea",                        45.300,  34.400, "OTH", 1, ["krym","crimea","dzhankoi","lobanovo","murzabek"]),
 ("Žytomyr obl.",           "Zhytomyr obl., Ukraine",        50.250,  28.660, "VOL", 1, ["majvizdorf","zitomir","zhytomyr"]),
 ("Luck",                   "Lutsk, Ukraine",                50.747,  25.325, "VOL", 1, ["luck","lutsk","kopcze","poddubce","puchava"]),
 ("Dubno",                  "Dubno, Ukraine",                50.417,  25.751, "VOL", 1, ["dubno","ploska","dubiscze"]),
 ("Zdolbuniv",              "Zdolbuniv, Ukraine",            50.520,  26.243, "VOL", 0, ["zdolobunov","zdolbuniv","zdolbunov"]),
 ("Rivne",                  "Rivne, Ukraine",                50.619,  26.251, "VOL", 0, ["rovno","rivne","holubna","sirotinka","korostovo","volkov","novostavce","ozenin","porozov","zakrewczina","zakrvcina","kadisce","kadyszcze","stepanovka","stepanowka","cubovka","alexandrovka"]),
 ("Kyiv obl.",              "Kyiv obl., Ukraine",            50.450,  30.523, "OTH", 0, ["veselynivka","baryshivka","kiev"]),
 ("Poland — other villages","scattered, Łódź / Wielkopolska",51.900,  18.400, "SIL", 1, ["grodziec","kucow","kuczow","mielecin","folwark","faustynow","sokolniki","pozdenice","sacken","lubin","prostrednipodebrady","gesiniec","strzelin","sulmierzyce","mazury","kacik"]),
 ("Wrocław / Breslau",      "Wrocław, Poland",               51.108,  17.038, "SIL", 0, ["breslau","wroclaw"]),
 ("Galicia",                "Galicia (Austria-Hungary)",     49.850,  22.680, "OTH", 1, ["galicia","wietlin","jaroslau"]),
 ("Lučenec",                "Lučenec, Slovakia",             48.331,  19.667, "OTH", 0, ["lucenec"]),
 ("Opava",                  "Opava, Czechia",                49.938,  17.903, "MOR", 0, ["kylesovice","opava"]),
 ("Františkovy Lázně",      "Františkovy Lázně, Czechia",    50.121,  12.352, "BOH", 0, ["frantiskovylazne"]),
 ("Keblice",                "Keblice, Czechia",              50.480,  14.070, "BOH", 0, ["keblice","zim","milesov"]),
 ("Jílové u Děčína",        "Jílové, Czechia",               50.760,  14.100, "BOH", 0, ["jiloveudecina"]),
 ("Hořovice",               "Hořovice, Czechia",             49.836,  13.902, "BOH", 0, ["horovice"]),
 ("Columbus, Ohio",         "Ohio, United States",           39.961, -82.999, "OTH", 0, ["carlislecemetery","columbusohio"]),
 ("Oregon",                 "Oregon, United States",         45.520,-122.680, "OTH", 1, ["washingtonoregon"]),
 ("Prince Rupert",          "Prince Rupert, BC",             54.312,-130.320, "CAN", 0, ["princerupert"]),
]

REGION_NAME = {
    "BOH": "Bohemia", "MOR": "Moravia & Silesia (CZ)", "SIL": "Zelów & Silesia (PL)",
    "VOL": "Volhynia", "KHE": "Kherson & Black Sea", "CAN": "Canada", "OTH": "Elsewhere",
}
# Fallback region dots for places we cannot pin to a settlement
REGION_FALLBACK = {
    "VOL": ("Volhynia (unspecified)", "Ukraine", 50.62, 26.25),
    "SIL": ("Poland (unspecified)", "Poland", 51.47, 19.22),
    "BOH": ("Czechia (unspecified)", "Czechia", 50.08, 14.44),
    "CAN": ("Canada (unspecified)", "Canada", 51.44, -106.63),
    "KHE": ("Black Sea steppe", "Ukraine", 46.90, 31.00),
    "OTH": (None, None, None, None),
}


def fold(s):
    s = unicodedata.normalize("NFKD", s.replace("ß", "ss"))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z]", "", s.lower())


COUNTRY_HINT = [
    (["ukrajina", "ukraine", "volyn", "wolyn", "ukraina"], "VOL"),
    (["polsko", "poland", "polen", "lodz", "slask", "schlesien", "silesia", "preuss", "prusy", "deutschland", "germany", "prussia"], "SIL"),
    (["kanada", "canada", "saskatchewan", "manitoba", "alberta", "ontario", "columbia"], "CAN"),
    (["russia", "rusko", "cherson", "kherson"], "KHE"),
    (["cesko", "ceska", "czech", "czechia", "cr", "cz", "ceskoslovensko", "cechy", "morav"], "BOH"),
]


def canon(raw):
    """Map one raw PLAC string to (label, modern, lat, lon, region, approx) or None."""
    if not raw:
        return None
    f = fold(raw)
    for label, modern, lat, lon, region, approx, keys in GAZETTEER:
        if any(k in f for k in keys):
            return (label, modern, lat, lon, region, approx)
    for words, region in COUNTRY_HINT:
        if any(w in f for w in words):
            nm, md, lat, lon = REGION_FALLBACK[region]
            if nm:
                return (nm, md, lat, lon, region, 1)
    return None


# ------------------------------------------------------------------- assemble

def main():
    indi, fam = parse(GED)

    for r in indi.values():
        for src, dst in (("bplac_raw", "bplac"), ("dplac_raw", "dplac")):
            c = canon(r[src])
            r[dst] = c[0] if c else ""

    def parents(i):
        out = []
        for f in indi.get(i, {}).get("famc", []):
            for p in (fam[f]["husb"], fam[f]["wife"]):
                if p:
                    out.append(p)
        return out

    # --- direct line: BFS up from David
    gen = {ROOT: 0}
    order = [ROOT]
    q = [ROOT]
    while q:
        x = q.pop(0)
        for p in parents(x):
            if p not in gen:
                gen[p] = gen[x] + 1
                order.append(p)
                q.append(p)

    people = []
    for pid in order:
        r = indi[pid]
        c = canon(r["bplac_raw"]) or canon(r["dplac_raw"])
        people.append({
            "id": pid,
            "gen": gen[pid],
            "name": r["name"] or "?",
            "sex": r["sex"],
            "b": r["birt"], "d": r["deat"],
            "bp": r["bplac"], "dp": r["dplac"],
            "region": c[4] if c else "",
        })

    # --- place tallies across the WHOLE file (every birth/death/marriage)
    tally = collections.Counter()
    meta = {}
    unplaced = collections.Counter()
    for r in indi.values():
        for raw in (r["bplac_raw"], r["dplac_raw"]):
            if not raw:
                continue
            c = canon(raw)
            if c:
                tally[c[0]] += 1
                meta[c[0]] = c
            else:
                unplaced[raw] += 1
    for f in fam.values():
        raw = f["mplac"]
        if raw:
            c = canon(raw)
            if c:
                tally[c[0]] += 1
                meta[c[0]] = c
            else:
                unplaced[raw] += 1

    places = []
    for label, n in tally.most_common():
        lab, modern, lat, lon, region, approx = meta[label]
        places.append({"label": lab, "modern": modern, "lat": lat, "lon": lon,
                       "region": region, "approx": bool(approx), "n": n})

    # --- migration edges: birthplace -> deathplace, when they differ
    edges = collections.Counter()
    for r in indi.values():
        a, b = r["bplac"], r["dplac"]
        if a and b and a != b:
            edges[(a, b)] += 1
    flows = [{"from": a, "to": b, "n": n} for (a, b), n in edges.most_common() if n >= 2]

    # --- coverage / honesty numbers
    stats = {
        "individuals": len(indi),
        "families": len(fam),
        "direct_line": len(people),
        "generations": max(gen.values()),
        "placed_refs": sum(tally.values()),
        "unplaced_refs": sum(unplaced.values()),
        "unplaced_distinct": len(unplaced),
        "line_missing_birth": sum(1 for p in people if not p["b"]),
        "line_missing_death": sum(1 for p in people if not p["d"]),
        "approx_places": sum(1 for p in places if p["approx"]),
    }

    out = {"people": people, "places": places, "flows": flows,
           "regions": REGION_NAME, "stats": stats}
    json.dump(out, open("data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print("\ntop unplaced:")
    for raw, n in unplaced.most_common(20):
        print(f"  {n:3d}  {raw}")


if __name__ == "__main__":
    main()
