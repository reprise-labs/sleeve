# Sleeve – overdracht voor de volgende agent (Codex of Claude)

Stand: 9 nov 2026, versie 0.5.22 (tag `v0.5.22`, branch `feiten`, github.com/reprise-labs/sleeve).
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

## Open
- **Witte platen op de witte deksel** (Queen A/B, Deena A/B/C): André scant ze opnieuw met een donker vel. Hier geen tijd meer aan besteden.
- **HNY kant A:** twijfel op de rand.
- **Super Jewel Box:** de maat van de achterkaart is onzeker.
- **Digipak en kartonnen hoesje:** nog niet op echte scans getest.
- **Andere promo's:** André zoekt nog waar de map met ruwe scans staat.
