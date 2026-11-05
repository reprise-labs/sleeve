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
