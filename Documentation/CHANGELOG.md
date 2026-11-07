# 0.4.12 — Rechte labels, schone naden, barcodes en automatische vinylkleur

- Plaatlabels recht: de scheefstand wordt op het label zelf gemeten (1600 px) in plaats van op de hele plaat verkleind tot 1200 px. Een gemeten scheefstand boven 12 graden wordt als meetfout genegeerd (`MAX_LABEL_SKEW`).
- "Hoes en plaat juist draaien" bij platen: wijkt de Discogs-foto minder dan 6 graden af (`MAX_PHOTO_SKEW`), dan alleen de kwartslag (de foto staat zelf scheef). Wijkt hij meer af, dan volgt Sleeve de foto exact (labels waarop de tekstmeting misleidt, zoals FIRE en Graduated Fool). Een exacte draaiing van een plaat werd voorheen niet uitgevoerd; opgelost.
- Naden: welke deelscan per plek wordt gebruikt, bepaalt de scherpste scan (met minder gewicht bij de scanrand). Een naadzoeker (graph cut, `SEAM_SIDE` 1200 px) mag de grens alleen binnen een strook van 40 px verleggen (`SEAM_CORRIDOR`), zodat die tussen woorden loopt. Alleen de heel grove toon (`TONE_SIGMA`) wordt tussen deelscans gemengd. Geen dubbele letters (Hotel New York), geen wazige scanranden (Urban Solitude) en geen blokken op goud vinyl (Together Alone).
- Releasevoorstellen: zo nodig worden alle scans gelezen, tot de eerste bruikbare barcode. Zoeken gaat barcode → catalogusnummer en tekst; logo's die als één woord gelezen worden, worden gesplitst (AnoukUrbanSolitude → Anouk Urban Solitude). Catalogusnummers uit drukwerkregels gaan voor grote losse tekst (TOGETHER ondersteboven → JIH13901); bij een barcode-treffer wordt het catalogusnummer van de uitgave getoond. Elke tekstherkenning heeft een eigen proces (de gedeelde procesvariabele gaf geen voorstellen).
- Herhaalde voorkant: de grootste is de voorkant; een duidelijk kleiner exemplaar (buitenkant binnenhoes) heet `insert` en wordt ter controle voorgelegd.
- Automatische vinylkleur: wijkt de gescande plaatkleur af van de kleurnaam op Discogs, dan maakt Sleeve een `_kleur`-voorstel met een Discogs-foto waarvan de tint wél bij die naam past (FIRE: rood → oranje). Originelen blijven behouden; zilver, zwart, clear, marbled en splatter niet automatisch.

# 0.4.11 — Geen rode of grijze gloed meer op samengevoegde hoezen

- Samenvoegen van deelscans: de lichtcorrectie per deelscan gebruikt nu één gedeeld lichtverloop voor alle kleurkanalen, plus per kanaal alleen een vaste kleurzweem. Voorheen kreeg elk kanaal een eigen verloop dat vanuit de overlap over de hele scan werd doorgetrokken; dat gaf op wit papier een rode, roze of grijze gloed die niet op de scans stond.
- Het lichtverloop per deelscan is begrensd op ongeveer 6% over de hele breedte/hoogte (`MAX_SLOPE`), de vaste kleurzweem per kanaal op ongeveer 4% (`MAX_CAST`). Voorheen liep de correctie per kanaal tot ±15%.
- Alleen `scan_stitch.py` is gewijzigd. Losse scans, `--geen-kleur`, Discogs-kleur en -stand, uitsnijden en uitvoerresolutie zijn ongewijzigd.

# 0.4.10 — Hoezen met witte randen en losse hoekscans

- Hoesranden: een grote gesloten rechthoek kan een aantoonbaar afwijkende combinatie van scanner- en afbeeldingslijnen vervangen. Eerdere overeenkomende uitsneden blijven behouden.
- Een gedeeld logo identificeert niet langer de volledige hoes als voorkant: de Discogs-overeenkomst moet voldoende beeldoppervlak bestrijken.
- Een losse hoekscan mag bij één bestaande groep aansluiten als de overlap sterk en eenduidig is; conflicten en twijfel blijven uitgesloten.
- Een herkende voorkant blijft beschikbaar bij het herkennen van herhaalde hoesbeelden.

# 0.4.9 — Kleurkopieën naast de scans en rode vinylkanten

- Kleurkopieën worden in de map van de gekozen beelden opgeslagen met `_kleur.png`; bestaande bestanden blijven behouden en krijgen bij herhaling een volgnummer.
- Geen aparte Kleurvoorstellen-map of mapkeuze voor kleurcorrectie meer.
- Alleen de nieuw gemaakte kopieën worden als kleurresultaat gecontroleerd. Scanmetadata blijft behouden; kleurgeschiedenis staat in een verborgen `.sleeve`-submap.
- Rode vinylplaten: etiketranden worden ook op kleurverschil herkend. Een contrastrijke tweede tekstlezing voorkomt dat bijna identieke A/B-labels in één groep belanden.
- De kleurworkflowtest vergelijkt genormaliseerde paden en rapporteert fouten zonder een crashmelding. Testbeelden worden naar een eigen testmap gekopieerd.

# Changelog

## 0.4.8 — prerelease, 6 November 2026

- Keep mapped work/output files visible to the scratch scheduler through repair and PNG encoding, after source maps have closed. Other workers can wait for those buffers to release space instead of failing prematurely.
- Exclude a worker’s own output activity from its wait condition, avoiding self-waits; stale claims and genuinely insufficient space remain handled.
- Show disk-space amounts in decimal GB, matching Finder.
- Present processing errors before opening review; preserve partial outputs for inspection.
- Image-processing calculations and output resolution are unchanged. Targeted cross-process disk regression checks and image tests passed. This hotfix is provided for the user’s FIRE practice test; the full FIRE timing remains the measured 0.4.7 result.

## 0.4.7 — prerelease, 6 November 2026

- Process separate components concurrently with a shared memory budget; start the largest group first and preserve original grouping, source identities and final roles.
- Reuse work previews only at the exact requested scale, with the same colour conversion and an unchanged source fingerprint. Remove consumed temporary previews.
- Store light-correction planes compactly and composite in bands. Stream full-resolution sources and use mapped output buffers.
- Turn covers before the first PNG save. Transfer merged discs to the cutting stage through lossless, uncompressed TIFF files.
- Coordinate native scratch reservations across workers; wait for live renderers to release space, while still rejecting genuinely insufficient space.
- Report component-specific progress, elapsed time and the number of active components. Cancellation stops isolated workers and their descendants.
- Honour an explicitly selected single-image role before attempting automatic disc detection.

Measured FIRE run: 28 scans to six full-resolution images in 11 minutes 23 seconds including file checks, without the separate colour pass. All six files exactly match the verified faster control run.

Output resolution is retained. Timing, pixel comparisons and test limitations are documented in TESTS.md. This is a prerelease tested on one Apple M1 Mac with 8 GB RAM.

## 0.4.6 — local test build

- Accelerate broad transition filtering, share preview decoding and reduce redundant writes during light correction.
- Remove full-size RGB copies during source decoding and cap image-worker thread counts.
- Complete FIRE measurement: 28 scans to six full-resolution images in 28 minutes 43 seconds, including file checks, without the separate colour-correction step.
