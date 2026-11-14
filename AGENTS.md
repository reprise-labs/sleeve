# Sleeve – overdracht voor de volgende agent (Codex of Claude)

Stand: 14 nov 2026, versie 0.5.41 (branch `feiten`, github.com/reprise-labs/sleeve).

> **Werk altijd op branch `feiten`.** Niet op `release/0.4.12` of `backup-local-0.4.23`: dat is de oude route met regels.
> Controleer bij de start: `git checkout feiten && git pull origin feiten`.
Antwoord André kort en in het Nederlands. Meld per release de uitkomst.

## Uitgangspunt: alleen feiten, geen regels
- Elk onderdeel (front, back, inside, insert, inlay, side a/b…, cd) krijgt **GOED** of **TWIJFEL** (of FOUT als er niets te maken valt).
- Bij twijfel beslist André ("Keep as it is", draaien, vierkant maken). Sleeve onthoudt dat per scanmap (`.sleeve-beslissingen.json`) en gokt nooit zelf.
- Een feit is meetbaar of komt van Discogs: maten van de verpakking, randen die echt in de scan staan, tekst van de release, de Discogs-foto, barcode. Geen uitzonderingen per hoes.
- Maten hoeven niet op de mm: de hoes moet kloppen (compleet, op de echte rand, rechtop). Front/back en inserts mogen 2,5 mm verschillen (`SAME_PRINT_MM` in `Resources/studio_bridge.py`).

## Werken
- Tests: `zsh scripts/check.sh` → moet eindigen met "Controles geslaagd".
- **Vaste toets van de feitenroute (verplicht vóór elke release):** `python3 Tests/feiten/reference.py run` → moet eindigen met "ALL THE SAME".
  - Maakt de vastgelegde releases opnieuw via de bridge en vergelijkt per onderdeel oordeel, maat, stand en beeld. De scans staan in `~/Desktop` (of `SLEEVE_TESTSCANS`).
  - Een verschil is een regressie, tenzij het de bedoeling van je wijziging is. Leg een bedoeld verschil aan André voor; na zijn akkoord: `reference.py record <naam> --approved`.
  - `--groot` neemt ook Fire en GF mee (1200 dpi, lang, ±5 GB vrij nodig). `--keep <map>` bewaart de beelden om te bekijken.
  - Niets anders tegelijk laten draaien: de tekstherkenning schakelt bij drukte over op snel lezen en dan verschilt de uitkomst.
- Bouwen: versie in `build.sh` ophogen, `zsh build.sh`; app kopiëren naar `~/Desktop/claude need fix/Sleeve - test <versie>/` en zip maken met `ditto -c -k --sequesterRsrc --keepParent`.
- Release: tag `v<versie>` pushen en `gh release create … --prerelease --target feiten` met de zip.
- Git-auteur: `reprise-labs <334611916+reprise-labs@users.noreply.github.com>`. Niet force-pushen.
- Python-runtime van de app: `~/Library/Application Support/com.repriselabs.Sleeve/Runtime/bin/python3`.
- Schijf loopt snel vol (scans van 1200 dpi): ruim eigen tussenbestanden op; het samenvoegen weigert bij te weinig ruimte.

## Route (één onderdeel)
`studio_bridge.py` (actie `scan`) → per vak `Resources/Tools/scan_feitenroute.py`:
1. `scan_stitch.py --vorm ruw`: scans samenvoegen (rekcorrectie alleen als de passing er echt beter van wordt).
2. `scan_feiten.py`: uitsnijden op de maten van de verpakking (`SHAPES`), randen op 300 dpi zoeken, eindbeeld op volle resolutie. Vinyl en cd transparant (achtergrond en gat).
3. `scan_rechtop.py`: rechtop zetten met de bekende tekst van de release (Discogs). Daarna de Discogs-foto, en daarna andere leesbare tekst (alleen echte woorden). Labels worden recht gezet op de tracklist.
4. Naam via `scan_naam.py` (jaar uit het bevestigingsscherm).

