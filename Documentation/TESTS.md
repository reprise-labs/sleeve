## 0.4.20 — binnenkant en asgat

- Indeling alle 9 uitgaven: alleen DEENA-binnenkant 37–42 (nu één groep) gewijzigd. DEENA 37–42 volledig verwerkt: inside (kamer) en inside_2 (bed), 7388×7143, rechtop via Discogs.
- Hoes/plaat op alle 50 samengevoegde onderdelen: alleen TGHT kant A verandert (hoes → plaat).
- 0.4.19-run (600 dpi): HNY-voorkant compleet met ANOUK-balk; GF stopte op volle schijf. Bekend: HNY kant A label 1,45° scheef (onder de bijstelgrens).
- Nieuwe controles in `check_grouping.py` en `check_cover_boundary.py`. Volledige projectcontroles geslaagd.

## 0.4.19 — hoes of plaat

- DEENA-tekstvellen 10–13 en 14–17 (600 dpi) samengevoegd: hoes, 6955 px (~29 cm), compleet met credits en marge; plaatkant A (18–21): plaat. Controle toegevoegd in `check_cover_boundary.py`. Volledige projectcontroles geslaagd.

## 0.4.18 — hoeskader

- Kader van alle samengevoegde hoezen en vellen van de 9 uitgaven, oud tegen nieuw: alleen veranderd waar drukwerk buiten het oude kader viel — DEENA-tekstvellen (2693 → 3568 px, op de papierrand) en HNY-voorkant (3247×3207 → 3716×3716, ANOUK-balk binnen). FIRE-achterkant, GF-voorkant, FBOW-achterkant en de overige hoezen gelijk.
- Nieuw geval in `check_cover_boundary.py` (vel met gedrukte binnenlijn en tekst erbuiten). Volledige projectcontroles geslaagd.

## 0.4.17 — kwartslag-delen groeperen en samen plaatsen

- Indeling van alle scans van de 9 vinyluitgaven, oud tegen nieuw: alleen DEENA-tekstvellen (10–13, 14–17) en TGHT-inlay (9–12, 13–16) veranderd; de rest gelijk aan 0.4.14. Een eerdere variant zonder kwartslag-eis voegde GF kant A en B samen (A/B 0,58–0,77); verworpen.
- Plaatsing van alle 50 samengevoegde onderdelen, slechtste paar voor/na: vrijwel overal beter of gelijk, o.a. US-front 2,3 → 0,9 px, GF-front 2,8 → 1,0, HNY-achterkant 3,5 → 1,4, FBOW-achterkant 3,2 → 1,1, FIRE-front 5,4 → 3,6, DEENA-tekstvel 3,4 → 0,9.
- DEENA-tekstvellen (600 dpi) volledig verwerkt: naadplekken in de eindcontrole 38 en 49 → 1 en 1 (onder de meldgrens). TGHT-inlay: twee complete vellen.
- Nieuw: `check_placement.py`, en een kwartslag-geval in `check_grouping.py`. Volledige projectcontroles geslaagd.

## 0.4.16 — promo's, ISRC en labels zonder leesrichting

- Release-zoeker op 9 cd-promo's (Feet On The Ground 2×, Places To Go, You & I, Dominique, Hold Me, New Day, Pretending As Always, Together Alone), echte OCR en Discogs: 7 met de juiste uitgave bovenaan (was 0). Feet On The Ground, Dominique en Hold Me met "ISRC komt overeen"; New Day via promo-voorrang (Discogs heeft daar geen ISRC). Places To Go (gespiegeld logo) en You & I (losse letters) niet.
- Zelfde OCR op de 9 vinyluitgaven, oud tegen nieuw: betere zoekteksten bij WEN, Urban Solitude, FBOW, Together Alone en DEENA; geen barcode of catalogusnummer verloren, behalve de foute JIH13901 bij TA.
- 0.4.15-herhaling: TGHT A en B 0,0 graden, DEENA B +0,2 (was 6,1). DEENA kant A los: op 1200 dpi +0,3, op 600 dpi +4,4 zonder leesrichting; met deze versie op 600 dpi +0,2.
- Nieuwe controle in `check_release_advice.py` (promo-titel, ISRC met en zonder landcode). Volledige projectcontroles geslaagd.

## 0.4.15 — labels tot 8 graden bijstellen, minder meldingen

- 0.4.14-eindtest (9 uitgaven, volle resolutie): alle zonder fouten. Labels recht en rechtop, ook TGHT en FIRE (−0,8 / +0,7 graden), behalve DEENA kant B (6,1 graden) en TGHT kant A (4,2): buiten de oude grens van 4 graden. Vinylkleur: TA goud, US groen, HNY geel en FBOW rood komen overeen met Discogs; bij FIRE twee oranje `_kleur`-voorstellen.
- Valse naadmeldingen op platen (GF, HNY, FBOW, FIRE, US) en onterecht "nakijken" op voorkanten die op Discogs passen (GF, HNY, FBOW) zijn de aanleiding voor de twee meldingswijzigingen.
- Volledige projectcontroles (`scripts/check.sh`) geslaagd. De Swift-wachtrijtest loopt vast als tegelijk een zware verwerking draait; op een rustige Mac slaagt hij.

