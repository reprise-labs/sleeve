# 0.5.30 — Five bugs fixed: decisions, rotating, remembered choices, a rare merge crash, record colour

Found in a bug hunt through the facts route (14 November); each one reproduced first, then fixed and checked.

- **A decision on the second insert no longer overwrites the first.** Two inserts of one release get the same name (`_insert` and `_insert_2`). Answering a question on the second one rewrote `_insert.png` with the second image, so one insert was lost. A decision now replaces exactly the file you decided on.
- **Rotating works without Discogs text.** With no Discogs link (or Discogs not reachable), "which way is up" offered 90/180/270, but the choice was ignored and the same question came back. It is now applied.
- **A remembered decision belongs to the scans you saw.** Decisions were remembered by file name only. A new scan with the same name in the same folder silently got the old "keep as it is" and was reported GOED. The size and date of each scan are now remembered with it; a replaced scan is judged afresh.
- **Merging no longer crashes at certain image heights** (new in 0.5.29, about 1 in 250 parts): the last band fell outside the reduced depth map. Results for every other height are identical.
- **New Release always starts in Process Scans.** After Adjust Color, a new release opened in Adjust Color.
- **A record side made again after a decision keeps the colour of its other side.** Side A and B are matched once after a run; a side remade after a decision came back with the scanner's colour. It is now matched to the other side (which stays as it is). The colour matching also no longer turns a side black when too little vinyl is visible.

# 0.5.29 — Sharp small text on stitched sleeves, no patchwork on vinyl, light falloff of the glass removed

Found on the Urban Solitude scans on a purple sheet (12–13 November), checked against the full reference test.

- **Small text comes from the sharp scan.** The threshold for "this is print" was computed on a quarter-size image and came out about 100 times too high, so small grey text counted as plain paper and a blurred partial scan could win there. Now, where one scan is clearly sharper (1.8×), the whole block of text around it (±1.5 mm) is taken from the scan that is sharpest there. Elsewhere on a sleeve the choice is as in 0.5.28, so the found edges do not move.
- **No more patchwork on vinyl.** On a record, "sharpness" in the grooves is only gloss. Away from the label and the rim, the partial scan in which that spot lies furthest from the edge of the glass is used. Side effect (approved): a narrow strip (±1 mm) of the rounded rim of the record is now in the image; cutting exactly on its inner side follows in 0.5.30.
- **The light falloff of the glass is measured and removed on sleeves.** On this scanner the right part of the glass is 2–3% darker, in every scan. Sleeve measures that from even areas in all partial scans together and removes it before the scans are matched; it is saved next to the scans (`.sleeve-glas.json`). Not yet for records (translucent vinyl takes the colour behind it).
- **A strip of background along one part of an edge is cut off — only on a coloured sheet.** When a sleeve lay slightly differently in two partial scans, a grey strip of the sheet could fall inside the cut along part of one side. On a coloured sheet the side is now checked in 8 pieces and the worst piece counts (only the colour of the sheet, at most 1 mm). On the white lid the same check is done only where the paper of that piece differs strongly from the lid (dark or saturated print): a thin line of white lid along part of a side is cut off (Fire insert and back, Fake, Queen sleeve front); light print along the edge stays whole.
- Tried and not kept, after the reference test showed sleeves 1–2 mm smaller: a looser scanner-stretch correction, levelling the tone across seams (`SEAM_LEVEL`, off), cutting a record inward to its worst point, and checking edges in pieces on the white lid regardless of the print colour.
- Reference test: Urban Solitude green, blue and white on the purple sheet added; GF recorded for the first time.

# 0.5.28 — Scans on a coloured sheet: blank corners, faint print, clean edges; blue vinyl keeps its white label

Found on the first releases scanned with a purple sheet behind them (Urban Solitude green, blue and white, 12 November).

- **A scan without print is no longer left out.** A corner of a sleeve with nothing printed on it had nothing to be matched on and was dropped; the result then said "not scanned". Sleeve now places such a scan on its paper edges (`scan_edges.py`): the edges run straight on from the neighbouring scans, which fixes position and rotation. If the edges are not visible either, the result says which scan was left out and why.
- **Faint print is used.** When a scan fits nowhere, Sleeve looks again with raised contrast (for matching only). A page with very light lettering is now merged.
- **The shadow along the edge of each scan is measured, per side** (`shading_widths`): from the scan border to where the colour becomes flat, or to just before a jump (a paper edge). On a coloured sheet that shadow is up to 2 mm wide and was taken for the paper edge; sheets came out 4 to 10 mm too wide with a strip of background.
- **A sheet with a band of print along its edge is cut on the paper edge.** When two frames lie equally well on edges, the outer one wins, provided it is clearly larger (3 mm or more) and background is scanned outside all four of its sides. A black band along a sheet was cut off before.
- **White vinyl on a coloured sheet:** the background shines through the thin rim. Sleeve cuts where that tint ends. Only with a coloured background; on the white lid the cut is unchanged.
- **Blue vinyl no longer gets a blue-green label.** Matching the colour of side A and B divided two near-zero numbers for a colour channel in which the vinyl is black, and multiplied the whole image, label included, by the result. Such a channel is now left alone, and a correction larger than a scanner can explain (15 to 18%) is not applied at all.
- **Inserts of different sizes in one release** (a 29 cm booklet and a 30 cm sheet) no longer give doubt. Doubt only when two inserts are almost the same size (2.5 to 6 mm apart).
- **Inside with a single sheet in it** is cut as a sheet, with a note; the error text says to use Insert slots.
- **Adjust Color:** the record is located in your own photo by its label, and the label (the same paper in scan and photo) is used to match the photo's exposure to the scan. The colour is applied up to the measured edge of the label, so no dark ring remains.
- Insert size range 288 to 312 mm (was 290).

