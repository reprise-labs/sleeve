import Foundation

func colourKey(_ url:URL)->String {url.resolvingSymlinksInPath().standardizedFileURL.path}

extension StudioModel {
    var colourCandidates:[MediaItem] {
        inputs.filter{!$0.reference && (colourScope=="vinyl" ? ($0.part.hasPrefix("side") || $0.part=="unknown") : (!$0.part.hasPrefix("side") && !$0.part.hasPrefix("cd")))}
    }
    var colourResults:[MediaItem] {outputs.filter{colourScope=="vinyl" ? ($0.part.hasPrefix("side") || $0.part=="unknown") : (!$0.part.hasPrefix("side") && !$0.part.hasPrefix("cd"))}}
    var colourTargets:[MediaItem] {colourCandidates.filter{colourSelection.contains($0.id)}.map{input in
        if let edited=outputs.first(where:{$0.previousVersion != nil && ($0.colourSource ?? $0.source).map{colourKey($0)}==colourKey(input.url)}) {return MediaItem(id:input.id,url:edited.url,part:input.part,source:input.url)}
        return input
    }}
    var mergedColourInputs:[MediaItem] {
        inputs.map{input in
            if let updated=outputs.last(where:{!$0.partial && ($0.colourSource ?? $0.source).map{colourKey($0)}==colourKey(input.url)}) {return MediaItem(url:updated.url,part:updated.part)}
            return input
        }
    }
    var colourActionTitle:String {
        let count=colourTargets.count
        if count==0{return colourScope=="vinyl" ? "Vink eerst vinylkanten aan" : "Kies eerst een hoes"}
        if referenceURL==nil{return "Kies eerst een referentiefoto"}
        return colourScope=="vinyl" ? "Maak nieuwe kleur voor \(count) vinyl\(count==1 ? "kant" : "kanten")" : "Maak nieuwe kleur voor deze hoes"
    }
    func chooseColourKind(_ kind:String) {
        guard !busy,["vinyl","photo"].contains(kind) else{return}
        if kind != colourScope {referenceURL=nil}
        colourScope=kind;resetColourSelection()
    }
    func resetColourSelection() {
        let candidates=colourCandidates
        colourSelection=Set((colourScope=="vinyl" ? candidates : Array(candidates.prefix(1))).map{$0.id})
        showResults = !colourResults.isEmpty
        selectedID=showResults ? colourResults.first?.id : candidates.first?.id
    }
    func setColourTarget(_ id:UUID,_ chosen:Bool) {
        guard !busy,colourCandidates.contains(where:{$0.id==id}) else{return}
        if chosen {if colourScope != "vinyl" {colourSelection=[]};colourSelection.insert(id)} else {colourSelection.remove(id)}
    }
    func mergeColourOutput(_ item:MediaItem) {
        var replacement=item
        let root=item.source.flatMap{source in outputs.first(where:{colourKey($0.url)==colourKey(source)})?.colourSource ?? source}
        replacement.colourSource=root
        if let root,let index=outputs.firstIndex(where:{($0.colourSource ?? $0.source).map{colourKey($0)}==colourKey(root)}) {
            replacement.id=outputs[index].id;outputs[index]=replacement
        } else {outputs.append(replacement)}
        activeColourOutputPaths.insert(item.url.path)
    }
}
