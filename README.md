# Sleeve

Een macOS-app voor scans van je muziekcollectie: cd's en platen uitsnijden,
deelscans samenvoegen, later kleurvoorstellen maken en bestandsnamen overnemen
van een Discogs-uitgave. Met wachtrij, projecten en eindcontrole.

![Sleeve](Artwork/Sleeve.png)

## Proefversie 0.3.0

Apple Silicon, macOS 14 of nieuwer. De app is lokaal ondertekend en nog niet
bij Apple genotariseerd. Deze proefversie heeft een eenmalige installatie van
Python-beeldonderdelen nodig; die zijn nog niet in het appbestand gebundeld.
De interface is Nederlands. De werking is getest op één Mac; een schone,
andere Mac is nog niet getest.

## Installeren

1. Pak het volledige downloadpakket uit en verplaats `Sleeve.app` naar je Apps-map.
2. Voer `Installeer beeldonderdelen.command` uit vanuit het uitgepakte pakket.
   Bewaar de meegeleverde `scripts`-map en `requirements.txt` ernaast.
   Dit maakt een aparte Python-omgeving onder
   `~/Library/Application Support/com.repriselabs.Sleeve/Runtime`.
3. Open Sleeve. Als de installatie geen geschikte Python vindt, installeer dan
   Python 3.11 via [python.org](https://www.python.org/downloads/macos/),
   of met Homebrew: `brew install python@3.11`. Voer de installatie daarna opnieuw uit.

Op de oorspronkelijke ontwikkel-Mac kan de bestaande Python-installatie ook
worden gebruikt. Voor andere Macs is de aparte omgeving de bedoelde route.
De installer heeft internet nodig om NumPy, Pillow en OpenCV te downloaden.

## Gebruik

- **Scans verwerken:** selecteer één uitgave uit één bronmap. Verwerk cd en vinyl
  apart. Gemengde cd/vinyl-invoer is niet getest. Markeer etiketclose-ups als
  referentie. Elke verwerking krijgt een nieuwe submap.
- **Discogs:** namen en stand zijn apart te kiezen. Controleer de juiste uitgave.
  Gebruik voor vinylkleur bewust een foto van de volledige plaat via Kleur aanpassen.
- **Kleur aanpassen:** ook later opnieuw mogelijk. De vinylmethode beschermt het
  etiket en transparantie. De kleur is een voorstel, geen exacte meting.
- **Namen aanpassen:** controleer het voorstel. Sleeve maakt zelfstandige kopieën.
- **Wachtrij:** stel een taak in, zet hem klaar en voeg desgewenst andere taken toe.
  De lijst verwerkt taken na elkaar met hun eigen instellingen. Een fout of
  onderbreking pauzeert de lijst. Er wordt na heropenen niets vanzelf herhaald.
- **Projecten:** bewaar als `.sleeveproject` en open later via het Project-menu.
  Eerdere `.anoukproject`-bestanden kunnen ook worden geopend. Referentiefoto's,
  instellingen, geschiedenis en beoordelingen worden bewaard. Bron- en
  resultaatbeelden blijven gekoppeld aan hun locatie: laat die mappen staan.
- **Eindcontrole:** leesbaarheid en ronde uitsneden worden gemeten. Beoordeel
  volledigheid, bestandsnamen en kleur zelf. Die drie punten worden nooit
  automatisch goedgekeurd. Gewijzigde bestanden verliezen hun eerdere goedkeuring.

De voortgang meet beschikbare werkermeldingen binnen een stap. Voor stappen
zonder meetbare voortgang verschijnt een lopende indicator, geen verzonnen totaal.

## Privacy en verbindingen

Beeldverwerking gebeurt lokaal, zonder AI-API. Voor Discogs worden openbare
gegevens en referentiefoto's opgehaald; scans worden niet geüpload. Een firewall
zoals Little Snitch kan voor een nieuwe appversie opnieuw toestemming vragen
voor `api.discogs.com` en `i.discogs.com`.

De meegeleverde voorbeeldplaten zijn synthetisch. Persoonlijke scans,
testprojecten en lokale instellingen maken geen deel uit van deze repository.

## Bouwen

Xcode Command Line Tools en een geschikte Apple Silicon Mac zijn nodig:

```sh
./build.sh
```

De OCR-helper wordt tijdens het bouwen gecompileerd, zodat de app daarvoor
geen bestanden in zijn eigen ondertekende pakket hoeft te wijzigen.

## Testen

```sh
./scripts/check.sh
```

De controles maken tijdelijke bestanden en testen beeldvorm, beschadigde
bestanden, etiket/transparantie, voortgang, stoppen, projecten en wachtrij.
Grote echte albumscans en de native vensters zijn lokaal aanvullend getest;
synthetische checks bewijzen niet dat elke mogelijke scan correct wordt verwerkt.

## Reprise Labs

Sleeve is een apart project naast [Reprise](https://github.com/reprise-labs/reprise).
De twee apps hebben eigen versies en downloads. Deze repository wijzigt Reprise niet.
