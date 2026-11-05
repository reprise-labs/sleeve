import SwiftUI

struct StudioColourControls:View {
    @ObservedObject var model:StudioModel
    var body:some View {
        VStack(alignment:.leading,spacing:14) {
            Text("1 · Kies wat je wilt aanpassen").font(.headline)
            Picker("Soort beeld",selection:Binding(get:{model.colourScope},set:{model.chooseColourKind($0)})) {Text("Vinylplaten").tag("vinyl");Text("Hoes").tag("photo")}.pickerStyle(.segmented).labelsHidden()
            Text(model.colourScope=="vinyl" ? "Vink de vinylkanten aan. Dezelfde kleurreferentie wordt op alle aangevinkte kanten gebruikt; etiketten blijven behouden." : "Kies één hoes en een foto van diezelfde hoes.").font(.caption).foregroundStyle(.secondary)
            if model.colourCandidates.isEmpty {Text("Voeg eerst de uitgeknipte platen of een afgewerkte hoes toe.").font(.caption).foregroundStyle(.secondary)}
            ForEach(model.colourCandidates) {item in
                HStack(spacing:8) {
                    Toggle(isOn:Binding(get:{model.colourSelection.contains(item.id)},set:{model.setColourTarget(item.id,$0)})) {
                        HStack {
                            StudioThumbnail(url:item.url,maxPixel:130).frame(width:42,height:42)
                            VStack(alignment:.leading,spacing:3) {Text(partLabel(item.part)).fontWeight(.semibold);Text(item.title).font(.system(size:10)).lineLimit(1).truncationMode(.middle)}
                        }
                    }
                    Button{model.showResults=false;model.selectedID=item.id} label:{Image(systemName:"eye")}.buttonStyle(.plain).help("Bekijk dit origineel")
                }
            }
            if model.colourScope=="vinyl" && model.colourCandidates.count>1 {Button("Selecteer alle vinylkanten"){model.resetColourSelection()}.font(.caption)}
            Text(model.colourScope=="vinyl" ? "\(model.colourTargets.count) vinylkanten aangevinkt · hoezen worden niet aangepast" : "\(model.colourTargets.count) hoes geselecteerd").font(.caption).fontWeight(.semibold).foregroundStyle(studioAccent)
            Divider()
            Text("2 · Kies de gewenste kleur").font(.headline)
            TextField("Discogs-link van deze uitgave",text:Binding(get:{model.discogs},set:{model.discogs=$0;model.references=[];if model.referenceFromDiscogs {model.referenceURL=nil}})).textFieldStyle(.roundedBorder)
            Button("Foto’s van Discogs ophalen"){model.loadReferences()}.disabled(model.discogs.isEmpty)
            Button("Kies een eigen referentiefoto…"){model.chooseReference()}
            Text(model.colourScope=="vinyl" ? "Klik op de volledige plaat met de gewenste kleur, niet op een etiketclose-up." : "Klik op dezelfde hoes als de geselecteerde scan; gebruik hier geen foto van een plaat.").font(.caption).foregroundStyle(.secondary)
            LazyVGrid(columns:[GridItem(.adaptive(minimum:65))]) {
                ForEach(model.references) {ref in
                    Button{model.referenceURL=ref.url;model.referenceFromDiscogs=true} label:{StudioThumbnail(url:ref.url,maxPixel:180).frame(height:65).padding(3).background(Color.white).overlay(RoundedRectangle(cornerRadius:5).stroke(model.referenceURL==ref.url ? studioAccent : .clear,lineWidth:3))}.buttonStyle(.plain).accessibilityLabel("Gebruik "+ref.title+" als kleurreferentie")
                }
            }
            if let ref=model.referenceURL {
                HStack {StudioThumbnail(url:ref,maxPixel:180).frame(width:55,height:55);Text("Gekozen kleurreferentie").font(.caption).fontWeight(.semibold).foregroundStyle(studioAccent)}
            } else {Text("Nog geen kleurreferentie gekozen").font(.caption).foregroundStyle(.secondary)}
            if model.colourScope=="vinyl" {
                HStack {Text("Sterkte van kleurcorrectie");Spacer();Text("\(Int(model.strength*100))%").monospacedDigit()}.font(.caption)
                Slider(value:$model.strength,in:0...1)
            }
            Text("3 · Maak de nieuwe kleuren").font(.headline)
            Text("Gebruik de grote knop hieronder. Daarna zie je de opgeslagen nieuwe kleurkopieën en kun je vergelijken met de originelen.").font(.caption).foregroundStyle(.secondary)
        }.font(.system(size:12)).disabled(model.busy)
    }
}

struct StudioColourResultHeader:View {
    @ObservedObject var model:StudioModel
    var body:some View {
        VStack(alignment:.leading,spacing:8) {
            if model.showResults {
                HStack {Label(model.busy ? "Nieuwe kleuren worden gemaakt…" : model.colourResults.contains(where:{$0.partial}) ? "Kleurstap niet volledig afgerond" : "Nieuwe kleurkopieën opgeslagen",systemImage:model.colourResults.contains(where:{$0.partial}) ? "exclamationmark.triangle" : model.busy ? "hourglass" : "checkmark.circle").fontWeight(.semibold);Spacer();Text("\(model.colourResults.count) beelden")}.font(.system(size:13)).foregroundStyle(model.colourResults.contains(where:{$0.partial}) ? Color.orange : studioAccent)
                if model.beforeURL != nil {
                    Picker("Bekijk",selection:Binding(get:{model.compare==0 ? "after" : model.compare==1 ? "before" : "compare"},set:{model.compare=$0=="after" ? 0 : $0=="before" ? 1 : 0.5})) {Text("Origineel").tag("before");Text("Vergelijken").tag("compare");Text("Nieuwe kleur").tag("after")}.pickerStyle(.segmented)
                    Text(model.compare==0 ? "Dit is de opgeslagen nieuwe kleur." : model.compare==1 ? "Je bekijkt het origineel; de nieuwe kleurkopie is apart opgeslagen." : "Links het origineel, rechts de nieuwe kleur. Schuif om te vergelijken.").font(.caption).foregroundStyle(.secondary)
                }
                HStack {Button("Toon dit kleurbestand in Finder"){model.revealOutput()};Button("Controleer kleurkopieën"){model.showReview=true}}.font(.caption).disabled(model.busy)
            } else {
                Label("Je bekijkt een origineel voor deze kleurstap",systemImage:"photo").font(.system(size:12,weight:.semibold))
                if !model.outputs.isEmpty {Button("Bekijk de opgeslagen nieuwe kleuren"){model.selectList(true);model.compare=0}.font(.caption)}
            }
        }.padding(12).frame(maxWidth:.infinity,alignment:.leading).background(studioAccent.opacity(0.08),in:RoundedRectangle(cornerRadius:9))
    }
}
