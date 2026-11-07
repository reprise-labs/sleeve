# Sleeve

A macOS app for scans of your music collection: crop CDs and records, stitch partial
scans together, suggest colour corrections later on and take file names from a Discogs
release. With a queue, projects and a final review.

![Sleeve](Artwork/Sleeve.png)

## Test version 0.4.8

New in this test version: disk-space management keeps tracking temporary output buffers
while saving, so other parts can wait for space to free up. After an error, the error
message appears before a final review is opened. Image processing and output resolution
are unchanged.
Measurements and quality checks are in [TESTS.md](Documentation/TESTS.md);
changes are in [CHANGELOG.md](Documentation/CHANGELOG.md).
Also available: Discogs release suggestions and a separate colour step for sleeves and
records. Also available: adjusting round crops yourself, reprocessing a single part, and
the memory fix for large FIRE scans.
This version is a preview; download the full app package from Releases.

Apple Silicon, macOS 14 or later. The app is signed locally and not yet notarized by
Apple. This preview needs a one-time installation of Python image components; they are not
yet bundled in the app. The interface is in Dutch; menu and button names below are given
as they appear in the app. It has been tested on one Mac; a clean, different Mac has not
been tested yet.

## Installation

Download the full app package from [Releases](https://github.com/reprise-labs/sleeve/releases).

1. Unzip the full download package and move `Sleeve.app` to your Applications folder.
2. Run `Installeer beeldonderdelen.command` from the unzipped package.
   Keep the included `scripts` folder and `requirements.txt` next to it.
   This creates a separate Python environment under
   `~/Library/Application Support/com.repriselabs.Sleeve/Runtime`.
3. Open Sleeve. If the installer can't find a suitable Python, install
   Python 3.11 from [python.org](https://www.python.org/downloads/macos/),
   or with Homebrew: `brew install python@3.11`. Then run the installer again.

On the original development Mac the existing Python installation can be used as well.
For other Macs, the separate environment is the intended route.
The installer needs internet access to download NumPy, Pillow and OpenCV.

## Usage

- **Processing scans (Scans verwerken):** select one release from one source folder.
  Process CD and vinyl separately; mixed CD/vinyl input has not been tested. Mark label
  close-ups as reference. Every run gets a new subfolder.
- **Discogs:** names and orientation can be chosen separately. Check that it's the right
  release. For vinyl colour, deliberately use a photo of the full record via
  Kleur aanpassen.
- **Adjusting colour (Kleur aanpassen):** can also be redone later. The vinyl method
  protects the label and transparency. The colour is a suggestion, not an exact
  measurement.
- **Renaming (Namen aanpassen):** check the suggestion. Sleeve creates independent copies.
- **Queue:** set up a job, mark it ready and add other jobs if you like. The list
  processes jobs one after another, each with its own settings. An error or interruption
  pauses the list. Nothing is repeated automatically after reopening.
- **Projects:** save as `.sleeveproject` and reopen later via the Project menu.
  Older `.anoukproject` files can be opened too. Reference photos, settings, history and
  reviews are saved. Source and result images stay linked to their location: leave those
  folders where they are.
- **Final review:** legibility and round crops are measured. Judge completeness, file
  names and colour yourself. Those three points are never approved automatically.
  Changed files lose their earlier approval.

Progress reflects the worker messages available within a step. For steps without
measurable progress an activity indicator appears, not a made-up total.

## Privacy and connections

Image processing happens locally, without an AI API. For Discogs, public data and
reference photos are fetched; scans are never uploaded. A firewall such as Little Snitch
may ask for permission again for a new app version, for `api.discogs.com` and
`i.discogs.com`.

The included sample records are synthetic. Personal scans, test projects and local
settings are not part of this repository.

## Building

Xcode Command Line Tools and a suitable Apple Silicon Mac are required:

```sh
zsh build.sh
```

The OCR helper is compiled during the build, so the app doesn't have to modify files
inside its own signed bundle.

## Testing

```sh
zsh scripts/check.sh
```

The checks create temporary files and test image shape, damaged files,
label/transparency, progress, stopping, projects and the queue. Large real album scans
and the native windows have additionally been tested locally; synthetic checks don't
prove that every possible scan is processed correctly.

## Reprise Labs

Sleeve is a separate project alongside [Reprise](https://github.com/reprise-labs/reprise).
The two apps have their own versions and downloads. This repository doesn't change Reprise.

## New: adjusting a crop

Select a loaded CD or vinyl image and choose **Ronde uitsnede bijstellen…** (adjust round
crop). Drag the circle or use the sliders; the plus/minus buttons move the centre or the
diameter one pixel at a time. **Toon uitgeknipt voorbeeld** (show cropped preview) shows
the result straight away. A circle outside the source can't be saved.

Choose **Kies oorspronkelijke scan…** (choose original scan) if an earlier crop already
removed too much. The new crop stays a true circle, without stretching the image. Only
the outer edge changes: the centre hole and any other holes stay as in the source. Pixels
inside the circle, DPI and ICC profile are preserved. The outermost edge gets a soft
one-pixel transition.

**Bewaar nieuwe uitsnede** (save new crop) creates a new PNG and replaces only the chosen
result in the project. The source and the previous attempt stay on disk. The new version
needs a final review again.

## New: reprocessing a single part

Select a result and choose **Dit onderdeel opnieuw verwerken…** (reprocess this part), or
choose **Onderdeel opnieuw…** in the final review. Check the ticked source images; if it
isn't known which scans belong to the part, choose them yourself. Use one source folder.
The selection is processed as one part, for example just side B. Exactly one new result
must come out; otherwise the previous version stays active. On an error or cancellation
the other results and their reviews are kept.

The original Discogs settings are taken from the edit history when available. Adjust
vinyl colour separately afterwards if needed. The chosen sources are saved for a next
attempt.

For a correction or retry, the existing before/after slider shows **the previous attempt
against the new attempt**. Via **Eerdere bewerkingen** (earlier edits) you can look back
at an older state. Projects keep this history and its references, so leave the folders
with previous versions in place as well.


## New in 0.4.2: process first, choose colour afterwards

When processing scans, Discogs is now only used for file names and orientation.
A saved old checkbox for sleeve colour no longer turns on colour correction.
For a sleeve, choose Kleur aanpassen → Hoes / ander beeld · passende foto later on.
For vinyl, the separate method that preserves the label remains available.
Look at and compare the suggestion before using it further.

## New in 0.4.2: possible Discogs releases

After loading scans without a release link, Sleeve reads text and barcodes locally from
at most six downscaled images. As soon as a usable barcode is found, it stops reading.
Only search terms go to Discogs, never images.
Bekijk releasevoorstellen (view release suggestions) shows at most five possible
releases, with format, year, country, catalogue number and any variant/colour. A shared
barcode can match several pressings. Only Gebruik deze uitgave (use this release) fills in
the link. The search data can be edited; searching can be stopped and resumed.
An existing release link is never replaced automatically. You can also search Discogs
yourself and paste a link. Recognition can produce incomplete or misread text and doesn't
confirm the exact pressing.


## Parts and partial scans cropped differently

Scans with the same DPI keep the same physical scale when grouped, even if one part was
cropped smaller. Unknown provisional results are called Nog te bepalen (to be
determined). An interrupted naming step doesn't turn every image into Voorkant (front).
Known parts and their source images are tracked for every result.
Front and back can be suggested using the matching Discogs sleeve photo and barcode;
always check the names in the final review.


## New in 0.4.3: clear progress

A large progress panel shows the current part, the number of parts processed, the
current step, the total time and the time of the current step.
Preparing, comparing scans, matching exposure between partial scans and finishing the
seams also report progress. Bars and percentages are based on counted images,
comparisons or processed image strips.
For saving, text recognition and Discogs comparison no percentage is guessed: you see an
activity bar and the name and duration of that step.
A phase percentage is not a percentage of the whole job, nor a time estimate.


## New in 0.4.4: a clear colour step and multiple vinyl sides

1. Open Kleur aanpassen and add the finished images.
2. Choose Vinylplaten: tick sides A and B. Sleeves are kept separate.
3. Fetch the Discogs photos and click the full record with the desired colour.
4. Click Maak nieuwe kleur voor 2 vinylkanten (make new colour for 2 vinyl sides).

Both new colour copies are saved straight away and shown together.
No separate Apply button is needed. The Origineel, Vergelijken and Nieuwe kleur buttons
make clear what you're looking at. The new colour is fully visible by default; the
comparison slider runs from original to new colour.
The final review only opens when you choose it. Via Toon dit kleurbestand in Finder
(show this colour file in Finder) you find exactly the selected file.

An earlier colour copy of A stays in view if you later reprocess only B. In the Namen
aanpassen step the sleeves and both colour copies stay available together. Your ticked
images are saved in projects.
For a sleeve, choose Hoes (sleeve) and one matching sleeve reference. When switching
between sleeve and vinyl you need to choose a matching reference photo again.