## 0.4.14 — leesstand-zoektocht en strengere naadmeting

- 0.4.13-eindtest (9 uitgaven, volle resolutie): alle zonder fouten; DEENA kant A/B/C/D en TGHT A/B correct ingedeeld; labels recht behalve TGHT (ondersteboven, ~25 graden); eindcontrole gaf vals alarm op platen (US, HNY, FBOW, FIRE, DEENA: tot 134 px).
- Leesstand-zoektocht op beide TGHT-labels vanuit drie startstanden (0, 70, 200 graden): telkens recht en rechtop.
- Strengere naadmeting (halve resolutie): HNY-achterkant 29 plekken (terecht), DEENA kant A 1 (onder de drempel), DEENA-tekstvel 0.

## 0.4.13 — kantherkenning, eindcontrole en labelstand

- Indeling van alle scans van acht uitgaven (DEENA, TGHT, TA, US, GF, HNY, FBOW, FIRE): DEENA kant A 18–21, B 23–26, C 28–31; TGHT A 20–23, B 24–27; de overige zes precies gelijk aan de goede indeling van de 0.4.12-run. Kantletters: geen enkele foute letter op alle plaatscans.
- Een eerdere aanpak (labels pixel voor pixel vergelijken) is verworpen: bij Graduated Fool verschilden scans van dezelfde kant meer dan DEENA A tegen B.
- Eindcontrole op verkleinde scans: Hotel New York-achterkant 35 plekken (tot ~15 px), Urban Solitude, WEN, FBOW 0 plekken, Together Alone-plaat 1 plek (onder de drempel van 3).
- Labelfijnbijstelling: WEN kant B +2,7 graden; op 16 al rechte labels van zes uitgaven nul (alle onder 1,5 graden).
- Volledige projectcontroles (`scripts/check.sh`) geslaagd, met nieuwe `check_sides.py`.

## 0.4.12 — labels, naden, barcodes, voorkant en vinylkleur

- Labels: Urban Solitude A/B en Graduated Fool A/B (uitvoer 0.4.11, verkleind tot 3000 px) stonden +1,9 / −3,5 / +0,6 / +2,2 graden scheef; de nieuwe meting corrigeert dat tot 0,0 graden (onafhankelijke projectiemeting), visueel gecontroleerd. Volledige `scan_cutout`-run op één plaat: 0.4.11 draaide 0,0 graden, 0.4.12 −1,9 graden.
- Naden: Hotel New York-achterkant (Scan 4–7, halve resolutie). De bronscans liggen lokaal tot 5–19 px uit elkaar (hoes niet vlak). 0.4.11 gaf dubbele/vage letters in de copyrighttekst; 0.4.12 geeft scherpe letters met de naad tussen woorden. Samenvoegtijd 41 s → 67 s op halve resolutie. WEN-front (3500 px) en Urban Solitude-kant A ook samengevoegd: neutraal papierwit, geen zichtbare naden.
- Barcodes: Urban Solitude, 16 scans: barcode 0602455508959 (alleen op scan 14) en MOVLP1573 gevonden in ~5 s; precies één Discogs-uitgave (27551973). Alleen met de oude tekst-hints (AnoukUrbanSolitud / nSolitude) nu 4 juiste uitgaven in plaats van 0.
- Voorkant: Together Alone front (308 mm) en front_2 (296 mm, artwork 3,3% kleiner) → front_2 wordt `insert` en ter controle gemarkeerd.
- Vinylkleur: getest op de vinylkanten van 6 uitgaven tegen Discogs. Alleen Set This Thing On Fire (oranje, gescand als rood) krijgt een voorstel, met Discogs-foto 7, dezelfde die handmatig gekozen was; resultaat visueel gelijk aan de handmatige kleurkopie. Goud, groen, geel, zilver en rood ongemoeid.
- Releasevoorstellen via de app-koppeling (studio_bridge): Together Alone (19 scans) barcode 0602547578068, 2 voorstellen met de gouden uitgave 8388109 bovenaan, ~4 s; Urban Solitude 1 voorstel (Moss Green). Zonder barcode en met fout catalogusnummer JIH13901: nog steeds 5 juiste Together Alone-voorstellen.
- Catalogusnummer uit alleen de gelezen tekst: Together Alone MOVLP1572 (was JIH13901), Urban Solitude MOVLP1573, Hotel New York MOVLP1575.
- Volledige keten (samenvoegen → uitknippen → Discogs-stand) op Urban Solitude A en B en Together Alone B (3500 px / origineel): labels 0,0 graden scheef. In de afgebroken app-run stonden ze +2,0 en −3,5 graden scheef door de Discogs-stand (−1,7 / +3,4 graden). Together Alone B: goud weer egaal; Hotel New York-tekst blijft scherp.
- Discogs-stand na de labelfix: Discogs-foto's wijken af bij Urban Solitude −1,9 tot +3,5, Together Alone −1,3 tot 0,0 (labels blijven 0,0 graden), FIRE A/B +36,4 / +37,2 met drie foto's eens (label nu zoals ontworpen, gelijk aan Discogs). Volledige FIRE-run via de app-koppeling: hoes, achterkant en twee automatische _kleur-voorstellen (rood → oranje) goed; labels toen nog 36 graden verkeerd, daarna met deze regel gecorrigeerd.
- Wachtrij van 6 uitgaven via de app-koppeling (eerste 0.4.12-build): TA en FBOW goed; US-back wazige woorden (scanrand gekozen terwijl scan 13 scherp was), HNY-back naad door tekst, FIRE-labels niet gedraaid (fout in Discogs-stand), GF kant A: label in Scan 9–11 wijkt af van Scan 12 (twee verschillende labels in de bronscans).
- Na de corridor-fix (verkleind): US-back scherp, HNY-back naden tussen woorden zonder dubbele letters; controles TA-goud, WEN-front en FBOW-front ongewijzigd goed. FIRE-labels na Discogs-stand 0,0 graden afwijking. FIRE-back niet verkleind te testen (8 deelscans passen op 35% niet betrouwbaar).
- Niet uitgevoerd: volledige app-run op volle resolutie, de volledige regressieset en de native app-controles.