Extra feiten:
- **Al uitgesneden** geldt alleen bij transparantie rondom. Een gewone scan met de goede buitenmaat wordt eerst echt op randen doorzocht (wit hoesje op witte deksel).
- **Gekleurd vlak**: alles wat gekleurd is hoort bij het kaartje; ligt de snede binnen het gekleurde vlak (drukrand, bv. Places To Go), dan wordt op de buitenrand van het gekleurde vlak gesneden (cd).
- **Buitenste rand (cd)**: bij vierkante cd-kaartjes wint per zijde de buitenste rechte rand. Ook een zwakke rand telt (wit kaartje op witte deksel), mits hij in minstens 7 van de 10 stukken langs de zijde te zien is en niet binnen 1 mm van de scanrand ligt. Kaartjes van 117 tot 131 mm zijn toegestaan. Bij cd gaat er langs de rand hooguit 0,3 mm af. Bij vinyl blijft de binnenste rand gelden (schaduw en karton vallen buiten).
- **Al uitgesneden (ondoorzichtig)**: past de snede op geen enkele cd-maat maar het hele beeld wel, of ligt er tussen de snede en de beeldrand nog drukwerk in plaats van deksel, dan is het hele beeld het kaartje.
- **CD-verpakking**: past een onderdeel niet bij een jewel case, dan bepaalt de gemeten vorm het (vierkant kaartje ±121 mm, kartonnen hoesje ±127 mm, digipak); dat staat in het resultaat. Een gekozen verpakking die niet bij de gemeten maat past, geeft twijfel.
- **Vakken vooraf invullen** (`scan_vakken.py`, actie `suggestGroups`), alleen op feiten:
  - back: de barcode van de release staat op de scan;
  - front: de scan past bij de Discogs-hoesfoto;
  - cd: er ligt een schijf van 120 mm op de scan.

  De rest sleept André zelf. Overlap tussen scans is géén feit gebleken: de deksel en gedeeld ontwerp geven valse overlap.

## App (Swift, `Source/`)
- Na het inslepen van de scans verschijnt een venster "Which release is this?" (`StudioRelease*.swift`): een Discogs-link plakken of laten zoeken.
- In dat venster: gegevens controleren, het jaar aanpassen en de verpakking kiezen. De vakken komen van Discogs en worden per set scans onthouden in `.sleeve-release.json` (een map kan meerdere releases bevatten).
- In de eindcontrole betekent "Keep as it is" klaar: het bestand blijft onaangeroerd.
- Altijd lichte modus.

## Testscans en uitkomsten
- **Vinyl:** `~/Desktop/vinyl/<release>`.
- **CD:**
  - `~/Desktop/vinyl/2005_together_alone_cd_dino_emi_europe`;
  - Deena CD in `~/Desktop/vinyl/2023_deena_cd`;
  - promo's in `~/Desktop/scans_2026`: `dominique 6–8` = Pretending As Always-promo, Discogs 6035104.
- **Laatste uitvoer:** `~/Desktop/sleeve_feiten/v0515` en `~/Desktop/sleeve_feiten/nacht`.
- **Uitkomst 9 nov:**
  - Fake 4/4 GOED.
  - Fire front, back en inserts GOED. Fire-insert = scans 12–15 en 16–19.
  - Deena-hoes GOED: de uitklap staat in twee panelen; de front heeft een melding van 0,1% niet gescand.
  - Deena CD en TA CD 4/5 GOED: de inlay zonder tekst is TWIJFEL.
  - Pretending-promo 3/3 GOED.
  - Promo-cd's in `~/Desktop/scans_2026`: 30 cd-onderdelen (7 promo's plus Pretending, Deena CD en TA CD), allemaal schoon uitgesneden.

## Ook 9 nov (middag, 0.5.18–0.5.24)
- **Snelheid:**
  - Het nauwkeurige tekstmodel (Neural Engine) mag maximaal 8 s duren. Hangt het, dan leest Sleeve 10 minuten lang snel; dat wordt onthouden in een vlagbestand in de tijdelijke map.
  - De bridge warmt het model op de achtergrond op.
  - Een cd met front, back en cd duurt op de Mac mini ±1,5 minuut.
