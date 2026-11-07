# 0.4.18 — Samengevoegde hoezen en vellen niet meer te krap bijgesneden

- Hoeskader: Sleeve zoekt het vierkant dat het best op de randen past. Bij een wit vel op het witte deksel is de papierrand zwak, en kon een gedrukte lijn met een tekstregel een kleiner "vierkant" vormen: Deena & Jim tekstvel verloor links, rechts en boven tekst (27% van het drukwerk viel erbuiten), Hotel New York-voorkant de ANOUK-balk bovenaan. Nu: valt er duidelijk drukwerk (randen in beide richtingen; lijnen en scannerstrepen tellen niet) buiten het kader (`INK_OUTSIDE`), dan neemt Sleeve per zijde de eerste duidelijke rand buiten het drukwerk, en vult de korte zijde aan tot een vierkant.
- Testset: de wachtrijtest stopt bij drukte netjes (na 120 s) in plaats van te crashen met een macOS-melding "Checks is onverwacht gestopt".

# 0.4.17 — Grote vellen in kwartslag-delen als één geheel

- Groeperen: een tekstvel of inlay dat groter is dan de scanner, scan je in vier delen en draai je steeds een kwartslag. Die delen werden niet samengevoegd. Bij het vergelijken telt nu de scannerrek mee (y/x ~0,9975, draait mee met de kwartslag; bij fijne tekst zakte de gelijkenis daardoor onder de grens), en vier delen gaan samen als álle paren een kwartslag verschillen, ook al overlappen de diagonale delen maar smal (`MERGE_WEAKEST`, `MERGE_STRONGEST`). Beide alleen bij kwartslagen (`QUARTER_TOL`): kant A en B van een plaat liggen in een willekeurige hoek en scoren anders even hoog (Graduated Fool). Deena & Jim: tekstvellen 10–13 en 14–17; To Get Her Together: inlay 9–12 en 13–16.
- Samenvoegen: elk deel werd via één ander deel geplaatst (opspannende boom); bij vier delen stapelden kleine fouten zich op één naad op (letters ~6 px verschoven). Nu worden alle delen daarna tegelijk bijgesteld over alle overlappen (kleinste kwadraten, `refine_placement`). Alleen als geen paar slechter wordt (`REFINE_SLACK`); paren die volgens de boom ver afwijken, tellen niet mee (`REFINE_MAX_ERROR`).

# 0.4.16 — Release-zoeker voor promo's en labels bij onbekende leesrichting

- Releasevoorstellen: als titel telt nu de tekst die op meerdere delen staat (hoes, achterkant, cd), zonder speelduur ("New Day 3.37" → "New Day"). Copyright-, credit-, UPC- en ISRC-regels tellen niet mee, ook als © als "@" gelezen wordt. Voorheen zocht New Day op "@ 2015 Goldilox, under the exclusive license…", de copyrightregel langs de cd-rand.
- Artiest: de grootste tekst die op meer dan één deel staat; "& DOUWE BOB" onder de naam hoort erbij. Ondersteboven gelezen tekst met onzinwoorden (">lnONV") verliest het nu van de goede leesrichting.
- ISRC: Sleeve leest het ISRC-nummer ("ISRC: NL-XA9-15-00003"). Discogs zoekt er niet op, maar staat het bij een gevonden uitgave (ook zonder landcode), dan staat er "ISRC komt overeen" en komt die uitgave bovenaan.
- Staat er "For promotional use only" of "Not for sale" op, dan gaat een promo-uitgave voor.
- Labelstand: vindt Sleeve de leesrichting van een label niet, dan wordt de gemeten scheefstand toch rechtgezet; de kwartslag volgt uit de Discogs-foto. Voorheen bleef het label dan scheef (Deena & Jim kant A op 600 dpi: 4,4 graden).

# 0.4.15 — Rechtere labels en minder onterechte meldingen

- Labelstand: de fijnbijstelling op de tekstregels mag tot 8 graden (`LABEL_REFINE`, was 4). Na de leesstand-zoektocht in stappen van 15 graden kan de rest tot 7,5 graden zijn (Deena & Jim kant B stond 6,1 graden scheef, To Get Her Together kant A 4,2).
- Eindcontrole: geen naadmelding meer bij platen. Groeven en de draaiing tussen deelscans gaven daar vals alarm; het label komt meestal uit één scan.
- Eindcontrole: een samengevoegde voorkant zonder leesbare tekst kreeg "nakijken", ook als een zeker passende Discogs-foto de stand daarna al had gezet (Graduated Fool, Hotel New York, For Bitter or Worse). Die vlag vervalt nu; zonder passende Discogs-foto blijft hij staan.

# 0.4.14 — Labels met een misleidend ontwerp en minder vals alarm in de eindcontrole

- Labelstand: is het label sterk scheef (de hoekmeting wordt als onwaarschijnlijk afgewezen) of is de leesrichting onduidelijk, dan draait Sleeve het label in stappen van 15 graden rond en kiest de stand met de meeste echte woorden (`reading_sweep`, `SWEEP_MARGIN`). Voor platen zonder Discogs-foto van het vinyl met een schuin logo of strepen (To Get Her Together stond ondersteboven en ~25 graden scheef).
- Eindcontrole: een verschuiving telt alleen bij een duidelijke match (`QUALITY_RESPONSE` 0,3) en niet als de uitslag tegen de rand van het meetvak ligt. Dat gaf op labels met weinig contrast vals alarm (tot ~130 px).

# 0.4.13 — Kantherkenning, eindcontrole op naden en fijnere labelstand

- Kanten herkennen: ook leesfouten van "SIDE" tellen ("SDEA", "S1DE B"), een schuin label wordt nog eens 15 en 30 graden gedraaid gelezen, en een label met alleen een losse letter (A, B, C, D, zoals Deena & Jim) wordt herkend door losse tekens uit te knippen en vergroot te lezen. Alleen hoofdletters tellen (een omgekeerde 'a' is geen A).
- Groeperen: scans met dezelfde gelezen kantletter die via overlap verbonden zijn, beginnen samen; een scan zonder leesbare letter komt daarna bij de juiste kant. Daarmee geen kant A en B in één onderdeel meer (Deena & Jim: A, B en C apart; TGHT: Scan 22 bij kant A).
- Labelstand: na de grove meting een fijnbijstelling op de tekstregels van ±1,5 tot 4 graden (`LABEL_REFINE`); kleiner is ruis van het ontwerp. Vooral voor platen zonder Discogs-foto van het vinyl (Wen d'r maar aan kant B stond 2,7 graden scheef).
- Eindcontrole: tijdens het samenvoegen telt Sleeve plekken waar een naad door tekst loopt met zichtbaar verschoven deelscans (hoes niet plat). Vanaf 3 plekken staat er een melding bij dat bestand in de eindcontrole. Bij platen zonder passende Discogs-foto van het vinyl meldt de eindcontrole dat de labelstand alleen op de tekst is bepaald.

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
