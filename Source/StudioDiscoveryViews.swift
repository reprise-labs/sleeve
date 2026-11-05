import SwiftUI

struct ReleaseAdviceView:View {
    @ObservedObject var model:StudioModel
    @State private var showSearch=true
    var body:some View {
        VStack(alignment:.leading,spacing:10) {
            HStack {
                Text("Welke uitgave is dit?").font(.system(size:12,weight:.semibold))
                Spacer()
                if model.discovering {ProgressView().controlSize(.small)}
            }
            if !model.adviceStatus.isEmpty {Text(model.adviceStatus).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal:false,vertical:true)}
            if model.discovering {Button("Stop zoeken"){model.cancelReleaseAdvice()}.font(.caption)}
            DisclosureGroup("Zoekgegevens controleren",isExpanded:$showSearch) {
                VStack(alignment:.leading,spacing:7) {
                    TextField("Artiest",text:$model.adviceArtist).accessibilityLabel("Zoekartiest")
                    TextField("Titel",text:$model.adviceTitle).accessibilityLabel("Zoektitel")
                    TextField("Barcode",text:$model.adviceBarcode).accessibilityLabel("Zoekbarcode")
                    TextField("Catalogusnummer",text:$model.adviceCatalog).accessibilityLabel("Zoekcatalogusnummer")
                    Picker("Formaat",selection:$model.adviceFormat) {Text("Alle formaten").tag("");Text("Vinyl").tag("Vinyl");Text("Cd").tag("CD")}
                    Button("Zoek releasevoorstellen"){model.findReleaseAdvice(recognize:false)}.disabled(model.inputs.isEmpty)
                    Button("Lees scans opnieuw"){model.findReleaseAdvice(recognize:true)}.disabled(model.inputs.isEmpty)
                }.textFieldStyle(.roundedBorder).disabled(model.discovering).padding(.top,5)
            }
            ForEach(model.adviceCandidates) {candidate in
                VStack(alignment:.leading,spacing:5) {
                    Text(candidate.title).font(.system(size:12,weight:.semibold)).fixedSize(horizontal:false,vertical:true)
                    Text(candidate.detail).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal:false,vertical:true)
                    if !candidate.catno.isEmpty {Text("Catalogus: "+candidate.catno).font(.caption).textSelection(.enabled)}
                    Text(candidate.reasons.joined(separator:" · ")).font(.caption).foregroundStyle(studioAccent).fixedSize(horizontal:false,vertical:true)
                    HStack {
                        Button("Gebruik deze uitgave"){model.chooseRelease(candidate)}
                        if let url=URL(string:candidate.url) {Link("Bekijk",destination:url)}
                    }.font(.caption)
                }.padding(10).frame(maxWidth:.infinity,alignment:.leading).background(studioAccent.opacity(0.06),in:RoundedRectangle(cornerRadius:7))
            }
            if let url=model.discogsSearchURL {Link("Zoek op Discogs ↗",destination:url).font(.caption)}
            Text("Suggesties, geen bevestiging. Controleer vooral formaat, persing en kleur. Tekstherkenning gebeurt op je Mac; alleen zoektermen gaan naar Discogs.").font(.caption).foregroundStyle(.secondary).fixedSize(horizontal:false,vertical:true)
        }.onChange(of:model.adviceStatus){if !model.discovering && model.adviceCandidates.isEmpty && !model.adviceStatus.isEmpty {showSearch=true}}
    }
}

struct ReleaseAdviceSheet:View {
    @ObservedObject var model:StudioModel
    var body:some View {
        VStack(spacing:0) {
            HStack {Text("Discogs · releasevoorstellen").font(.title2);Spacer();Button("Sluiten"){model.panel=nil}.keyboardShortcut(.cancelAction)}.padding(22)
            Divider()
            ScrollView {ReleaseAdviceView(model:model).padding(22)}
        }.frame(width:640,height:680).disabled(model.busy)
    }
}
