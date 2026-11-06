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