- **Voortgang:** de route schrijft `SLEEVE_STEP <tekst>` naar stderr; de bridge toont dat als status per onderdeel.
- **Release-geheugen:** per set scans (bestandsnamen) in `.sleeve-release.json`, niet meer per map.
- **Bestandsnaam:** het laatste woord van de naam (na `_`, `-` of een spatie) is het onderdeel, bv. `2015_hold_me_back.png` → back. Die bestanden gaan meteen in het vak.
- **Tekstherkenning reageert soms helemaal niet** (Mac mini, ook als het scherm vergrendeld is): `run_ocr` geeft elke aanroep een harde tijdgrens (nauwkeurig 8 s, snel 15 s). Hangt ook snel lezen, dan wordt 10 minuten lang geen tekst meer gelezen (vlagbestand `sleeve-ocr-unavailable`); de stand komt dan van de Discogs-foto.
- **Tekstherkenning altijd via `scan_rechtop.ocr_lines` of `run_ocr`**: nauwkeurig hooguit 8 s, anders snel. Een eigen aanroep die wacht (zoals vroeger de kantletter met 4 × 120 s) laat een onderdeel op de Mac mini mislukken.
- **Een mislukt onderdeel wordt altijd gemeld**: 'NOT MADE: <onderdeel> – <reden>' in het eindbericht en als melding in de app.
- **Vakken in de app**: het onderdeel van een vak kies je via een menu met knoppen. Een Picker schreef soms zelf een waarde naar een ander vak, waardoor de cd 'inlay' werd. De bridge weigert twee vakken met hetzelfde onderdeel, en meldt het als een bestand naar een ander onderdeel heet dan het vak.
- **Testmodus van de app**: `Sleeve --scans "a.png|b.png" --discogs <link> --dump /tmp/x`. Die bevestigt de release en schrijft elke 5 s de indeling naar `/tmp/x_<t>s.json`.
- **Afspraak met André:** elke verbetering is een feit voor álle releases, nooit een uitzondering voor één release.

## 11 nov (0.5.27)
- **Hangen:** elk onderdeel heeft een tijdgrens (`part_time_limit` in de bridge: 15 min + 1,5 s per megapixel). Daarna wordt het gestopt en gemeld als NOT MADE.
- **Discogs:** alles gaat via `Resources/Tools/scan_net.py`: één keer per adres ophalen, een uur onthouden (map in de tijdelijke map, of `SLEEVE_NET_CACHE`), opnieuw proberen bij 429 of een storing. Nooit meer zelf `urlopen` aanroepen.
- **Beslissing:** `decide` gebruikt formaat, verpakking en resolutie van de eerste run (`run_facts`, uit `Studio-verwerking.json`).
- **Stand bij twijfel:** het beeld wordt niet gedraaid; jouw draaiing geldt voor het beeld dat je zag.
- **Scanwijze:** `Documentation/SCANNEN.md`. Een donker vel achter een kaartje telt niet als kaartje of drukwerk (`backing_mask`).
- **Nog niet op echte scans getest:** een donker vel achter een cd-kaartje (alleen nagebootst).

## 12 nov (0.5.28): scans op een gekleurd vel
- Testscans: `~/Desktop/vinyl/us_new_green_scan`, `us_new_blue_scan`, `us_new_white_scan` (Urban Solitude, 600 dpi, paars vel).
- **Deelscan zonder drukwerk:** `scan_edges.place_on_edges` legt hem op zijn papierranden (alleen `--vorm ruw`). Daarvoor: opnieuw zoeken met meer contrast (`faint_print`).
- **Randschaduw per scanzijde:** `shading_widths` in `scan_feiten.py`. Geen vaste marge meer; een vaste 2 mm verborg de echte papierrand als het vel dicht bij de glasrand lag.
- **Buitenste kader wint** (`find_rect(outer_wins=…)`), alleen vinyl-vellen, alleen als het 3 mm groter is en er achtergrond buiten alle zijden ligt (`background_outside`). Zonder die voorwaarden won de scanrand zelf, of verschoof Fake 0,6 mm.
- **Rand van de plaat:** `rim_end`, alleen bij een gekleurde achtergrond. Op de witte klep sneed hij Together Alone 1,3 mm per kant te klein (glans lijkt op doorschijnen).
- **Kleur kant A/B:** `scan_kleur_kanten.gains`; een kanaal waarin het vinyl zwart is, blijft staan.
- **Inserts:** verschillende maten mogen (`SAME_SHEET_MM`); maatbereik 288-312. Bij 280 won een band drukwerk.
- **Vaste toets:** Deena front is 0,6 mm kleiner (grijze strook boven is weg: beter); daardoor verschillen front en back 2,8 mm en zijn beide TWIJFEL. US kant B is GOED geworden. Nog niet opnieuw vastgelegd: wacht op akkoord van André.
- **Nog toe te voegen aan de vaste toets:** de drie Urban Solitude-releases op het paarse vel.

