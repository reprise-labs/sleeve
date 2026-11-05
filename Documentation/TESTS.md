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
