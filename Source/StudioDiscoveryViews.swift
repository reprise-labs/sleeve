import SwiftUI

struct ReleaseAdviceView:View {
    @ObservedObject var model:StudioModel
    @State private var showSearch=true
    var body:some View {
        VStack(alignment:.leading,spacing:10) {
            HStack {
                Text("Which release is this?").font(.system(size:12,weight:.semibold))
                Spacer()
                if model.discovering {ProgressView().controlSize(.small)}
            }
            if !model.adviceStatus.isEmpty {Text(model.adviceStatus).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal:false,vertical:true)}
            if model.discovering {Button("Stop Search"){model.cancelReleaseAdvice()}.font(.caption)}
            DisclosureGroup("Check search details",isExpanded:$showSearch) {
                VStack(alignment:.leading,spacing:7) {
                    TextField("Artist",text:$model.adviceArtist).accessibilityLabel("Search artist")
                    TextField("Title",text:$model.adviceTitle).accessibilityLabel("Search title")
                    TextField("Barcode",text:$model.adviceBarcode).accessibilityLabel("Search barcode")
                    TextField("Catalog number",text:$model.adviceCatalog).accessibilityLabel("Search catalog number")
                    Picker("Format",selection:$model.adviceFormat) {Text("All formats").tag("");Text("Vinyl").tag("Vinyl");Text("Cd").tag("CD")}
                    Button("Find Release Suggestions"){model.findReleaseAdvice(recognize:false)}.disabled(model.inputs.isEmpty)
                    Button("Read Scans Again"){model.findReleaseAdvice(recognize:true)}.disabled(model.inputs.isEmpty)
                }.textFieldStyle(.roundedBorder).disabled(model.discovering).padding(.top,5)
            }
            ForEach(model.adviceCandidates) {candidate in
                VStack(alignment:.leading,spacing:5) {
                    Text(candidate.title).font(.system(size:12,weight:.semibold)).fixedSize(horizontal:false,vertical:true)
                    Text(candidate.detail).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal:false,vertical:true)
                    if !candidate.catno.isEmpty {Text("Catalog: "+candidate.catno).font(.caption).textSelection(.enabled)}
                    Text(candidate.reasons.joined(separator:" · ")).font(.caption).foregroundStyle(studioAccent).fixedSize(horizontal:false,vertical:true)
                    HStack {
                        Button("Use This Release"){model.chooseRelease(candidate)}
                        if let url=URL(string:candidate.url) {Link("View",destination:url)}
                    }.font(.caption)
                }.padding(10).frame(maxWidth:.infinity,alignment:.leading).background(studioAccent.opacity(0.06),in:RoundedRectangle(cornerRadius:7))
            }
            if let url=model.discogsSearchURL {Link("Search on Discogs ↗",destination:url).font(.caption)}
            Text("Suggestions, not confirmation. Check format, pressing and color in particular. Text recognition happens on your Mac; only search terms are sent to Discogs.").font(.caption).foregroundStyle(.secondary).fixedSize(horizontal:false,vertical:true)
        }.onChange(of:model.adviceStatus){if !model.discovering && model.adviceCandidates.isEmpty && !model.adviceStatus.isEmpty {showSearch=true}}
    }
}

struct ReleaseAdviceSheet:View {
    @ObservedObject var model:StudioModel
    var body:some View {
        VStack(spacing:0) {
            HStack {Text("Discogs · release suggestions").font(.title2);Spacer();Button("Close"){model.panel=nil}.keyboardShortcut(.cancelAction)}.padding(22)
            Divider()
            ScrollView {ReleaseAdviceView(model:model).padding(22)}
        }.frame(width:640,height:680).disabled(model.busy)
    }
}
