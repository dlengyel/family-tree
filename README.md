# The Lengyel Line

Two visuals built from a MyHeritage GEDCOM export of the Lengyel family tree —
860 people, 265 families, 1700 to today.

1. **A timeline** of all 77 direct ancestors, ten generations, each drawn as a
   lifespan bar on one shared scale and coloured by where that person was born.
2. **A migration map** of every birth, death and marriage that can be placed —
   Bohemia, the Silesian exile villages, Zelów, Volhynia, the Black Sea
   colonies and the Canadian prairies.

Everything is one self-contained HTML file. No map service, no build step at
view time, works offline.

## Privacy

The source `.ged` is **not** in this repository and is excluded by
`.gitignore`. It contains phone numbers, email and street addresses for living
people, none of which reach the output: `extract.py` reads only names, years
and places. Living people appear as a name and a birth year.

## Rebuilding

```bash
python3 extract.py ~/Desktop/<your-export>.ged   # writes data.json
python3 build.py                                 # inlines it into index.html
```

- `extract.py` — parses the GEDCOM, traces the direct line, merges the 361
  different place spellings down to 79 places with coordinates.
- `template.html` — the page: styles, layout and the drawing code.
- `build.py` — inlines `data.json` into `template.html` to produce `index.html`.

Edit `template.html`, never `index.html` — the latter is generated.

## Notes on the data

- 12 of the 77 direct ancestors have no birth year and cannot be placed on the
  timeline; they are listed by name under their generation instead.
- 29 of the 79 places are positioned approximately — small Volhynian and
  Silesian villages that no longer exist under that name, plus a few buckets
  standing for several nearby villages. They are drawn with a dashed ring.
- Place names are shown as the family wrote them, with today's official name
  underneath.
- No dates or places have been guessed or filled in.

## Previewing

```bash
python3 -m http.server 8731
```

Then open <http://localhost:8731/index.html>.