## 0.4.11 — kleurgloed bij samengevoegde hoezen

- WEN front (Scan 1–4) en back (Scan 5–8): in de 0.4.10-uitvoer gemeten papierwit bovenaan back ongeveer RGB 244/218/217 (roze) en front deels ~207 (grijs) en ~254 (overbelicht), terwijl de bronscans overal neutraal papier hebben (~235/235/234). Oorzaak: per kanaal sterk verschillende lichtcorrectie (hellingen tot 0,6 in log-ruimte; bij de back rood 0,07 tegenover groen 0,39).
- Controle op verkleinde kopieën (langste zijde 3500 px) van dezelfde scans: met 0.4.10 dezelfde gloed; zonder kleurcorrectie neutraal; met 0.4.11 neutraal papierwit (~245) zonder zichtbare naden, visueel gecontroleerd.
- Niet uitgevoerd: volledige-resolutierender van WEN met 0.4.11, andere uitgaven (FIRE, FBOW, GF) en de volledige regressieset.

## 0.4.10 — witte hoesranden, gedeelde logo’s en losse hoekscans

- WEN: acht oorspronkelijke hoesdeelscans opnieuw op volledige resolutie verwerkt tot front (14671 × 14749) en back (14671 × 14769), met de juiste namen. Beide bestanden leesbaar; verkleinde resultaten visueel gecontroleerd op de hoesranden en behoud van tekst/witte rand.
- GF: alle 17 bronnen opnieuw automatisch gegroepeerd als front (4), back (5), sidea (4) en sideb (4). De voorkant apart opnieuw opgebouwd uit alle vier de bekende voorkantscans via de functie voor één onderdeel: 14506 × 14652, leesbaar en visueel gecontroleerd. De hele GF-uitgave is niet opnieuw gerenderd.
- WEN-vinyl: de oorspronkelijke B-scans zijn 5096 × 7016, tegenover 10192 × 14032 voor A. De bestaande vinylresultaten zijn niet vergroot of opnieuw gemaakt.
- Nieuwe regressies: gesloten hoesrand versus scanner-/illustratielijnen, behoud van een bestaande goede uitsnede, ronde objecten, gelokaliseerd gedeeld logo, unieke losse hoek, dubbelzinnige hoek en conflictveto.
- Volledige regressieset en native project-, bewerkings-, kleurworkflow- en modelcontroles geslaagd. Geen volledige FIRE- of FBOW-render opnieuw uitgevoerd voor deze versie.

## 0.4.9 — kleurkopieën in dezelfde map

Regressiecontrole: beide vinylkanten krijgen uitsluitend nieuwe `_kleur`-bestanden naast hun bronbeelden. Bij herhaling blijft de eerdere kopie bestaan en volgt `_kleur_2`. Etiket en transparantie blijven exact behouden; oorspronkelijke scans en hun Studio-verwerking.json blijven identiek. Geen volledige FIRE-scan opnieuw uitgevoerd voor deze wijziging.

FBOW-praktijkcontrole: alle 17 bronnen groeperen correct als voorzijde (4), achterzijde (5), plaat A (4) en plaat B (4). De acht vinylscans zijn opnieuw verwerkt op volledige resolutie: kant A 13725 × 13725 en kant B 13721 × 13721 pixels. Beide bestanden zijn leesbaar, rond gemeten en hebben 0% ontbrekend oppervlak in de gemeten binnenring. De verkleinde uitvoer is visueel gecontroleerd op volledige schijven en de juiste A/B-etiketten. Geen aparte kleurcorrectie toegepast.

Volledige regressieset en native project-, bewerkings-, kleurworkflow- en modelcontroles geslaagd. De kleurworkflowtest vergelijkt nu genormaliseerde paden; dat verhielp de testcrash.

# Controle van Sleeve 0.3.1 — 5 november 2026

