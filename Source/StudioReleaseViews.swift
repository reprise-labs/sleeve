import SwiftUI
import AppKit

/// "Which release is this?" – verschijnt na het inslepen. Kiezen, controleren, bevestigen.
struct ReleaseConfirmSheet:View {
    @ObservedObject var model:StudioModel
    var body:some View {
        VStack(alignment:.leading,spacing:0) {
            HStack {
                Text(model.releaseInfo==nil ? "Which release is this?" : "Are these details correct?").font(.system(size:24,weight:.semibold,design:.serif))
                Spacer()
                Button("Skip"){model.skipRelease()}.help("For a release that isn't on Discogs: choose CD or vinyl and the packaging yourself.")
            }.padding(22)
            Divider()
            ScrollView {
                VStack(alignment:.leading,spacing:16) {
                    if !model.releaseStatus.isEmpty {Text(model.releaseStatus).font(.callout).foregroundStyle(.secondary)}
                    if let info=model.releaseInfo {details(info)} else {chooser}
                }.padding(22)
            }
            Divider()
            HStack {
                if model.releaseLoading {ProgressView().controlSize(.small)}
                Spacer()
                if model.releaseInfo != nil {
                    Button("Other Release"){model.rejectRelease()}
                    Button("Yes, This Is Correct"){model.confirmRelease()}.keyboardShortcut(.defaultAction).buttonStyle(.borderedProminent)
                }
            }.padding(16)
        }.frame(width:720,height:740).tint(studioAccent)
    }
    var chooser:some View {
        VStack(alignment:.leading,spacing:12) {
            Text("Paste the Discogs link, or let Sleeve search with the barcode, catalog number and title on your scans.").font(.callout)
            HStack {
                TextField("https://www.discogs.com/release/…",text:$model.discogs).textFieldStyle(.roundedBorder)
                Button("Load"){model.loadReleaseInfo()}.disabled(model.discogs.trimmingCharacters(in:.whitespaces).isEmpty || model.releaseLoading)
            }
            Divider()
            ReleaseAdviceView(model:model)
        }
    }
    func details(_ info:ReleaseInfo)->some View {
        VStack(alignment:.leading,spacing:14) {
            HStack(spacing:10) {
                ForEach(info.thumbs ?? [],id:\.self) {path in
                    if let image=NSImage(contentsOfFile:path) {Image(nsImage:image).resizable().scaledToFit().frame(width:120,height:120).background(studioPaper,in:RoundedRectangle(cornerRadius:6))}
                }
            }
            Grid(alignment:.leading,horizontalSpacing:14,verticalSpacing:8) {
                row("Artist",info.artist);row("Title",info.title)
                GridRow {
                    Text("Year").foregroundStyle(.secondary)
                    HStack {
                        TextField("Year",text:$model.releaseYear).textFieldStyle(.roundedBorder).frame(width:80)
                        if model.releaseYear != info.year {Text("Discogs: \(info.year.isEmpty ? "none" : info.year)").font(.caption).foregroundStyle(.orange)}
                    }
                }
                row("Country",info.country);row("Label",info.label);row("Catalog number",info.catno)
                row("Format",info.formatText)
                if !info.colour.isEmpty {row("Color",info.colour)}
                GridRow {
                    Text("Packaging").foregroundStyle(.secondary)
                    VStack(alignment:.leading,spacing:4) {
                        Picker("Packaging",selection:$model.packaging) {
                            ForEach(packagingChoices.filter{info.format=="vinyl" ? ["sleeve","gatefold","unknown"].contains($0.0) : !["sleeve","gatefold"].contains($0.0)},id:\.0) {Text($0.1).tag($0.0)}
                        }.labelsHidden().frame(width:220)
                        Text(info.packagingFromDiscogs ? "From Discogs. Change it if your copy is different." : "Discogs doesn't say. Choose what you have.").font(.caption).foregroundStyle(info.packagingFromDiscogs ? Color.secondary : Color.orange)
                    }
                }
                row("Slots",info.slots.map{partLabel($0)}.joined(separator:", "))
            }
            if let url=URL(string:info.url) {Link("View on Discogs ↗",destination:url).font(.caption)}
            Text("Sleeve uses these details for the sizes (format and packaging) and the file names (year, title, label, color).").font(.caption).foregroundStyle(.secondary)
        }
    }
    func row(_ label:String,_ value:String)->some View {
        GridRow {Text(label).foregroundStyle(.secondary);Text(value.isEmpty ? "—" : value).textSelection(.enabled)}
    }
}