## 13 nov (0.5.29): scherpe tekst, geen lapjes op vinyl, lichtpatroon van het glas
- **Scankeuze per plek** (`scan_stitch.py`, blok 'Comparing details'):
  - Hoes: zoals 0.5.28 (scherpte ±25 px x afstand tot de scanrand), behalve waar één scan duidelijk scherper is (1,8x): dan het hele tekstblok (±1,5 mm) uit de scherpste. De drempel voor 'detail' wordt nu op dezelfde schaal gemeten als de scherpte (was ±100x te hoog).
  - Plaat: buiten sterk detail wint de scan waarin de plek het verst van de glasrand ligt (geen lapjes). Gevolg, door André goedgekeurd (keuze B): ±1 mm afgeronde rand zichtbaar. **Open voor 0.5.30: strak snijden op de binnenkant van de rand.**
- **Lichtpatroon van het glas** (`glass_fields`, alleen hoezen; `GLASS_FOR_RECORDS = False`): rechterdeel van het glas 2-3% donkerder; bewaard als `.sleeve-glas.json` bij de scans.
- **Strook achtergrond langs een deel van een zijde**: `trim_edge_lines` kijkt per 8 stukken, alleen de kleur van het vel of de klep (geen schaduw), hooguit 1 mm. Op een gekleurd vel altijd; op de witte klep alleen waar het papier van dat stuk sterk van de klep verschilt (`FAR_FROM_LID` = 60 Lab). Beeld voor beeld nagekeken: Fake, Fire, Queen-hoes, Deena back verliezen alleen klep.
- **Geprobeerd en teruggedraaid** (vaste toets: hoezen 1-2 mm kleiner): ruimere rekcorrectie, `SEAM_LEVEL` (uit; idee André: als optie, eerst rand zoeken en daarna pas naden gelijktrekken), plaat naar binnen snijden tot het slechtste punt, per stuk bijsnijden op de witte klep.
- **Les:** alles wat de toon langs randen verandert of de scan bij de rand anders kiest, verschuift de gevonden hoesrand. Altijd de vaste toets draaien, ook `--groot`.
- **Scanadvies** (SCANNEN.md): 1 cm van de glasrand, klep aandrukken bij rand en tekst, plaat mag een kwartslag draaien. Opnieuw scannen van de witte back (`~/Desktop/vinyl/us_new_white_back3`) gaf een perfecte back.
- **Open:**
  - Doorschijnend vinyl: André probeert optie A (per positie twee scans: witte klep voor de kleur, vel erop voor de rand).
  - Glans in de groeven verschilt per kwart (kwartslag gedraaid): per ring de helderheid gelijktrekken.
  - Groen kant B: label alleen op de titel rechtgezet, tracklist niet gelezen.
  - 0.5.30: FAQ en scanwijzer in de app (Help), meldingen in gewone taal met "Hoe los ik dit op?".
  - Queen en HNY: opnieuw scannen op een donker vel (rand van wit/geel vinyl op de witte klep).

## 14 nov (0.5.30): bugjacht
- Beslissing vervangt precies het eigen bestand: bridge geeft `--target <oud pad>` mee aan de route (twee inserts heetten `_insert`/`_insert_2`; de tweede overschreef de eerste).
- `rotate` uit een beslissing geldt ook zonder Discogs-tekst (tak `else` in de route).
- Onthouden beslissingen (`.sleeve-beslissingen.json`) dragen grootte+wijzigtijd per scan (`fingerprint`); een vervangen scan krijgt de oude beslissing niet meer. Oude regels zonder `files` gelden niet meer.
- Stitch: dieptekaart één rij langer (kopie laatste rij); crashte bij hoogte % 768 in {1,2,3}. Uitkomst elders bit-gelijk.
- Na een beslissing op een plaatkant: `scan_kleur_kanten.py nieuw ander --first-only` (alleen de nieuwe kant naar de andere). Lege ring of geen alfakanaal: niets aanpassen.
- Nog open uit de bugjacht: geheugenreservering render bij 1200 dpi (FieldGain niet meegeteld), dubbel rekenwerk bij hoezen in de keuzelus, dode code (`tone_fields`, `seam_level`, `square`).