De onderstaande controles zijn daadwerkelijk uitgevoerd op de ontwikkel-Mac
(Apple Silicon). De aparte installatie is getest met Python 3.11, NumPy 2.0.2,
Pillow 11.3.0 en OpenCV 4.12.0.88, naast de eerdere ontwikkelomgeving.

- Nieuwe aparte Python-omgeving uit requirements.txt installeren: geslaagd.
- Kleurvoorstel: etiketpixels en transparantie exact behouden, plaatkleur gewijzigd.
- Hernoemen: zelfstandige kopieën met identieke inhoud; onveilige paden geweigerd.
- Ronde, ovale, onvolledige en beschadigde beelden: correct onderscheiden.
- Onbekende kleurhistorie: wordt niet voorgesteld als oorspronkelijke scankleur.
- Werkelijke werkermeldingen sturen voortgang; onbekende fasen krijgen geen percentage.
- Stoppen beëindigt ook onderliggende processen.
- Projecten bewaren, verplaatsen en openen; ingesloten referentie blijft bestaan
  nadat de oorspronkelijke tijdelijke foto weg is.
- Instellingen, selectie, resultaten, geschiedenis, vinkjes en opmerkingen blijven bewaard.
- Oud projectformaat blijft leesbaar; nieuw formaat is .sleeveproject.
- Wachtrij: vastgelegde instellingen, volgorde, aparte uitvoermappen, bewaren en herstellen.
- Fout en annulering pauzeren de lijst; geen automatische herstart na afsluiten.
- Geen automatische visuele goedkeuring; wijziging maakt eerdere goedkeuring ongeldig.
- Beschadigde project- en wachtrijbestanden worden niet stilzwijgend overschreven.
- Opnieuw controleren en controleverslag exporteren: geslaagd.
- Namenregel voor collectie-label beperkt tot de passende artiest; andere artiesten
  behouden het door Discogs opgegeven label.
- Native Sleeve-venster: kleurvoorstel via de aparte Python-installatie afgerond,
  automatische eindcontrole getoond, voor/na visueel gecontroleerd en nieuw project opgeslagen.
- Appnaam, venstertitel en zichtbare bediening heten Sleeve / Reprise Labs.

De grote echte cd-, FIRE- en TGHT-scans zijn in de voorafgaande lokale versie
getest; ze zijn niet voor deze hernoeming volledig opnieuw doorgerekend.
De beeldalgoritmen zijn behouden. Metadatanaam, netwerk-appnaam en een
artiestgebonden naamregel zijn aangepast voor de afzonderlijke app.

Nog niet getest: installatie op een schone tweede Mac, gemengde cd/vinyl-invoer.
Visuele volledigheid, passende referentiefoto, gewenste kleur en bestandsnamen
blijven handmatige beoordelingen. De app is een proefversie, niet genotariseerd.

Voer scripts/check.sh uit om de zelfstandige controles opnieuw te doen.

Bij de finale distributiecontrole is het bouwdoel gecorrigeerd naar macOS 14.0
voor zowel de app als de OCR-helper. Dit is gecontroleerd in de Mach-O-bestanden.


## Uitbreiding 0.4.0

- Handmatige cirkel: echte ronde alfa, onveranderde RGB-pixels binnen de bron,
  behoud van eerder transparante delen, ICC en DPI; bronbytes onveranderd.
- EXIF-oriëntatie van de bewaarde uitsnede komt overeen met de native preview.
- Ongeldige cirkels en gewijzigde bronbestanden worden geweigerd.
- Echte scanverwerking van een expliciet gekozen onderdeel levert precies één
  bestand met het juiste onderdeel op.
- Modelcontroles met echte processen: alleen het gekozen resultaat vervangen,
  vorige versie vergelijken, oude bestanden behouden, bronkeuze vastleggen,
  correctie als bron voor een volgende kleurstap gebruiken, andere resultaten
  en goedkeuringen behouden, fout en annulering terugdraaien, project heropenen.
- Tussentijds bewaren tijdens een correctie bewaart de voorafgaande resultaten.
- Native venster: grenzen van de cirkel, per pixel bijstellen, live uitsnede,
  990×990-resultaat opslaan en controleren; daarna één onderdeel opnieuw
  verwerken, voor/na-verwijzing en geschiedenis controleren en project bewaren.
- Bestaande controles voor wachtrij, projecten, kleur, voortgang en stoppen slagen.

Deze uitbreiding is niet opnieuw op alle grote albumscans doorgerekend.
De cirkel maakt ontbrekende scaninhoud niet terug; kies daarvoor een volledige
bron. Er is nog geen algemene handmatige correctie van perspectief of hoesranden.

## Geheugengebruik bij grote scans (5 november 2026)

De FIRE-crash bevatte een Python-beeldwerker van ongeveer 8,75 GiB op een Mac
met 8 GiB fysiek geheugen; WindowServer reageerde 40 seconden niet meer.
De voorbereiding gebruikt nu tijdelijke, anonieme schijfbestanden en stroken.
De uitvoer wordt op 8-GB-Macs in blokken van 1024 pixels opgebouwd. Bronnen,
uitvoerresolutie en kleurprofielconversie blijven behouden. Kleurcorrecties
vermijden een volledige extra beeldkopie. Te weinig vrije schijfruimte en een
te grote afzonderlijke bron leveren een leesbare foutmelding op.

