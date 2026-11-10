# Sleeve – overdracht voor de volgende agent (Codex of Claude)

Stand: 9 nov 2026, versie 0.5.26 (tag `v0.5.26`, branch `feiten`, github.com/reprise-labs/sleeve).

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

## Open
- **Witte platen op de witte deksel** (Queen A/B, Deena A/B/C): André scant ze opnieuw met een donker vel. Hier geen tijd meer aan besteden.
- **HNY kant A:** twijfel op de rand.
- **Super Jewel Box:** de maat van de achterkaart is onzeker.
- **Digipak en kartonnen hoesje:** nog niet op echte scans getest.
- **Andere promo's:** André zoekt nog waar de map met ruwe scans staat.
