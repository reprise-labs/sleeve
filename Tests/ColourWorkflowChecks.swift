import Foundation
import SwiftUI
@main struct ColourWorkflowChecks {
    @MainActor static func wait(_ model:StudioModel) async throws {
        let deadline=Date().addingTimeInterval(60)
        while model.busy {if Date()>deadline {model.cancel();throw NSError(domain:"ColourWorkflowTimeout",code:1)};try await Task.sleep(nanoseconds:100_000_000)}
        precondition(model.errorMessage==nil,model.errorMessage ?? "")
    }
    @MainActor static func main() async throws {
        let root=URL(fileURLWithPath:CommandLine.arguments[1]);try FileManager.default.createDirectory(at:root,withIntermediateDirectories:true)
        let resources=Bundle.main.resourceURL!;let sample=resources.appendingPathComponent("Samples/Voorbeeld_sidea.png")
        let a=root.appendingPathComponent("record_sidea.png"),b=root.appendingPathComponent("record_sideb.png"),cover=root.appendingPathComponent("cover_front.png")
        for url in [a,b,cover] {try FileManager.default.copyItem(at:sample,to:url)}
        let original=try Data(contentsOf:sample)
        let model=StudioModel(libraryDirectory:root.appendingPathComponent("Library"))
        model.inputs=[MediaItem(url:cover,part:"front"),MediaItem(url:a,part:"sidea"),MediaItem(url:b,part:"sideb")]
        model.changeMode(.colour);model.referenceURL=resources.appendingPathComponent("Samples/Oranje-referentie.png");model.outputFolder=root
        precondition(model.colourTargets.count==2 && model.colourCandidates.count==2)
        precondition(model.colourActionTitle.contains("2 vinylkanten"))
        model.selectedID=model.inputs[0].id
        precondition(model.colourTargets.count==2,"Een hoes bekijken mag de kleurselectie niet veranderen")
        model.start();try await wait(model)
        precondition(model.outputs.count==2 && model.outputs.allSatisfy{$0.part.hasPrefix("side")})
        precondition(model.showResults && model.compare==0 && model.panel==nil,"Laat het nieuwe resultaat zien zonder automatisch een controlevenster te openen")
        let firstA=model.outputs.first{$0.part=="sidea"}!.url
        let firstB=model.outputs.first{$0.part=="sideb"}!.url
        model.setColourTarget(model.inputs[1].id,false);model.strength=0.6
        precondition(model.colourTargets.map{$0.part}==["sideb"])
        model.start();try await wait(model)
        precondition(model.outputs.count==2 && model.outputs.first{$0.part=="sidea"}!.url==firstA,"Kant A mag niet verdwijnen als je B opnieuw aanpast")
        precondition(model.outputs.first{$0.part=="sideb"}!.url != firstB)
        precondition(model.runs.last?.processedPaths?.count==1)
        let afterA=try Data(contentsOf:a),afterB=try Data(contentsOf:b),afterCover=try Data(contentsOf:cover)
        precondition(afterA==original && afterB==original && afterCover==original)
        let saved=try JSONEncoder().encode(model.captureWorkspace());let snapshot=try JSONDecoder().decode(WorkspaceSnapshot.self,from:saved)
        let restored=StudioModel(libraryDirectory:root.appendingPathComponent("Restored"));restored.restoreWorkspace(snapshot)
        precondition(restored.colourTargets.map{$0.part}==["sideb"])
        restored.changeMode(.names)
        precondition(restored.inputs.count==3 && restored.inputs.contains{colourKey($0.url)==colourKey(cover)} && restored.inputs.contains{colourKey($0.url)==colourKey(firstA)},"Volgende stap moet hoezen en nieuwe vinylkleuren samen bewaren")
        print("Beide kanten tegelijk, hoezen uitgesloten, nieuwe kleuren direct zichtbaar, resultaten blijven samen en originelen zijn identiek.")
    }
}