De vier echte FIRE-frontscans (waaronder 1200-dpi-scans van 10192×14032) zijn
op dezelfde 8-GB-Mac op volle resolutie verwerkt: uitvoer 14757×14660,
304 seconden, exitcode 0. De met vmmap bemonsterde maximale fysieke footprint
was circa 3,6 GiB; maximale gemeten RSS 2327 MiB. Dit is een meting van deze
proef, geen harde bovengrens voor iedere mogelijke invoer.

Kleine beeldvergelijkingen met de voorafgaande implementatie: afmetingen en
alpha gelijk; bij 1024-pixel-uitvoerblokken maximaal één RGB-niveau verschil,
bij de strooksgewijze voorbereiding maximaal twee niveaus (schaal 0–255).
De afzonderlijke kleurcorrecties zijn pixelgelijk, inclusief alpha en metadata.
Tests controleren ook opruimen van tijdelijke bestanden en de schijfruimtecontrole.
De volledige FIRE-set met alle onderdelen is niet opnieuw als één app-opdracht
verwerkt; de oorspronkelijke crashende frontgroep is wel volledig doorgerekend.


## 0.4.2 — kleurstap en releasevoorstellen (5 november 2026)

- De Discogs-hoeskleurcorrectie is verwijderd uit scanopdrachten, ook wanneer
  oude projecten of wachtrijen useColour=true bewaren. De afzonderlijke kleurstap
  voor hoezen en vinyl blijft beschikbaar; het beeldalgoritme is daarbij behouden.
- Alle bestaande regressies voor beelden, metadata, geheugen, stoppen, voortgang,
  projecten, wachtrij, eindcontrole, ronde uitsnede en herhalen: geslaagd.
- Nieuwe tests: barcodecontrole, UPC/EAN-equivalentie, meerdere persingen,
  zoekfilter, geen tekst, netwerkfout, beperkte bronselectie en oude kleurinstelling.
- Echte Discogs-zoekopdracht vanuit de gebundelde adapter met de volledige
  oorspronkelijke FIRE-bestandslijst: voltooid in circa 16,5 seconden. De barcode
  en het catalogusnummer leverden uitgaven 33644769 en 33664818 op; bij de laatste
  wordt de variant Orange getoond. Dit bevestigt dat de barcode niet uniek is.
- Afbeeldingen worden lokaal verkleind en herkend. Alleen gerichte zoektermen
  gaan naar de Discogs-API; geen scans of volledige OCR-tekst.
- Native interface in een aparte testapp met eigen testbibliotheek gecontroleerd:
  voorstellenvenster, variantkleur, expliciet kiezen vult de juiste link in,
  venster sluit na kiezen en een hoes krijgt de passende-foto-methode.
- Een voorstel wordt niet automatisch gekozen. De exacte persing en een
  kleurvoorstel blijven handmatige beoordelingen. Herkenning kan mislukken.
- De lopende FIRE-verwerking in de bestaande app is niet onderbroken.


## 0.4.2 — FIRE-herstel en betrouwbare onderdeellabels

De praktijkproef van 0.3.2 stopte bij kant A: Scan 23 was korter bijgesneden
maar had dezelfde 1200 dpi. De oude groepsvergelijking maakte elke langste
zijde even groot en verwierp die scan daardoor als een andere schaal.
Groeperen gebeurt nu op dezelfde fysieke schaal bij bekende dpi; zonder dpi
blijven gedeelde pixelschalen behouden. De acht echte vinylscans worden nu
twee groepen van vier. Een synthetische test controleert ook dat een andere
afbeelding apart blijft.

Voorlopige bestanden krijgen niet standaard Voorkant. Bekende onderdelen
worden per bestand bijgehouden in Studio-onderdelen.json; onbekende onderdelen
heten Nog te bepalen. Oude afgebroken *_hoes-resultaten worden bij openen
ook zo hersteld, tenzij een onderdeelmanifest de voorkant bevestigt.
Onbekende onderdelen vereisen een keuze voordat namen worden voorgesteld.

Bij een passende primaire Discogs-hoesfoto wordt de voorkant herkend. Een
unieke barcode op een andere hoes helpt de achterkant te herkennen. Overige
hoesonderdelen blijven voorstellen die de gebruiker visueel moet beoordelen.
De primaire-fotostatus blijft correct als een eerdere foto niet kan worden
opgehaald. De concrete melding over een onvolledige schijf wordt doorgegeven.

Herstelproef met alle 28 originele FIRE-bestanden: zes onderdelen gevonden.
De vier eerder voltooide hoezen zijn in deze proef hergebruikt; beide vinylkanten
zijn opnieuw op volle resolutie samengevoegd, uitgesneden en met Discogs gedraaid.
Alle zes definitieve namen zijn voltooid: front, back, inside, insert, sidea, sideb.
Duur circa 18,6 minuten; gemeten maximale gezamenlijke RSS circa 2956 MiB en
bemonsterde gezamenlijke fysieke footprint circa 4085 MiB. Dit is een meting
van deze proef, geen harde geheugenlimiet voor alle invoer.

