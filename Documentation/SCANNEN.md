# Scanwijzer voor Sleeve

Sleeve werkt op feiten: randen die echt in de scan staan en maten die echt gemeten zijn.
Wat niet op de scan staat, kan Sleeve niet meten; dan krijg je TWIJFEL. Met deze scanwijze
staat alles erop en hoeft Sleeve nergens te raden.

## De vijf regels

1. **De achtergrond is anders dan de rand van het onderdeel.**
   - Licht onderdeel (witte hoes, wit kaartje, wit of doorzichtig vinyl): leg er een **effen,
     gekleurd of donker vel** achter, tussen het onderdeel en de klep. Een paars vel werkt goed.
   - Donker onderdeel (zwart vinyl, donkere hoes): de gewone **witte klep**.
   - Cd-schijf: de witte klep.
   - Twijfel je: kijk of je de rand rondom ziet in de voorvertoning. Zie jij hem niet, dan
     ziet Sleeve hem ook niet.

2. **Niet tegen de glasrand.** Leg het onderdeel minstens een halve centimeter (liever een
   hele) van de rand van het glas, aan elke kant waar een buitenrand in beeld komt. De rand van een scan is
   geen rand van de hoes: een hoesrand die op de scanrand ligt, telt niet als gezien.

3. **Liefst schuiven, niet draaien.** Een scanner rekt in de ene richting net iets anders dan
   in de andere. Een hoes van 31 cm past op een A4-glas in vier posities zonder te draaien:
   schuif hem steeds een hoek verder over het glas. Moet je toch draaien (de hoes valt van
   het glas, of het ligt onhandig), dan kan dat: Sleeve legt de delen dan nog steeds goed
   aan elkaar, maar de maat kan 1 à 2 mm afwijken.

4. **Ruime overlap.** Elke deelscan deelt minstens 5 cm met zijn buren. Samen moeten de
   deelscans het hele onderdeel tonen, met rondom nog een strook achtergrond.

5. **Klep dicht en aandrukken, steeds dezelfde instelling.** Karton dat niet plat ligt,
   scheelt tot 2 mm in de maat. Gebruik per release één resolutie en laat de scansoftware
   de resolutie in het bestand zetten (dat doet hij standaard).

## Per soort onderdeel

| Onderdeel | Scans | Zo leg je het |
|---|---|---|
| LP-hoes (voor of achter) | 4 | Elke hoek één keer. Elke scan toont twee buitenranden met achtergrond erlangs. |
| Uitklaphoes (binnenkant, vak "Inside") | 6 | Twee rijen van drie, van links naar rechts. Alleen voor een opengeklapte hoes. |
| Insert of tekstvel (30 cm) | 4 per kant | Als een hoes. Elke kant in een eigen vak "Insert". |
| Boekjespagina (29 cm) | 2 per pagina | Eén keer de linkerhelft, één keer de rechterhelft. Elke pagina in een eigen vak "Insert". |
| Plaat | 4 | Elke scan een kwart van de plaat, met de buitenrand en achtergrond erlangs. Plaat niet draaien. |
| Cd-boekje, kaartje, achterkaart | 1 | Recht leggen (binnen een paar graden), rondom achtergrond in beeld. |
| Cd-schijf | 1 | Midden op het glas, bedrukte kant naar beneden. |

## Namen

Eindigt de bestandsnaam op het onderdeel (`..._front.png`, `..._back.png`, `..._cd.png`),
dan zet Sleeve die scan meteen in het goede vak.

## Als Sleeve toch TWIJFEL geeft

- **"not scanned: … mm2"**: dat stuk staat op geen enkele scan. Scan die hoek opnieuw
  (regel 2 en 4).
- **"directions off the circle"** bij een plaat: de rand is niet rondom te zien. Andere
  achtergrond (regel 1).
- **"front … and back … differ"**: één van de twee is op een drukrand gesneden of lag niet
  plat (regel 1 en 5).
- **"which way is up"**: er is geen tekst van de release te lezen. Dat is geen scanfout;
  kies zelf de stand.
