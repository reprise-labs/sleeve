# Scanwijzer voor Sleeve

Sleeve werkt op feiten: randen die echt in de scan staan en maten die echt gemeten zijn.
Wat niet op de scan staat, kan Sleeve niet meten; dan krijg je TWIJFEL. Met deze scanwijze
staat alles erop en hoeft Sleeve nergens te raden.

## De vijf regels

1. **De achtergrond is anders dan de rand van het onderdeel.**
   - Licht onderdeel (witte hoes, wit kaartje, wit of geel dekkend vinyl): leg er een **effen,
     gekleurd of donker vel** achter, tussen het onderdeel en de klep. Een paars vel werkt goed.
   - Doorschijnend vinyl (clear, translucent blauw/groen): **optie A**, per positie twee scans zonder de plaat te
     verschuiven: één met de witte klep (de kleur), één met een vel óp de plaat (de rand). Vel: clear → mat zwart;
     blauw/groen → oranje of geel; magenta/rood → groen; geel → blauw of paars. Mat, effen. Alle scans in hetzelfde vak.
   - Donker onderdeel (zwart vinyl, donkere hoes): de gewone **witte klep**.
   - Cd-schijf: de witte klep.
   - Twijfel je: kijk of je de rand rondom ziet in de voorvertoning. Zie jij hem niet, dan
     ziet Sleeve hem ook niet.

2. **Niet tegen de glasrand.** Leg het onderdeel minstens een centimeter van de rand van het glas
   (langs de glasrand valt het licht af en ligt een hoes vaak net niet plat: grijze stroken), aan elke kant waar een buitenrand in beeld komt. De rand van een scan is
   geen rand van de hoes: een hoesrand die op de scanrand ligt, telt niet als gezien.

3. **Hoes: liefst schuiven, niet draaien. Plaat: een kwartslag draaien is prima** (een plaat van 30 cm
   past anders niet op het glas; de glans in de groeven verschilt dan per kwart, dat is natuurkunde).
   Bij een hoes: Een scanner rekt in de ene richting net iets anders dan
   in de andere. Een hoes van 31 cm past op een A4-glas in vier posities zonder te draaien:
   schuif hem steeds een hoek verder over het glas. Moet je toch draaien (de hoes valt van
   het glas, of het ligt onhandig), dan kan dat: Sleeve legt de delen dan nog steeds goed
   aan elkaar, maar de maat kan 1 à 2 mm afwijken.

4. **Ruime overlap.** Elke deelscan deelt minstens 5 cm met zijn buren. Samen moeten de
   deelscans het hele onderdeel tonen, met rondom nog een strook achtergrond.

5. **Klep dicht en aandrukken, vooral bij de rand en bij kleine tekst; steeds dezelfde instelling.**
   Ligt een stuk niet plat, dan is de tekst daar wazig; zorg dat elk stuk tekst in minstens één scan
   ruim in het glas en plat ligt. Karton dat niet plat ligt,
   scheelt tot 2 mm in de maat. Gebruik per release één resolutie en laat de scansoftware
   de resolutie in het bestand zetten (dat doet hij standaard).

## Per soort onderdeel

| Onderdeel | Scans | Zo leg je het |
|---|---|---|
| LP-hoes (voor of achter) | 4 | Elke hoek één keer. Elke scan toont twee buitenranden met achtergrond erlangs. |
| Uitklaphoes (binnenkant, vak "Inside") | 6 | Twee rijen van drie, van links naar rechts. Alleen voor een opengeklapte hoes. |
| Insert of tekstvel (30 cm) | 4 per kant | Als een hoes. Elke kant in een eigen vak "Insert". |
| Boekjespagina (29 cm) | 2 per pagina | Eén keer de linkerhelft, één keer de rechterhelft. Elke pagina in een eigen vak "Insert". |
| Plaat | 4 + 1 | Elke scan een kwart van de plaat, met de buitenrand en achtergrond erlangs. Een kwartslag draaien mag. **Plus één scan met het label midden op het glas**: in de kwartscans ligt het label tegen de rand van het glas en is het wazig; Sleeve neemt het label dan uit deze scan (10× scherper, US blauw 14 nov). Zet hem in hetzelfde vak. |
| Cd-boekje, kaartje, achterkaart | 1 | Recht leggen (binnen een paar graden), rondom achtergrond in beeld. |
| Cd-schijf | 1 | Midden op het glas, bedrukte kant naar beneden. |
| Sticker | 1 | Op zijn eigen plastic hoes, ruim binnen het glas, plastic plat en klep dicht. Eén scan per sticker. |

## Stickers

- Scan de sticker op zijn eigen plastic hoes: één scan, de sticker ruim binnen het glas (minstens 1 cm van de rand), het plastic plat en de klep dicht.
- Sleeve herkent de scan zelf als sticker (kleine vorm met afgeronde hoeken, of rond, op een verder lege scan) en zet hem in het vak Sticker.
- Uitsnijden: bij een Music On Vinyl-sticker het gedrukte kader en de rand eromheen; bij een strook zonder kader de rand zelf; bij een ronde sticker de cirkel. Transparante hoeken.
- Rechtop op de tekst van de release (artiest, titel). Mosgroene stickers (vanaf 2025) zijn te donker voor de tekstherkenning: daar kies je zelf de stand.
- Is de rand niet goed te zien (goud op goud of geel): leg een contrasterend vel achter het plastic.

## Namen

Eindigt de bestandsnaam op het onderdeel (`..._front.png`, `..._back.png`, `..._cd.png`),
dan zet Sleeve die scan meteen in het goede vak.

## Als Sleeve toch TWIJFEL geeft

- **"not scanned: … mm2"**: dat stuk staat op geen enkele scan. Scan die hoek opnieuw
  (regel 2 en 4).
- **"directions off the circle"** / "rand op N van de 72 plekken naast de cirkel" bij een plaat: de
  rand is niet rondom te zien. Licht vinyl op de witte klep: leg er een donker of gekleurd vel achter
  (regel 1).
- **"front … and back … differ"**: één van de twee is op een drukrand gesneden of lag niet
  plat (regel 1 en 5).
- **"the left edge could not be seen …"** (hoes of kaart): langs die zijde was de rand niet te zien; Sleeve legde hem op de bekende maat. Leg een contrasterend vel achter dat deel (regel 1) en houd de rand 1 cm van het glas (regel 2).
- **"the edge of the record could not be seen at N of 36 places"**: op die plekken rondom was de plaatrand niet te zien; de cirkel is op de rest gemeten. Licht vinyl: donker of gekleurd vel erachter.
- **"which way is up"**: er is geen tekst van de release te lezen. Dat is geen scanfout;
  kies zelf de stand.
