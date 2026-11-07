import SwiftUI

struct StudioColourControls:View {
    @ObservedObject var model:StudioModel
    var body:some View {
        VStack(alignment:.leading,spacing:14) {
            Text("1 · Choose what to adjust").font(.headline)
            Picker("Image type",selection:Binding(get:{model.colourScope},set:{model.chooseColourKind($0)})) {Text("Vinyl records").tag("vinyl");Text("Cover").tag("photo")}.pickerStyle(.segmented).labelsHidden()
            Text(model.colourScope=="vinyl" ? "Check the vinyl sides. The same color reference is used on all checked sides; labels are kept." : "Choose one cover and a photo of that same cover.").font(.caption).foregroundStyle(.secondary)
            if model.colourCandidates.isEmpty {Text("First add the cut-out records or a finished cover.").font(.caption).foregroundStyle(.secondary)}
            ForEach(model.colourCandidates) {item in
                HStack(spacing:8) {
                    Toggle(isOn:Binding(get:{model.colourSelection.contains(item.id)},set:{model.setColourTarget(item.id,$0)})) {
                        HStack {
                            StudioThumbnail(url:item.url,maxPixel:130).frame(width:42,height:42)
                            VStack(alignment:.leading,spacing:3) {Text(partLabel(item.part)).fontWeight(.semibold);Text(item.title).font(.system(size:10)).lineLimit(1).truncationMode(.middle)}
                        }
                    }
                    Button{model.showResults=false;model.selectedID=item.id} label:{Image(systemName:"eye")}.buttonStyle(.plain).help("View This Original")
                }
            }
            if model.colourScope=="vinyl" && model.colourCandidates.count>1 {Button("Select All Vinyl Sides"){model.resetColourSelection()}.font(.caption)}
            Text(model.colourScope=="vinyl" ? "\(model.colourTargets.count) vinyl sides checked · covers are not adjusted" : "\(model.colourTargets.count) cover selected").font(.caption).fontWeight(.semibold).foregroundStyle(studioAccent)
            Divider()
            Text("2 · Choose the desired color").font(.headline)
            TextField("Discogs link of this release",text:Binding(get:{model.discogs},set:{model.discogs=$0;model.references=[];if model.referenceFromDiscogs {model.referenceURL=nil}})).textFieldStyle(.roundedBorder)
            Button("Fetch Photos from Discogs"){model.loadReferences()}.disabled(model.discogs.isEmpty)
            Button("Choose Your Own Reference Photo…"){model.chooseReference()}
            Text(model.colourScope=="vinyl" ? "Click the full record with the desired color, not a label close-up." : "Click the same cover as the selected scan; don't use a photo of a record here.").font(.caption).foregroundStyle(.secondary)
            LazyVGrid(columns:[GridItem(.adaptive(minimum:65))]) {
                ForEach(model.references) {ref in
                    Button{model.referenceURL=ref.url;model.referenceFromDiscogs=true} label:{StudioThumbnail(url:ref.url,maxPixel:180).frame(height:65).padding(3).background(Color.white).overlay(RoundedRectangle(cornerRadius:5).stroke(model.referenceURL==ref.url ? studioAccent : .clear,lineWidth:3))}.buttonStyle(.plain).accessibilityLabel("Use "+ref.title+" as color reference")
                }
            }
            if let ref=model.referenceURL {
                HStack {StudioThumbnail(url:ref,maxPixel:180).frame(width:55,height:55);Text("Chosen color reference").font(.caption).fontWeight(.semibold).foregroundStyle(studioAccent)}
            } else {Text("No color reference chosen yet").font(.caption).foregroundStyle(.secondary)}
            if model.colourScope=="vinyl" {
                HStack {Text("Strength of color correction");Spacer();Text("\(Int(model.strength*100))%").monospacedDigit()}.font(.caption)
                Slider(value:$model.strength,in:0...1)
            }
            Text("3 · Make the new colors").font(.headline)
            Text("Use the big button below. You'll then see the saved new color copies and can compare them with the originals.").font(.caption).foregroundStyle(.secondary)
        }.font(.system(size:12)).disabled(model.busy)
    }
}

struct StudioColourResultHeader:View {
    @ObservedObject var model:StudioModel
    var body:some View {
        VStack(alignment:.leading,spacing:8) {
            if model.showResults {
                HStack {Label(model.busy ? "Making new colors…" : model.colourResults.contains(where:{$0.partial}) ? "Color step not fully finished" : "New color copies saved",systemImage:model.colourResults.contains(where:{$0.partial}) ? "exclamationmark.triangle" : model.busy ? "hourglass" : "checkmark.circle").fontWeight(.semibold);Spacer();Text("\(model.colourResults.count) images")}.font(.system(size:13)).foregroundStyle(model.colourResults.contains(where:{$0.partial}) ? Color.orange : studioAccent)
                if model.beforeURL != nil {
                    Picker("View",selection:Binding(get:{model.compare==0 ? "after" : model.compare==1 ? "before" : "compare"},set:{model.compare=$0=="after" ? 0 : $0=="before" ? 1 : 0.5})) {Text("Original").tag("before");Text("Compare").tag("compare");Text("New color").tag("after")}.pickerStyle(.segmented)
                    Text(model.compare==0 ? "This is the saved new color." : model.compare==1 ? "You're viewing the original; the new color copy is saved separately." : "Original on the left, new color on the right. Slide to compare.").font(.caption).foregroundStyle(.secondary)
                }
                HStack {Button("Show This Color File in Finder"){model.revealOutput()};Button("Review color copies"){model.showReview=true}}.font(.caption).disabled(model.busy)
            } else {
                Label("You're viewing an original for this color step",systemImage:"photo").font(.system(size:12,weight:.semibold))
                if !model.outputs.isEmpty {Button("View the saved new colors"){model.selectList(true);model.compare=0}.font(.caption)}
            }
        }.padding(12).frame(maxWidth:.infinity,alignment:.leading).background(studioAccent.opacity(0.08),in:RoundedRectangle(cornerRadius:9))
    }
}
