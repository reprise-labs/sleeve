# Scanwijzer voor Sleeve

Sleeve werkt op feiten: randen die echt in de scan staan en maten die echt gemeten zijn.
Wat niet op de scan staat, kan Sleeve niet meten; dan krijg je TWIJFEL. Met deze scanwijze
staat alles erop en hoeft Sleeve nergens te raden.

## De vijf regels

1. **De achtergrond is anders dan de rand van het onderdeel.**
   - Licht onderdeel (witte hoes, wit kaartje, wit of doorzichtig vinyl): leg er een **donker,
     effen vel** achter (zwart karton tussen het onderdeel en de klep).
   - Donker onderdeel (zwart vinyl, donkere hoes): de gewone **witte klep**.
   - Cd-schijf: de witte klep.
   - Twijfel je: kijk of je de rand rondom ziet in de voorvertoning. Zie jij hem niet, dan
     ziet Sleeve hem ook niet.

2. **Niet tegen de glasrand.** Leg het onderdeel minstens een halve centimeter van de rand
   van het glas, aan elke kant waar een buitenrand in beeld komt. De rand van een scan is
   geen rand van de hoes: een hoesrand die op de scanrand ligt, telt niet als gezien.

3. **Alleen schuiven, niet draaien.** Leg het onderdeel bij elke deelscan in dezelfde stand
   en schuif het op. Een scanner rekt in de ene richting net iets anders dan in de andere;
   draai je een kwartslag tussen twee deelscans, dan passen ze nooit helemaal.

4. **Ruime overlap.** Elke deelscan deelt minstens 5 cm met zijn buren. Samen moeten de
   deelscans het hele onderdeel tonen, met rondom nog een strook achtergrond.

5. **Klep dicht en aandrukken, steeds dezelfde instelling.** Karton dat niet plat ligt,
   scheelt tot 2 mm in de maat. Gebruik per release één resolutie en laat de scansoftware
   de resolutie in het bestand zetten (dat doet hij standaard).

## Per soort onderdeel

| Onderdeel | Scans | Zo leg je het |
|---|---|---|
| LP-hoes (voor of achter) | 4 | Elke hoek één keer. Elke scan toont twee buitenranden met achtergrond erlangs. |
| Uitklap (binnenkant) | 6 | Twee rijen van drie, van links naar rechts. |
| Insert of tekstvel | 4 | Als een hoes. |
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
