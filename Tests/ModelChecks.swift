import Foundation
import SwiftUI
@main struct ModelChecks {
    @MainActor static func main() {
        let model=StudioModel(libraryDirectory:FileManager.default.temporaryDirectory.appendingPathComponent("StudioModelChecks-"+UUID().uuidString))
        for (name,part) in [("release_sidea_kleur.png","sidea"),("release_sideb_2_kleur_3.png","sideb"),("release_cd1.png","cd1"),("release_front.png","front")] {
            precondition(model.inferredPart(name)==part,"Onderdeel kwijt: "+name)
        }
        let source=URL(fileURLWithPath:"/tmp/studio-source_sidea.png")
        model.inputs=[MediaItem(url:source,part:"sidea")];model.mode = .colour
        model.receive(BridgeEvent(event:"outputs",files:[BridgeFile(path:"/tmp/studio-result_sidea_kleur.png",source:source.path)]))
        model.selectList(true)
        precondition(model.selectedInput?.part=="sidea","Bronverbinding kwijt na kleurvoorstel")
        model.changeMode(.names)
        precondition(model.inputs.first?.part=="sidea","Onderdeel kwijt bij wisselen werktafel")
        precondition(model.inputs.first?.url.path=="/tmp/studio-result_sidea_kleur.png","Volgende stap gebruikt niet het resultaat")
        model.receive(BridgeEvent(event:"references",files:[BridgeFile(path:"/tmp/photo.png")]))
        precondition(model.referenceURL==nil,"Referentiefoto moet bewust worden gekozen")
        model.receive(BridgeEvent(event:"progress",fraction:0.37,index:2,total:6,phase:"Beeld opbouwen"))
        precondition(model.measuredProgress==0.37 && model.currentPart==2 && model.totalParts==6)
        model.receive(BridgeEvent(event:"progress",fraction:nil,index:2,total:6,phase:"Beeld opslaan"))
        precondition(model.measuredProgress==nil && model.progressPhase=="Beeld opslaan","Geen schijnpercentage tijdens opslaan")
        print("Modelcontroles geslaagd: onderdelen, bronverbinding, volgende stap, referentiekeuze.")
    }
}
