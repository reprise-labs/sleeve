import SwiftUI

/// Hulp in de app: de scanwijzer en wat een twijfelmelding betekent, in gewone taal.
/// Elke melding van Sleeve wijst naar één onderwerp (helpTopic(for:)); in de Final Check klapt
/// "How do I fix this?" dat onderwerp open onder de melding.
struct HelpTopic: Identifiable {
    let id: String
    let title: String
    let meaning: String
    let fix: [String]
}

let helpTopics: [HelpTopic] = [
    HelpTopic(id:"not-scanned", title:"“not scanned: … mm2”",
              meaning:"A piece of the part is on none of the scans, so Sleeve can't show it. The message says how big the hole is and where it is (for example top-left).",
              fix:["Scan that corner again, with at least 5 cm overlap with the scans next to it.",
                   "Keep the part about 1 cm away from the edge of the glass: along the glass edge the light falls off.",
                   "Put the new scan in the same slot and process the part again (Reprocess Part…)."]),
    HelpTopic(id:"record-rim", title:"“… directions more than 0.75 mm off the circle” (record)",
              meaning:"A record is round. Sleeve measures its edge in 72 directions; in some directions the edge it found is not on the circle. Usually the edge can't be seen there: light vinyl on the white lid, or translucent vinyl that lets the lid shine through.",
              fix:["Light or white opaque vinyl: put a dark or coloured sheet between the record and the lid, and scan again.",
                   "Translucent vinyl (clear, see-through blue or green): a dark sheet colours the record. Use a light, coloured sheet for now; a dedicated method is coming.",
                   "Black vinyl: the white lid is fine. Check for dust or a scratch right on the edge.",
                   "If the record looks fine to you, choose ‘Keep as it is’."]),
    HelpTopic(id:"record-edge-missing", title:"“the edge of the record could not be measured anywhere”",
              meaning:"Sleeve could not find the edge of the record in any direction. Often the resolution stored in the scan file doesn't match the real size, so the record looks too big or too small.",
              fix:["Let the scan software store the resolution in the file (it does by default) and use one resolution for the whole release.",
                   "Make sure every scan shows the outer edge of the record with background next to it."]),
    HelpTopic(id:"centre-hole", title:"“centre hole …”",
              meaning:"The hole in the middle couldn't be measured clearly (label colour close to the background, or the hole covered). Sleeve then cuts the standard size (7.24 mm for an LP).",
              fix:["Usually nothing to do: check the hole in the image.",
                   "If it looks wrong, use Adjust Crop… in the Final Check."]),
    HelpTopic(id:"front-back", title:"“front … and back … differ”",
              meaning:"Front and back are the same sleeve, so they must be the same size. One of the two was cut on a print edge (a border or band printed near the edge) or didn't lie flat.",
              fix:["Put a contrasting sheet behind the sleeve, so the real paper edge is visible all around.",
                   "Press the lid down, especially along the edges.",
                   "Look at both images: the one that is too small lost a strip; scan that side again."]),
    HelpTopic(id:"insert-size", title:"“this insert is … another is …: almost the same”",
              meaning:"Two inserts are almost, but not exactly, the same size. Two sides of one sheet are the same size, so one side was probably cut slightly differently.",
              fix:["Check the smaller one for a missing strip along an edge.",
                   "If they really are different sheets, choose ‘Keep as it is’."]),
    HelpTopic(id:"packaging", title:"“measured … but this packaging is …”",
              meaning:"The size Sleeve measured doesn't fit the packaging you chose (for example a jewel case card that is really a slim jewel or digipak card).",
              fix:["Check the packaging in the release details and process again.",
                   "If the size is right and the packaging is unusual, choose ‘Keep as it is’."]),
    HelpTopic(id:"upright", title:"“which way is up”",
              meaning:"Sleeve turns an image upright only on facts: text from the release that it can read, or a Discogs photo that matches. Neither was found here. This is not a scanning fault.",
              fix:["Choose the right turn yourself (90°, 180° or 270°). Sleeve remembers it for these scans.",
                   "With a Discogs link Sleeve can usually do it by itself."]),
    HelpTopic(id:"title-only", title:"“the label was set straight on the title only”",
              meaning:"On a record label Sleeve read only the title, not the tracklist. A title is sometimes printed at an angle, so this is not certain enough.",
              fix:["Look at the label: if it is straight, choose ‘Keep as it is’; otherwise choose the turn."]),
    HelpTopic(id:"side-letter", title:"“the label says side B, the slot says A”",
              meaning:"Sleeve read the side letter on the label and it differs from the slot you (or Sleeve) put the scans in.",
              fix:["Open Arrange Scans and swap the two sides, then process again."]),
    HelpTopic(id:"left-out", title:"“… was left out: it shares no print with the other scans”",
              meaning:"A partial scan couldn't be placed: it has no print in common with the other scans and no paper edges to place it on.",
              fix:["Scan that corner again with more overlap (at least 5 cm) with a neighbouring scan.",
                   "Put a contrasting sheet behind it, so its paper edges are visible."]),
    HelpTopic(id:"no-dpi", title:"“the scan has no resolution (dpi) stored”",
              meaning:"Sizes are measured in millimetres, so Sleeve needs the resolution stored in the file. Without it, 300 dpi is assumed.",
              fix:["Let the scan software store the resolution (it does by default), or export again as PNG or TIFF."]),
    HelpTopic(id:"not-gatefold", title:"“this is not an opened gatefold sleeve”",
              meaning:"The ‘Inside’ slot is only for an opened gatefold (two panels, about 62 × 31 cm).",
              fix:["Put a loose sheet or a booklet page in an ‘Insert’ slot instead."]),
    HelpTopic(id:"hung", title:"“stopped after … minutes without a result”",
              meaning:"Processing this part took far too long and was stopped; the other parts went on.",
              fix:["Process this part again (Reprocess Part…). If it happens again, save the log and send it."]),
    HelpTopic(id:"edge-unseen", title:"“the left edge could not be seen …”",
              meaning:"Sleeve finds a sleeve or card by its four edges. Along this side the edge was not visible for most of its length (for example a white sleeve on the white lid), so Sleeve placed it by the known size of the part. It is probably right, but not measured. The side named is as it lay on the scanner, before turning upright.",
              fix:["Put a contrasting sheet behind the part (a coloured or dark sheet) and scan that side again.",
                   "Keep the edge at least 1 cm from the edge of the glass.",
                   "If the result looks right to you, choose ‘Keep as it is’."]),
    HelpTopic(id:"disc-unseen", title:"“the edge of the record could not be seen at N of 36 places”",
              meaning:"Sleeve looks for the edge of a record or CD in 36 directions around it. In some of them the edge was not visible (light vinyl on the white lid, the lid shining through translucent vinyl, or the edge too close to the edge of the glass). The circle is measured on the places where it was seen, so the cut is usually right.",
              fix:["Light or white vinyl: put a dark or coloured sheet behind it and scan again.",
                   "Keep the edge of the record at least 1 cm from the edge of the glass in every scan.",
                   "If the result looks right to you, choose ‘Keep as it is’."]),
    HelpTopic(id:"no-sticker", title:"“no sticker found”",
              meaning:"Sleeve looks for a closed rectangle with rounded corners (the printed frame of a Music On Vinyl sticker, or the sticker's own edge) or a round edge all around. Neither was found in this scan.",
              fix:["Scan the sticker well inside the glass, with the plastic sleeve flat and the lid closed.",
                   "Check that this scan is in the Sticker slot and that the whole sticker is on it."]),
    HelpTopic(id:"sticker-edge", title:"“the edge of the sticker is not equally visible on all four sides”",
              meaning:"The printed frame was found, but the sticker's own edge around it could not be seen on every side (for example a gold sticker on a gold or yellow sleeve).",
              fix:["Put a contrasting sheet behind the plastic sleeve and scan again.",
                   "If the result looks right to you, choose ‘Keep as it is’."]),
    HelpTopic(id:"discogs", title:"“… could not be read from Discogs”",
              meaning:"Discogs couldn't be reached. Sleeve went on with what it knows; a name or the upright position may be missing.",
              fix:["Check the internet connection and process again later."]),
]