# 0.5.27 — A part that hangs no longer hangs the app; Discogs fetched once; a fixed reference test

- **No more hanging.** Each part has a time limit (15 minutes plus 1.5 s per megapixel of scans). A part that passes it is stopped with everything it started and reported as `NOT MADE: <part> – stopped after N minutes`; the other parts go on. Filling in the slots and matching the colour of side A and B have a time limit too.
- **Discogs is fetched once per address and remembered for an hour** (`scan_net.py`), shared by all parts. "Too many requests" (429) or a fault at Discogs is retried after a short wait instead of failing the part. Before, every part asked Discogs three to four times, close to its limit of about 25 requests a minute.
- **A fault at Discogs no longer throws away a finished cut-out.** If the text of the release cannot be fetched, the part is kept and you get doubt about which way is up, with the reason.
- **A decision is remade with the same facts.** Rotating or squaring a part in the Final Check now uses the same format, packaging and resolution as the first run (stored in `Studio-verwerking.json`). Before, a slim-jewel or cardboard-sleeve part was remade on jewel-case sizes.
- **In doubt about which way is up, Sleeve no longer turns the image.** It stays as it was cut out, and your rotation applies to exactly the image you saw. (A label set straight on its title is still shown straightened, and marked as doubt.)
- **Side letter on the label:** also read as `Side 1`, `A-Side`, `Kant A`, `Seite 2`; words from a title ("Side by side") do not count.
- **Dark sheet behind a card:** a dark, even sheet behind a CD card is no longer taken for the card or for print.
- Slots are also filled in from a Discogs master link.
- **Reference test for the facts route** (`Tests/feiten/reference.py`): approved releases are made again through the bridge and compared part by part (verdict, size in mm, upright angle, a small image print). See `Documentation/TESTS.md`.
- New: `Documentation/SCANNEN.md`, how to scan so that Sleeve does not have to doubt.

# 0.4.23 — Sleeve in English

- The whole app is now in American English: screens, buttons, messages, progress and the final check, following the approved glossary (release, cover, record, part, Final Check, Process Scans, Adjust Color, Rename Files; parts Front, Back, Inside, Insert, Insert Left/Right, Side A–D, CD, Unassigned).
- Internal signals between the processing steps are English too and changed on both sides at once (record:, cover:, orientation: unknown, done:, building full resolution:, fits best, name via Discogs failed, warning words, disk-space and incomplete-disc errors).
- Saved keys stay unchanged, so existing projects and queues still open (work modes keep their stored value and get an English title).
- File naming conventions (`_kleur`, part names in file names) and internal JSON names are unchanged.
- The reference set (formerly "gouden set") is now `Tests/reference/reference.py` with English output.

# 0.4.22 — Binnenkant insert_left/insert_right; release-zoeker voor losse titelwoorden

- De twee helften van een uitgeklapte binnenkant heten `insert_left` en `insert_right` (in de app "Inlegvel links" en "Inlegvel rechts"). Is er zo'n binnenkant, dan is "inside" bezet en heten losse tekstvellen `insert` en `insert_2`.
- Releasevoorstellen: grote losse woorden op de voorkant worden samen gelezen ("PLACES" + "TOGO"), de titel komt uit de trackregel met speelduur als die daarbij past ("Places To Go 3..47", "You &13..54" = "You & I"), en bij promo's met twijfel over de artiest telt de naam uit de credits ("Written by Anouk Teeuwe"). Places To Go en You & I vinden nu de juiste promo; alle 9 promo's in scans_2026 kloppen.

# 0.4.21 — Labelhoek: de rechte tekstregels hebben het laatste woord

- Na het rechtzetten (en na het volgen van een Discogs-foto) meet Sleeve de rechte tekstregels op het label zelf: letters worden tot regels samengevoegd, alleen lange, rechte, gevulde regels tellen (geen tekeningen of ronde randtekst), minstens drie moeten het eens zijn. Wijken ze nog 1,2 graden of meer af (`TEXT_LINE_MIN`), dan wordt dat bijgesteld. Hotel New York kant A stond 1,5 graden scheef: de Discogs-foto die Sleeve volgde, stond zelf scheef.

# 0.4.20 — Uitgeklapte binnenkant als twee vierkanten; doorzichtig vinyl als plaat

- Uitgeklapte binnenkant (twee panelen naast elkaar, in delen gescand): de scans worden één groep, ook als de uiteinden elkaar niet raken (meerdere sterke kwartslag-overlappen; bij een exacte kwartslag volstaan 25 passende punten, `MIN_INLIERS_QUARTER`). Het samengevoegde vlak (≥1,7:1) krijgt een kader van 2:1, en Sleeve slaat dat op als twee vierkanten, precies op de vouw gesplitst (`inside`, `inside_2`). Deena & Jim: kamer en bed, rechtop.
- Hoes of plaat: is de cirkel bijna even sterk als het vierkant (doorzichtig vinyl op het witte deksel), dan beslist het asgat midden in de cirkel (`centre_hole`). To Get Her Together kant A was als hoes verwerkt.

# 0.4.19 — Tekstvellen niet meer als plaat

- 0.4.18 gaf het ruimere hoeskader de randsteun van de zwakke papierrand. Daarmee won de cirkelzoeker en werden de Deena & Jim-tekstvellen als plaat uitgesneden. Hoes of plaat wordt nu weer beslist op de steun van het sterke vierkant (zoals in 0.4.17); het ruimere kader bepaalt alleen de uitsnede.

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