## 14 nov (0.5.31): automatisch indelen
- `scan_vakken.py`: eerst stapels (SIFT op 2 px/mm, schaal 1, bestandsvolgorde zoals de Finder; nieuw onderdeel bij geen overlap, zelfde plek < 12 mm / < 20°, of overeenkomst < 0,35 x de mediaan van de stapel), dan namen op feiten (barcode → back, + stapels op dezelfde Discogs-foto; hoesfoto's (primary + foto's die erop lijken) → front, maar niet als meer stapels erop lijken; plaatrand r 147-151 mm doorlopend (mediaan ≥ 0,21) → kant, A/B/C/D op volgorde; cd 120 mm).
- Gemeten: overlap alleen, overeenkomst van de hele overlap en mate van overlap scheiden kant A/B en herhaalde hoes NIET (label = zelfde ontwerp, insert = afdruk van de hoes). Plek op het glas en sterkte van de overeenkomst wel.
- Toets: `Tests/feiten/indeling.py` (±8 min). Stand: 0 fout, 6 helemaal goed, rest naamloze stapels (inserts, inside, cd-backs zonder barcode), Deena inside in 2 stapels.
- Open: inserts/inside/inlay een naam geven (maat? Discogs-foto's?), cd-back (150 mm breed) herkennen.

## 14 nov (0.5.32): plaatrand, echte cirkel, Help
- `flat_start` in `scan_feiten.py`: per 24 stukken van de omtrek waar de kleur weer binnen 3 ΔE van het vlakke vinyl (3-5 mm) is; mediaan. Alleen DONKERDER telt (schaduw van de ronding); lichter = doorschijnen/glans = echte plaat. Eerst geprobeerd: mediaan-ring over de hele omtrek (blauw −3 mm, TA −2 mm: fout), richting-naar-de-klep (HNY viel weg: gele rand is ook minder geel). Uit te zetten met SLEEVE_FLAT_START=0.
- `soft_disc`: masker als echte cirkel; cv2.circle tekent een grote cirkel als 72-hoek (tot 0,13 mm naar binnen).
- Indelen: met front én back gevonden wordt een ander vel insert (scans bedekken < 520 mm) of inside (> 580 mm, `extent_mm`); geen insert-namen als er een inside is. Cd-back/inlay: geen feit (beide ±150 x 118).
- `Source/StudioHelp.swift`: hulpvenster + `helpTopic(for:)` (melding → onderwerp; alle 17 meldingsvormen getest). Nieuwe melding in de route? Voeg een onderwerp en een regel toe.

## 14 nov (0.5.33): naad-gelijktrekken als optie
- Reprocess Part… → vinkje → bridge `seamLevel` → route `--seam-level`: tweede stitch met `SLEEVE_SEAM_LEVEL=1` naar `*_raw_level.png`; alleen als `scans.json` (hoeken) gelijk is aan de gewone run. `scan_feiten.py --pixels`: randen op het gewone beeld, pixels uit het gelijkgetrokken beeld (`swap_pixels`: zelfde venster/hoek/bijsnijding).

## 14 nov (0.5.34): snellere toets, inlay
- `Tests/feiten/snel.py`: voortoets voor wijzigingen in het samenvoegen (keuzekaart op rekenschaal, oud vs nieuw; oude kaarten bewaard in ~/Library/Caches/com.repriselabs.Sleeve/reference/choice). Haak in scan_stitch: `STITCH_CHOICE_ONLY`.
- `reference.py`: cache van samengevoegde beelden (`SLEEVE_STITCH_CACHE`, route `stitch_cache_get/put`, max 3 GB, alleen bij ≥ 8 GB vrij), `--hoezen`, `--no-cache`. Niet `--keep` gebruiken bij weinig schijfruimte (volle schijf op 14 nov).
- Naadregel (naad tot 15 mm verleggen waar scans op de naad verschillen; eilandjes opnemen) GEPROBEERD EN WEGGEHAALD: verschoof gevonden randen (Deena back +1,3 mm, Queen-insert −0,8 mm) en gaf dubbele letters waar de naad langs een tekstregel ging. André: "beter scannen ipv verbeteren na afloop".
- Sticker (0.5.35): `scan_sticker.py` (kader → rand op vaste afstand rondom, eerste duidelijke sprong op alle zijden; of rand zelf; of cirkel in 180 richtingen; hoeken op kleur), route `sticker_route` (rechtop via scan_rechtop, cirkel met --disc). Getest op 7 chatbeelden van André; originele scans met dpi nog nodig. Strook zonder kader nog niet echt gezien. Indelen herkent een sticker (0.5.36, `is_sticker`: ≤ 15% van de scan, afgeronde hoeken ≥ 1,5 mm of cirkel ≠ 112-125 mm). Snede: vanaf de gevonden rand naar binnen tot net binnen stickerkleur is (strook zonder kader). Mosgroene stickers (2025+) zijn te donker voor de tekstherkenning: André draait zelf.

## 14 nov avond (0.5.38): optie A, labelscan
- Route: `scan_background` (rand van de scan wit+kleurloos = klep, anders vel); ≥2 van elk bij een plaatkant → vel-scans apart samenvoegen, `scan_feiten` geeft `cut_circle_px`, `map_circle` (SIFT op 1/4, gelijkvormig, schaal 1) legt hem op de klep-versie, `scan_feiten --cut-circle`. Getest: US blauw optie A (map vinyl/us_blauw_optieA): 297,3 mm, randstreep weg.
- Indelen: vel-scans bij de stapel van hun klep-scan (`background` in scan_vakken).
- Labelscan (label midden op het glas) als extra scan in het vak: label 10× scherper (sharpest wins). Oorzaak wazig label: in kwartscans ligt het label tegen de glasrand en niet plat.

- Indelen (0.5.40): barcode wint van hoesfoto in één stapel; zwakke overlap mag bij een onvolledige stapel als die daardoor ≥ 305 mm wordt (`complete`). US wit herscan (us_new_white_back3, 18 scans) goed ingedeeld.

## 14 nov laat (0.5.41): sneller indelen, Queen nieuw
- `scan_discogs.matches`: punten van een Discogs-foto één keer (cache op inhoud); `scan_vakken`: verkleinen + barcode in 3 threads. Queen 27 scans 92 → 47 s, uitkomst gelijk.
- Front: Discogs-foto telt als hoesfoto als de hoes ≥70% van de foto vult; getoonde breedte ≥ `FRONT_MIN_MM` (lp 250, cd 96). Sticker vóór insert/inside. Volgorde op het laatste getal in de naam (`number_key`).
- `scan_sticker`: na de gezamenlijke stap naar binnen nog per zijde (`side_trim_px`); Queen-sticker had 6-8 px grijs onderaan.
- Queen 2021 nieuwe scans (`~/Desktop/vinyl/queen_new_scan`, wit vinyl op paars): 7/7 GOED. Kant A: lichte grijze zweem rechtsboven (L 95 tegen 99), niet gemeld.

## Open
- **Helderheid langs de rand gelijk trekken (optie, André 14 nov "optie 1"):** gemeten toon tilt een donkere plek naar de rest; structuur blijft; standaard uit, vermeld bij het resultaat. Geen content-aware fill (verzint pixels).
- ~~Verkeerd gevouwen hoes melden~~: opgelost sinds 0.5.29 (smalle randen per stuk van een zijde bijsnijden); André 14 nov: "De back is perfect".
- **Blauw vinyl kant A:** TWIJFEL, rand op 11 plekken 1,3-1,7 mm naast de cirkel (doorschijnend vinyl op de witte klep).
- **Donker vinyl op een gekleurd vel:** `rim_end` kan daar glans voor doorschijnen aanzien; nog niet getest.
- Rand niet gezien → nu TWIJFEL met reden (0.5.37, scan_feiten: `weak_sides` en `weak_degrees`). Vannacht gemeten hoeveel onderdelen dit raakt.
- ~~Hoes > 3° scheef~~: niet doen (André: wie slordig scant, is niet de doelgroep).
- **Oude route:** `scan_cutout.py` en de vormherkenning in `scan_stitch.py` worden door de feitenroute niet meer gebruikt en kunnen eruit.
- **Eindbeeld in één keer opbouwen:** nu wordt elk beeld twee keer omgerekend (samenvoegen, daarna rechtzetten) en vier keer naar schijf geschreven.
- **Witte platen op de witte deksel** (Queen A/B, Deena A/B/C): André scant ze opnieuw met een donker vel. Hier geen tijd meer aan besteden.
- **HNY kant A:** twijfel op de rand.
- **Super Jewel Box:** de maat van de achterkaart is onzeker.
- **Digipak en kartonnen hoesje:** nog niet op echte scans getest.
- **Andere promo's:** André zoekt nog waar de map met ruwe scans staat.