Bij uitsnijden worden overtollige kopieën en kanalen vermeden en ongebruikte
bronbuffers eerder vrijgegeven. RGB/RGBA-inlezen en de volledige uitsnede zijn
met de oude implementatie pixel voor pixel vergeleken: identiek.
Alle regressies, inclusief oude projecten, annulering en onderdeellabels, slagen.


## 0.4.3 — gemeten voortgang en zichtbare stappen

Nieuwe staptellingen voor etiketten, herkenningspunten, scanvergelijkingen,
openen van bronnen, belichting, details en overgangen. Opslaan, uitsnijden,
leesrichting en Discogs krijgen expliciete fasen; onbekende duur krijgt geen
verzonnen percentage. Afronden wist de actieve onderdeelindex. Een bijgewerkte
fase houdt zijn begintijd; een nieuwe fase begint een nieuwe timer.

Nieuwe protocol- en modeltests controleren percentages, tellers, stoppen,
timers, ontbrekende percentages en de overgang naar afronden. Alle regressies
slagen. Een vergelijking met 0.4.2 op dezelfde samengestelde testbeelden geeft
identieke pixels en alpha (maximaal verschil 0).
De grote balk, werkstap, beide timers en de onderdeelstand zijn in een aparte
native testapp met eigen gegevens visueel gecontroleerd. De lopende app is niet
vervangen. De nieuwe versie is niet opnieuw met de hele FIRE-set doorgerekend.
De volledige 28-scans-praktijkrun van 0.4.2 is intussen succesvol afgerond met
zes resultaten en eindcontrole; de gemeten totale duur was 39 minuten 50 seconden.


## 0.4.4 — kleurbediening en meerdere vinylkanten

- Expliciete checkboxselectie van vinylkanten, met aparte keuze voor één hoes.
  Hoezen worden vooraf uit een vinylkleuraanvraag geweerd. Alle geselecteerde
  bronbeelden worden gecontroleerd voordat de eerste kleurkopie wordt gemaakt.
- Nieuwe kleurkopieën blijven samen zichtbaar. Opnieuw aanpassen van één kant
  vervangt alleen diens actuele voorstel; eerdere bestanden blijven op schijf.
  Bij verdergaan naar namen blijven de andere hoezen en beelden behouden.
- Selecties en de herkomst van kleurkopieën overleven het opslaan van projecten.
  Padvergelijkingen houden rekening met onder andere /var en /private/var.
- Native integratietest verwerkt A en B samen, daarna alleen B; controleert
  behoud van A, van de bronbestanden, van de hoes bij de volgende stap, en van
  de aangevinkte selectie na opnieuw openen. Alle regressies slagen.
- Native UI met een aparte testbibliotheek: A en B aangevinkt, oranje referentie
  gekozen, beide met één knop verwerkt. Geen automatische eindcontrolemelding;
  beide kleurkopieën zichtbaar, Nieuwe kleur standaard geselecteerd. Wisselen
  naar Origineel en terug toont de juiste selectie en uitleg.
- De twee echte FIRE-platen zijn op volle resolutie met de door de gebruiker
  gekozen Foto 7 uit Discogs verwerkt: 151 seconden, maximaal gemeten RSS circa
  1724 MiB. Beide bestanden leesbaar, ronde uitsneden en 0,0% ontbrekend beeld
  in de gemeten binnenring. Beide hebben colourApplied=true. De bestaande
  pixeltests controleren behoud van etiketten, alpha en originele bestanden.
- Dit bepaalt de kleur op basis van de gekozen foto; een referentiefoto is geen
  gekalibreerde meting van de fysieke plaat. De gebruiker beoordeelt het resultaat.


## 0.4.5 — minder dubbel reken- en opslagwerk

- Een samengevoegde hoes wordt binnen de eigen tijdelijke werkmap verplaatst,
  in plaats van dezelfde pixels nog eens als PNG te decoderen en te comprimeren.
- Een RGBA-beeld waarvan de Discogs-stand en kleur ongewijzigd blijven, hoeft
  niet opnieuw te worden gecomprimeerd. Pixels, alpha en bronmetadata blijven behouden.
  Echte kleurcorrecties en rotaties gebruiken de bestaande verwerking.
- Detailkeuze gebruikt stroken van 768 in plaats van 256 regels, met exact
  dezelfde convolutionele rand van 102 regels. De uitvoerresolutie blijft gelijk.
- Echte FIRE-fronttest, vier bronbeelden op volle resolutie: 299 naar 272 seconden
  in één vergelijking. Uitvoer 14757 × 14660 pixels; RGB en alpha exact gelijk.
  Gemeten piek physical footprint in beide tests circa 3,6 GiB.
