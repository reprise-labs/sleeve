import Foundation
import SwiftUI
@main struct ModelChecks {
    @MainActor static func main() async throws {
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
        // Vakken: slepen bepaalt de indeling; Suggest vult alleen wat nog vrij is.
        let arrange=StudioModel(libraryDirectory:FileManager.default.temporaryDirectory.appendingPathComponent("StudioArrangeChecks-"+UUID().uuidString))
        let scans=(1...6).map{MediaItem(url:URL(fileURLWithPath:"/tmp/arrange/Scan \($0).jpeg"))}
        arrange.inputs=scans+[MediaItem(url:URL(fileURLWithPath:"/tmp/arrange/Scan 7.jpeg"),reference:true)]
        precondition(arrange.unassignedInputs.count==6 && arrange.slots.isEmpty,"Begin: alles vrij, referentie telt niet mee")
        let sideA=arrange.addSlot(part:"sidea");let front=arrange.addSlot(part:"front")
        precondition(arrange.slots.count==2 && arrange.slots.allSatisfy{$0.items.isEmpty},"Lege vakken zichtbaar")
        for item in scans[0...1] {arrange.assign(item.id,to:sideA)}
        arrange.assign(scans[2].id,to:front)
        precondition(arrange.inputs[0].part=="sidea" && arrange.inputs[2].part=="front","Scan krijgt het onderdeel van zijn vak")
        precondition(arrange.slots.map{$0.items.count}==[2,1],"Vakken met scans in volgorde")
        arrange.setSlotPart(sideA,"sideb")
        precondition(arrange.inputs[0].part=="sideb" && arrange.inputs[1].part=="sideb","Onderdeel van het hele vak wijzigt")
        arrange.unassign(scans[2].id)
        precondition(arrange.inputs[2].group==nil && arrange.inputs[2].part=="unknown" && arrange.slots.contains(where:{$0.id==front && $0.items.isEmpty}),"Laatste scan eruit: vak blijft leeg staan")
        // Voorstel overschrijft geen eigen indeling
        arrange.applySuggestion([SuggestedGroup(files:["/tmp/arrange/Scan 1.jpeg","/tmp/arrange/Scan 4.jpeg","/tmp/arrange/Scan 5.jpeg"],part:"sidea")])
        precondition(arrange.inputs[0].group==sideA,"Eigen vak blijft staan")
        precondition(arrange.inputs[3].group != nil && arrange.inputs[3].group==arrange.inputs[4].group && arrange.inputs[3].part=="sidea","Vrije scans uit het voorstel samen in een nieuw vak")
        precondition(arrange.unassignedInputs.map{$0.title}==["Scan 3.jpeg","Scan 6.jpeg"],"Rest blijft vrij")
        arrange.removeSlot(sideA)
        precondition(arrange.inputs[0].group==nil && arrange.inputs[1].group==nil,"Vak weg: scans weer vrij")
        arrange.clearArrangement()
        precondition(arrange.arrangedCount==0 && arrange.emptySlots.isEmpty && arrange.inputs[6].reference,"Wissen laat referenties staan")
        print("Arrangement: slots, drag, suggestion without overwriting, clear.")
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
        precondition(partLabel("unknown")=="Unassigned")
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
        model.receive(BridgeEvent(event:"progress",index:1,total:6,phase:"Scans openen",scope:"component",activeParts:3,detail:"4 deelscans"))
        let firstStart=Date(timeIntervalSince1970:100);model.phaseStartedAt=firstStart
        model.receive(BridgeEvent(event:"progress",index:2,total:6,phase:"Scans openen",scope:"component",activeParts:3,detail:"8 deelscans"))
        model.receive(BridgeEvent(event:"progress",fraction:0.5,index:1,total:6,phase:"Scans openen",scope:"component",activeParts:3))
        precondition(model.activePartCount==3 && model.currentPart==1 && model.phaseStartedAt==firstStart,"Parallelle staptijd moet per onderdeel blijven kloppen")
        precondition(model.progressDetail=="4 deelscans","Details moeten bij het huidige onderdeel horen")
        model.receive(BridgeEvent(event:"progress",phase:"Afronden",scope:"finishing",activeParts:1))
        precondition(model.activePartCount==1 && model.currentPart==nil)
        let checkRoot=URL(fileURLWithPath:CommandLine.arguments[1])
        try FileManager.default.createDirectory(at:checkRoot,withIntermediateDirectories:true)
        let broken=checkRoot.appendingPathComponent("invalid.png")
        try Data("not an image".utf8).write(to:broken)
        let sample=Bundle.main.resourceURL!.appendingPathComponent("Samples/Voorbeeld_sidea.png")
        let failed=StudioModel(libraryDirectory:checkRoot.appendingPathComponent("Library"))
        failed.inputs=[MediaItem(url:broken,part:"sidea")];failed.outputFolder=checkRoot
        failed.discogs="";failed.useNames=false;failed.useStand=false;failed.useColour=false
        failed.launch(action:"scan")
        precondition(failed.busy,"De gecontroleerde fout moet via een echt proces lopen")
        failed.receive(BridgeEvent(event:"outputs",files:[BridgeFile(path:sample.path,source:broken.path,partial:true,part:"front")]))
        let deadline=Date().addingTimeInterval(15)
        while failed.busy {
            if Date()>deadline {failed.cancel();fatalError("Foutafhandeling liep vast")}
            try await Task.sleep(nanoseconds:20_000_000)
        }
        precondition(failed.showResults && !failed.showReview && failed.errorMessage != nil,"Een fout moet zichtbaar zijn voordat de eindcontrole wordt geopend")
        precondition(failed.outputs.count==1 && failed.outputs[0].partial,"Bewaarde gedeeltelijke uitvoer moet beschikbaar blijven")
        print("Modelcontroles geslaagd: onderdelen, bronverbinding, volgende stap, referentiekeuze.")
    }
}
