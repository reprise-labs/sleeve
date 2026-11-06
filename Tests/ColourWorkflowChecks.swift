import Foundation
import SwiftUI
@main struct ColourWorkflowChecks {
    @MainActor static func wait(_ model:StudioModel) async throws {
        let deadline=Date().addingTimeInterval(60)
        while model.busy {if Date()>deadline {model.cancel();throw NSError(domain:"ColourWorkflowTimeout",code:1)};try await Task.sleep(nanoseconds:100_000_000)}
        try check(model.errorMessage==nil,model.errorMessage ?? "")
    }
    @MainActor static func main() async {
        guard CommandLine.arguments.count==2 else {fputs("Dit is een interne test; start Sleeve.app.\n",stderr);return}
        do {try await run()} catch {fputs("Colour workflow check failed: \(error)\n",stderr);exit(1)}
    }
    static func check(_ condition: @autoclosure () -> Bool,_ message:String="Controle mislukt") throws {
        if !condition() {throw NSError(domain:message,code:1)}
    }
    @MainActor static func run() async throws {
        let root=URL(fileURLWithPath:CommandLine.arguments[1]);try FileManager.default.createDirectory(at:root,withIntermediateDirectories:true)
        let resources=Bundle.main.resourceURL!;let sample=resources.appendingPathComponent("Samples/Voorbeeld_sidea.png")
        let a=root.appendingPathComponent("record_sidea.png"),b=root.appendingPathComponent("record_sideb.png"),cover=root.appendingPathComponent("cover_front.png")
        for url in [a,b,cover] {try FileManager.default.copyItem(at:sample,to:url)}
        let original=try Data(contentsOf:sample)
        let model=StudioModel(libraryDirectory:root.appendingPathComponent("Library"))
        model.inputs=[MediaItem(url:cover,part:"front"),MediaItem(url:a,part:"sidea"),MediaItem(url:b,part:"sideb")]
        model.changeMode(.colour);model.referenceURL=resources.appendingPathComponent("Samples/Oranje-referentie.png")
        model.outputFolder=nil
        try check(model.canStart,"Kleurcorrectie vereist geen aparte uitvoermap")
        try check(model.colourTargets.count==2 && model.colourCandidates.count==2)
        try check(model.colourActionTitle.contains("2 vinylkanten"))
        model.selectedID=model.inputs[0].id
        try check(model.colourTargets.count==2,"Een hoes bekijken mag de kleurselectie niet veranderen")
        model.start();try await wait(model)
        try check(model.outputs.count==2 && model.outputs.allSatisfy{$0.part.hasPrefix("side")})
        try check(model.showResults && model.compare==0 && model.panel==nil,"Laat het nieuwe resultaat zien zonder automatisch een controlevenster te openen")
        let firstA=model.outputs.first{$0.part=="sidea"}!.url
        let firstB=model.outputs.first{$0.part=="sideb"}!.url
        try check(colourKey(firstA.deletingLastPathComponent())==colourKey(root) && colourKey(firstB.deletingLastPathComponent())==colourKey(root),"Kleurkopieën moeten naast de bronbeelden staan")
        model.setColourTarget(model.inputs[1].id,false);model.strength=0.6
        try check(model.colourTargets.map{$0.part}==["sideb"])
        model.start();try await wait(model)
        try check(model.outputs.count==2 && model.outputs.first{$0.part=="sidea"}!.url==firstA,"Kant A mag niet verdwijnen als je B opnieuw aanpast")
        try check(model.outputs.first{$0.part=="sideb"}!.url != firstB)
        try check(model.runs.last?.processedPaths?.count==1)
        let afterA=try Data(contentsOf:a),afterB=try Data(contentsOf:b),afterCover=try Data(contentsOf:cover)
        try check(afterA==original && afterB==original && afterCover==original)
        let saved=try JSONEncoder().encode(model.captureWorkspace());let snapshot=try JSONDecoder().decode(WorkspaceSnapshot.self,from:saved)
        let restored=StudioModel(libraryDirectory:root.appendingPathComponent("Restored"));restored.restoreWorkspace(snapshot)
        try check(restored.colourTargets.map{$0.part}==["sideb"])
        restored.changeMode(.names)
        try check(restored.inputs.count==3 && restored.inputs.contains{colourKey($0.url)==colourKey(cover)} && restored.inputs.contains{colourKey($0.url)==colourKey(firstA)},"Volgende stap moet hoezen en nieuwe vinylkleuren samen bewaren")
        print("Beide kanten tegelijk, hoezen uitgesloten, nieuwe kleuren direct zichtbaar, resultaten blijven samen en originelen zijn identiek.")
    }
}
