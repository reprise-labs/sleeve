# 0.4.9 — Kleurkopieën naast de scans en rode vinylkanten

- Kleurkopieën worden in de map van de gekozen beelden opgeslagen met `_kleur.png`; bestaande bestanden blijven behouden en krijgen bij herhaling een volgnummer.
- Geen aparte Kleurvoorstellen-map of mapkeuze voor kleurcorrectie meer.
- Alleen de nieuw gemaakte kopieën worden als kleurresultaat gecontroleerd. Scanmetadata blijft behouden; kleurgeschiedenis staat in een verborgen `.sleeve`-submap.
- Rode vinylplaten: etiketranden worden ook op kleurverschil herkend. Een contrastrijke tweede tekstlezing voorkomt dat bijna identieke A/B-labels in één groep belanden.
- De kleurworkflowtest vergelijkt genormaliseerde paden en rapporteert fouten zonder een crashmelding. Testbeelden worden naar een eigen testmap gekopieerd.

# Changelog

## 0.4.8 — prerelease, 6 November 2026

- Keep mapped work/output files visible to the scratch scheduler through repair and PNG encoding, after source maps have closed. Other workers can wait for those buffers to release space instead of failing prematurely.
- Exclude a worker’s own output activity from its wait condition, avoiding self-waits; stale claims and genuinely insufficient space remain handled.
- Show disk-space amounts in decimal GB, matching Finder.
- Present processing errors before opening review; preserve partial outputs for inspection.
- Image-processing calculations and output resolution are unchanged. Targeted cross-process disk regression checks and image tests passed. This hotfix is provided for the user’s FIRE practice test; the full FIRE timing remains the measured 0.4.7 result.

## 0.4.7 — prerelease, 6 November 2026

- Process separate components concurrently with a shared memory budget; start the largest group first and preserve original grouping, source identities and final roles.
- Reuse work previews only at the exact requested scale, with the same colour conversion and an unchanged source fingerprint. Remove consumed temporary previews.
- Store light-correction planes compactly and composite in bands. Stream full-resolution sources and use mapped output buffers.
- Turn covers before the first PNG save. Transfer merged discs to the cutting stage through lossless, uncompressed TIFF files.
- Coordinate native scratch reservations across workers; wait for live renderers to release space, while still rejecting genuinely insufficient space.
- Report component-specific progress, elapsed time and the number of active components. Cancellation stops isolated workers and their descendants.
- Honour an explicitly selected single-image role before attempting automatic disc detection.

Measured FIRE run: 28 scans to six full-resolution images in 11 minutes 23 seconds including file checks, without the separate colour pass. All six files exactly match the verified faster control run.

Output resolution is retained. Timing, pixel comparisons and test limitations are documented in TESTS.md. This is a prerelease tested on one Apple M1 Mac with 8 GB RAM.

## 0.4.6 — local test build

- Accelerate broad transition filtering, share preview decoding and reduce redundant writes during light correction.
- Remove full-size RGB copies during source decoding and cap image-worker thread counts.
- Complete FIRE measurement: 28 scans to six full-resolution images in 28 minutes 43 seconds, including file checks, without the separate colour-correction step.