/// Welk onderwerp hoort bij deze melding van Sleeve (op de vaste beginwoorden van de melding).
func helpTopic(for reason: String) -> String? {
    let r = reason.lowercased()
    if r.hasPrefix("front ") && r.contains("differ") {return "front-back"}
    if r.hasPrefix("measured ") && r.contains("packaging") {return "packaging"}
    let rules: [(String, String)] = [
        ("not scanned", "not-scanned"), ("directions more than", "record-rim"),
        ("could not be measured anywhere", "record-edge-missing"), ("centre hole", "centre-hole"),
        ("this insert is", "insert-size"),
        ("the label was set straight on the title only", "title-only"),
        ("which way is up", "upright"), ("the label says side", "side-letter"),
        ("was left out", "left-out"), ("no resolution", "no-dpi"), ("not an opened gatefold", "not-gatefold"),
        ("stopped after", "hung"), ("no sticker found", "no-sticker"), ("could not be seen along", "edge-unseen"), ("could not be seen at", "disc-unseen"), ("edge of the sticker", "sticker-edge"),
        ("round edge is visible", "sticker-edge"), ("discogs", "discogs"),
    ]
    return rules.first(where: {r.contains($0.0)})?.1
}

/// Onder een twijfelmelding: "How do I fix this?" klapt de uitleg open.
struct HelpForReason: View {
    let reason: String
    @State private var open = false
    var body: some View {
        if let id = helpTopic(for: reason), let topic = helpTopics.first(where: {$0.id == id}) {
            VStack(alignment:.leading, spacing:4) {
                Button(open ? "Hide help" : "How do I fix this?") {open.toggle()}
                    .buttonStyle(.link).font(.caption)
                if open {HelpTopicBody(topic: topic, compact: true)}
            }.padding(.leading, 10)
        }
    }
}