- Apart gemeten op dezelfde grote hoes: overbodig PNG-opslaan kostte 18,2 seconden;
  verplaatsen minder dan 0,001 seconde. Een onveranderde Discogs-standstap ging
  van 29,3 naar 6,1 seconden. Referentiematching was voor deze gerichte meting
  vastgezet op identiteit; dit is geen meting van netwerk- of zoekwerk.
- De volledige zesdelige FIRE-run is niet opnieuw getimed. De bovenstaande
  meetwaarden zijn geen voorspelling van de totale verwerkingstijd.
- Volledige regressiesuite geslaagd, inclusief projecten, wachtrij, opnieuw verwerken,
  kleurselectie A/B, naamgeving, geheugenbewaking en de nieuwe opslagtests.
  App-ondertekening en uitvoerrechten na ZIP-uitpakken gecontroleerd.


## 0.4.6 — berekening van overgangen en scanvoorbereiding versnellen

- Brede laagfrequente mengvelden gebruiken een Gauss-piramide met correctie
  voor de filtervariantie van verkleinen en vergroten. De detailpixels komen
  nog steeds uit de originele scans op volle resolutie. Schijfmaskers, uitsnede,
  bronuitlijning en selectie van scherpe details zijn behouden.
- Detailberekening wordt overgeslagen als een bron in dat hele blok geen
  enkele detailpixel levert. De lage-frequentiebijdrage blijft behouden.
- Etiketdetectie en groepering delen één PNG-decodering per bron. Beide previews
  worden onafhankelijk met dezelfde LANCZOS-resize en ICC-conversie gemaakt.
  De tussencache is één anoniem tijdelijk bestand: bij stoppen blijven deze
  previews niet achter en er worden geen extra volledige scans in RAM gehouden.
- Belichtingscorrectie schrijft drie kanalen per strook voordat de geheugenpagina's
  worden vrijgegeven. Uitkomst en gainvelden zijn in een gerichte vergelijking
  bit-identiek; 14 vrijgaveacties werden in die fixture 6.
- Vier gerichte renderercontroles (papier, oranje, doorzichtig met een gat, zwart):
  circa 2,3x sneller. Alpha exact gelijk, maximaal 1/255 zichtbaar RGB-verschil.
- Afzonderlijke echte FIRE-hoes met de nieuwe mengmethode: 203 tegenover 272
  seconden. Resolutie 14757 × 14660 exact gelijk; alpha exact gelijk.
  0,029% van de zichtbare kleurkanalen verschilt 1/255; de overige zijn gelijk.
  Gemeten peak physical footprint circa 4,1 GiB; de geheugengrens bleef actief.
- Twee previews uit één echte FIRE-bron: 6,17 naar 3,47 seconden, alle pixels
  exact gelijk. Tests dekken RGB, RGBA, grijs, ICC en cacheverversing bij gewijzigde bron.
- Volledige regressiesuite geslaagd, inclusief projecten, wachtrij, kleurworkflow,
  stoppen, geheugen, naamgeving en de nieuwe preview- en mengveldcontroles.
- Een eerste volledige-setmeting werd bij het openen van de laatste plaatkant
  door de testbewaking gestopt (peak physical footprint circa 5 GiB). Vijf
  tussentijdse resultaten bleven behouden; dit geldt niet als een voltooide benchmark.
- Daarom zijn overbodige volledige RGB-kopieën bij openen verwijderd en gebeurt
  de RGB-profielconversie in hetzelfde beeldbuffer. Een volledige echte bron
  van 10192 × 14032 pixels geeft vóór en na exact dezelfde BGR-SHA256.
  De definitieve hele-setmeting is daarna apart met deze geheugenfix uitgevoerd.
- De herhaalde volledige FIRE-setmeting met de geheugenfix is succesvol: alle
  28 scans → zes resultaten, Discogs-namen en stand, zonder kleurcorrectie.
  Backend 1715 seconden plus 7,88 seconden dezelfde bestandscontrole: totaal
  afgerond 28 minuten 43 seconden. De eerdere praktijkrun was circa 40 minuten;
  dit is geen verse volledige A/B-meting tegen 0.4.5.
- Alle zes bestanden leesbaar. Kant A 13924 × 13924 en kant B 13764 × 13764,
  beide rond gemeten en 0,0% ontbrekend beeld in de gecontroleerde binnenring.
  Gemeten RSS-piek procesgroep circa 2822 MiB; peak physical footprint circa
  4,6 GiB. De testbewaking hoefde niet in te grijpen in deze complete run.
- De app gebruikt voor haar beeldwerk dezelfde threadbudgetten als de meting
  (OpenCV 2, OpenBLAS/Accelerate 1) om overmatige parallelle werkbuffers te beperken.
- Na de laatste geheugenfix en gelijke threadinstellingen is de volledige
  regressiesuite opnieuw geslaagd. De definitieve app is opnieuw gebouwd en
  de ondertekening is gecontroleerd.


## Volledige-resolutietest 0.4.7 — 6 november 2026

- Definitieve gebouwde appbestanden: dezelfde Python-bronnen en OCR-helper als
  de bevroren meetkopie. Volledige controlesuite geslaagd, inclusief native
  project-, wachtrij-, bewerkings-, kleurworkflow- en modelcontroles.
