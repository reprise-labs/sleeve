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
        let candidate=ReleaseCandidate(id:33664818,title:"Anouk - Set This Thing On Fire",year:"2025",country:"Netherlands",format:"Vinyl",catno:"758 888-3",variant:"Orange",url:"https://www.discogs.com/release/33664818",reasons:["Barcode komt overeen"])
        model.discogs="https://www.discogs.com/release/123"
        model.adviceCandidates=[candidate]
        precondition(model.discogs.hasSuffix("123"),"Voorstel mag een bestaande keuze niet vervangen")
        model.chooseRelease(candidate)
        precondition(model.discogs==candidate.url)
        var unsafe=candidate;unsafe.url="https://example.com/release/33664818";model.chooseRelease(unsafe)
        precondition(model.discogs==candidate.url)
        let generation=model.adviceGeneration
        model.adviceArtist="Anouk";model.adviceTitle="Set This Thing On Fire"
        precondition(model.discogsSearchURL?.host=="www.discogs.com")
        model.cancelReleaseAdvice(clear:true)
        precondition(model.adviceGeneration != generation && model.adviceCandidates.isEmpty && model.adviceArtist.isEmpty)
        model.inputs=[MediaItem(url:URL(fileURLWithPath:"/tmp/front.png"),part:"front"),MediaItem(url:source,part:"sidea")]
        model.mode = .scans;model.changeMode(.colour)
        precondition(model.colourScope=="vinyl" && model.colourTargets.count==1,"Platen worden gekozen zonder de hoes mee te nemen")
        model.colourScope="photo";model.resetColourSelection()
        precondition(model.colourTargets.first?.part=="front","Een hoes wordt apart gekozen")
        precondition(model.inferredPart("Scan 12_hoes.png")=="unknown")
        precondition(partLabel("unknown")=="Nog te bepalen")
        model.outputs=[];model.inputs=[MediaItem(url:source,part:"front")]
        model.receive(BridgeEvent(event:"outputs",files:[BridgeFile(path:"/tmp/Scan 12_hoes.png",source:source.path)]))
        precondition(model.outputs[0].part=="unknown","Een voorlopige bronrol is geen herkend resultaatonderdeel")
        let legacy=MediaItem(url:URL(fileURLWithPath:"/tmp/Scan 12_hoes.png"),part:"front",partial:true)
        precondition(model.repairLegacyResultPart(legacy).part=="unknown","Oud afgebroken resultaat mag niet als voorkant terugkomen")
        let named=MediaItem(url:URL(fileURLWithPath:"/tmp/release_front.png"),part:"front",partial:true)
        precondition(model.repairLegacyResultPart(named).part=="front","Een expliciete onderdeelsnaam moet behouden blijven")
        model.receive(BridgeEvent(event:"progress",fraction:0.5,index:2,total:6,phase:"Overgangen afwerken",scope:"component",unitsDone:4,unitsTotal:8,completedParts:1,detail:"4 deelscans"))
        let oldDate=Date(timeIntervalSince1970:1);model.phaseStartedAt=oldDate
        model.receive(BridgeEvent(event:"progress",fraction:0.75,index:2,total:6,phase:"Overgangen afwerken",scope:"component",unitsDone:6,unitsTotal:8))
        precondition(model.phaseStartedAt==oldDate && model.completedParts==1 && model.progressUnitsDone==6)
        model.receive(BridgeEvent(event:"progress",phase:"Beeld opslaan",scope:"component"))
        precondition(model.measuredProgress==nil && model.phaseStartedAt != oldDate && model.progressUnitsDone==nil)
        model.receive(BridgeEvent(event:"progress",total:6,phase:"Namen maken",scope:"finishing",completedParts:6))
        precondition(model.currentPart==nil && model.completedParts==6 && model.progressDetail.isEmpty)
        precondition(durationText(500)=="8:20" && durationText(3661)=="1:01:01")
        model.inputs=[];model.outputs=[];model.mode = .scans;model.changeMode(.colour)
        precondition(model.colourScope=="vinyl","Begin zonder beelden standaard bij vinyl")
        model.referenceURL=URL(fileURLWithPath:"/tmp/plate-reference.png");model.chooseColourKind("photo")
        precondition(model.referenceURL==nil,"Een plaatreferentie mag niet vanzelf op een hoes worden gebruikt")
        print("Modelcontroles geslaagd: onderdelen, bronverbinding, volgende stap, referentiekeuze.")
    }
}