struct HelpTopicBody: View {
    let topic: HelpTopic
    var compact = false
    var body: some View {
        VStack(alignment:.leading, spacing:6) {
            Text(topic.meaning).font(compact ? .caption : .callout).fixedSize(horizontal:false, vertical:true)
            ForEach(Array(topic.fix.enumerated()), id:\.offset) {_, step in
                HStack(alignment:.firstTextBaseline, spacing:6) {
                    Image(systemName:"arrow.right.circle").foregroundStyle(studioAccent)
                    Text(step).fixedSize(horizontal:false, vertical:true)
                }.font(compact ? .caption : .callout)
            }
        }.padding(compact ? 8 : 0)
        .background(compact ? studioAccent.opacity(0.06) : .clear, in: RoundedRectangle(cornerRadius:6))
    }
}

/// Het hulpvenster: scanwijzer, indelen en de meldingen.
struct StudioHelpView: View {
    @ObservedObject var model: StudioModel
    private let rules: [(String, String)] = [
        ("The background differs from the edge of the part.",
         "Light parts (white sleeve, white card, white or yellow opaque vinyl): put a plain coloured or dark sheet between the part and the lid; a purple sheet works well. Dark parts (black vinyl, dark sleeve) and CDs: the normal white lid. If you can't see the edge all around in the preview, Sleeve can't either."),
        ("Not against the edge of the glass.",
         "Keep the part at least 1 cm from the glass edge on every side where an outer edge is in view. Along the glass edge the light falls off and a sleeve often doesn't lie flat."),
        ("Sleeve: slide, don't turn. Record: a quarter turn is fine.",
         "A 31 cm sleeve fits an A4 glass in four positions without turning: slide it one corner further each time. A record may be turned a quarter each time."),
        ("Plenty of overlap.",
         "Every partial scan shares at least 5 cm with its neighbours. Together they show the whole part with a strip of background around it."),
        ("Lid closed and pressed down; one setting per release.",
         "Press near the edges and near small text. Use one resolution per release and let the scan software store it in the file."),
    ]
    private let parts: [(String, String, String)] = [
        ("LP sleeve (front or back)", "4", "Each corner once; every scan shows two outer edges with background."),
        ("Gatefold, opened (Inside)", "6", "Two rows of three, left to right."),
        ("Insert or lyric sheet (30 cm)", "4 per side", "Like a sleeve; each side in its own Insert slot."),
        ("Booklet page (29 cm)", "2 per page", "Left half, then right half; each page its own Insert slot."),
        ("Record side", "4", "Each scan a quarter of the record, with the edge and background; a quarter turn is fine."),
        ("CD booklet, card, back card", "1", "Straight (within a few degrees), background all around."),
        ("CD", "1", "In the middle of the glass, printed side down."),
        ("Sticker", "1", "The sticker on its plastic sleeve, well inside the glass; put the scan in a Sticker slot."),
    ]
    var body: some View {
        VStack(alignment:.leading, spacing:0) {
            HStack {
                Text("Sleeve Help").font(.system(size:24, weight:.semibold, design:.serif))
                Spacer()
                Button("Close") {model.panel = nil}.keyboardShortcut(.cancelAction)
            }.padding(20)
            Divider()
            ScrollViewReader {proxy in
                ScrollView {
                    VStack(alignment:.leading, spacing:22) {
                        section("Scanning so Sleeve doesn't have to guess") {
                            Text("Sleeve works on facts: edges that are really in the scan and sizes that are really measured. What isn't on the scan can't be measured, and then you get ‘In doubt’.").font(.callout).foregroundStyle(.secondary)
                            ForEach(Array(rules.enumerated()), id:\.offset) {i, rule in
                                HStack(alignment:.top, spacing:10) {
                                    Text("\(i + 1)").font(.system(size:15, weight:.bold, design:.serif)).foregroundStyle(studioAccent).frame(width:18)
                                    VStack(alignment:.leading, spacing:3) {
                                        Text(rule.0).font(.callout.weight(.semibold))
                                        Text(rule.1).font(.callout).fixedSize(horizontal:false, vertical:true)
                                    }
                                }
                            }
                        }
                        section("How many scans per part") {
                            Grid(alignment:.leading, horizontalSpacing:14, verticalSpacing:6) {
                                ForEach(parts, id:\.0) {p in
                                    GridRow {
                                        Text(p.0).font(.callout.weight(.medium))
                                        Text(p.1).font(.callout.monospacedDigit())
                                        Text(p.2).font(.callout).foregroundStyle(.secondary).fixedSize(horizontal:false, vertical:true)
                                    }
                                }
                            }
                        }
                        section("Arranging the scans") {
                            Text("After you confirm the release, Sleeve puts the scans of one part together in a slot: scans that share print and follow each other in file order. It names a slot only on a fact: the barcode (Back), the Discogs cover photo (Front), the rim of a record (Side A, B … in scan order; the label is checked after processing), a 120 mm disc (CD), the second 150 mm card of a jewel case once the back is known (Inlay), and a small shape with rounded corners or a circle on an otherwise empty scan (Sticker). Once front and back are found, another sheet is an Insert, or the Inside when it is a whole opened gatefold. A slot without a fact says ‘choose the part’. A part that came in two slots: use the arrow on a slot to move all its scans at once.").font(.callout).fixedSize(horizontal:false, vertical:true)
                            Text("Tip: scan one part after the other (front, back, side A, side B …). If a file name ends in the part (…_front.png, …_cd.png), it goes straight into that slot.").font(.callout).foregroundStyle(.secondary).fixedSize(horizontal:false, vertical:true)
                        }
                        section("Stickers") {
                            Text("Scan the sticker on its own plastic sleeve: one scan, the sticker well inside the glass, the plastic lying flat and the lid closed. Sleeve finds the printed frame of a Music On Vinyl sticker and its edge around it, a strip without a frame by its own edge, or a round sticker by its round edge, and cuts it out with transparent corners. It is set upright on the text of the release (artist, title). Dark moss-green stickers (from 2025) can't be read by macOS: choose the turn yourself.").font(.callout).fixedSize(horizontal:false, vertical:true)
                        }
                        section("When Sleeve is in doubt") {
                            Text("‘In doubt’ means a fact couldn't be checked. Sleeve shows the reason and what you can choose; it remembers your choice for these scans.").font(.callout).foregroundStyle(.secondary)
                            ForEach(helpTopics) {topic in
                                VStack(alignment:.leading, spacing:6) {
                                    Text(topic.title).font(.callout.weight(.semibold))
                                    HelpTopicBody(topic: topic)
                                }.padding(12).frame(maxWidth:.infinity, alignment:.leading)
                                .background(model.helpTopic == topic.id ? studioAccent.opacity(0.10) : Color(nsColor:.controlBackgroundColor), in: RoundedRectangle(cornerRadius:8))
                                .id(topic.id)
                            }
                        }
                    }.padding(24).frame(maxWidth:760, alignment:.leading)
                }
                .onAppear {if let id = model.helpTopic {DispatchQueue.main.asyncAfter(deadline:.now() + 0.2) {withAnimation {proxy.scrollTo(id, anchor:.top)}}}}
            }
        }.frame(minWidth:720, idealWidth:820, minHeight:600, idealHeight:760).tint(studioAccent)
    }
    @ViewBuilder func section<Content: View>(_ title: String, @ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment:.leading, spacing:10) {
            Text(title.uppercased()).font(.system(size:11, weight:.bold)).tracking(1.4).foregroundStyle(.secondary)
            content()
        }
    }
}