- Echte FIRE-set: 28 oorspronkelijke scans naar zes PNG-bestanden, met
  Discogs-namen en stand, zonder de afzonderlijke kleurcorrectiestap.
- Verwerking: 664 seconden (11 minuten 4 seconden).
  Eindcontrole: 18.60 seconden. Totaal: afgerond 11 minuten
  23 seconden. De eerdere gebruikersmeting van circa 40 minuten is geen
  nieuwe gecontroleerde A/B-tijdmeting. Het eerdere doel van 5–10 minuten is
  niet bereikt; de gebruiker heeft de behaalde circa 11 minuten geaccepteerd.
- Alle zes nieuwste PNG-bestanden zijn byte voor byte gelijk aan de eerder
  gecontroleerde 11-minutenreeks (SHA256 van ieder volledig bestand gelijk).
  De laatste wijziging in geheugenplanning verandert dus geen beeldpixels.
- Volle afmetingen behouden: front 14757×14660, back 14718×14582,
  inside 14445×14172, insert 14428×14158, side A 13924×13924,
  side B 13764×13764. Alle bestanden leesbaar; beide platen rond gemeten,
  0,0% ontbrekend beeld in de gecontroleerde binnenring.
- Vergelijking van alle zes bestanden met de complete oude 0.4.2-reeks van
  dezelfde 28 bronnen: afmetingen exact gelijk; vier hoezen hebben identieke
  alfa en maximaal 1/255 RGB-verschil. Vinyl: maximaal 3/255 in volledig
  ondoorzichtige pixels en 8/255 bij zachte randen; respectievelijk 606 en
  1929 alfapixels verschillen (0,00031% en 0,00102% van het beeld). Dat is
  vrijwel hetzelfde beeldresultaat, maar geen volledige pixelidentiteit met
  de oude beeldberekening. De verdwenen bestanden van de specifieke
  oorspronkelijke 40-minutenrun zijn niet rechtstreeks vergeleken.
- Hoogst gemeten RSS voor de procesboom: 3313.3 MiB. Hoogste
  gemonsterde peak physical footprint per proces: 3686.4 MiB.
  Geen ingreep van de testbewaking in deze volledige run.
- Native bron- en uitvoerreserveringen delen een schijfruimtebudget. Geschreven
  bytes worden niet dubbel gereserveerd; actieve renderers kunnen ruimte
  vrijgeven voor wachtende onderdelen. Echte tekorten blijven een foutmelding.
  Twee eerdere proefruns zijn veilig gestopt wegens ruimtegebrek en tellen
  niet als geslaagde benchmarks. Verbruikte werkpreviews worden verwijderd.
- Gerichte controles dekken het terugkrijgen van decodeergeheugen, prioriteit
  bij starten, stoppen van workers en kleinkindprocessen, wachten op tijdelijke
  schijfruimte, opruimen van dode reserveringen, stoppen tijdens previewdecodering,
  exacte schalen en bronwijzigingen in de cache, en losse bekende hoezen.

Dit is één dataset op één Apple M1 met 8 GB RAM. Geen algemene tijdgarantie
voor andere scanformaten of aantallen. Gemengde cd/vinyl-invoer en de eerder
uitgestelde interfacewijzigingen zijn hiermee niet toegevoegd of getest.
Visuele goedkeuring van kleur, volledigheid en juiste uitgave blijft handmatig.


## Schijfruimte-hotfix 0.4.8 — 6 november 2026

De gebruikersrun met 0.4.7 brak af bij 3,4 GiB nodig en 3,0 GiB vrij. Bronmaps
waren op dat moment gesloten, maar grote werk-/uitvoermaps van andere onderdelen
bestonden nog tijdens repareren en PNG opslaan. Die buffers blijven nu als actieve
ruimteproducent zichtbaar, zonder hun al geschreven bytes opnieuw te reserveren.
Eigen werkbuffers worden niet als een andere ruimteproducent beschouwd.

Een gerichte test met twee echte processen reproduceert deze grens: de bronlease
is afgesloten, een uitvoermap van een ander proces blijft open, en de volgende
werker moet wachten. Na het sluiten van de uitvoermap gaat hij verder. De test
controleert ook het verdwijnen van reserveringen en het vermijden van zelfwachten.
De bestaande geheugen-, schijfruimte-, beeld-, annulerings- en workflowcontroles
blijven geslaagd. Een native modeltest stuurt gedeeltelijke uitvoer gevolgd door
een echte procesfout: resultaten blijven beschikbaar, maar de fout wordt niet
meer door een automatisch geopende eindcontrole bedekt.

Dit is geen garantie dat 10 GB voor elke uitgave volstaat: tijdelijke buffers,
reeds bewaarde resultaten en macOS-wisselgeheugen kunnen de vrije ruimte wijzigen.
De volledige FIRE-run is voor deze hotfix nog niet opnieuw gemeten; de gebruiker
heeft gevraagd 0.4.8 direct beschikbaar te maken voor de eigen praktijktest.
De beeldberekeningen zijn niet aangepast.
