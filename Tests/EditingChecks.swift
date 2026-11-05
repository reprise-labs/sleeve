import Foundation
import SwiftUI
import CryptoKit

@main struct EditingChecks {
    static func require(_ condition:Bool,_ message:String="Controle mislukt") {if !condition{FileHandle.standardError.write(Data((message+"\n").utf8));exit(1)}}
    @MainActor static func wait(_ m:StudioModel) async throws {
        let deadline=Date().addingTimeInterval(90)
        while m.busy {if Date()>deadline{m.cancel();fatalError("Bewerking liep vast")};try await Task.sleep(nanoseconds:50_000_000)}
    }
    @MainActor static func main() async throws {
        let root=URL(fileURLWithPath:CommandLine.arguments[1]);try FileManager.default.createDirectory(at:root,withIntermediateDirectories:true)
        let sample=Bundle.main.resourceURL!.appendingPathComponent("Samples/Voorbeeld_sidea.png")
        let front=root.appendingPathComponent("front.png");try FileManager.default.copyItem(at:sample,to:front)
        let m=StudioModel(libraryDirectory:root.appendingPathComponent("Library"));m.outputFolder=root;m.inputs=[MediaItem(url:sample,part:"sidea"),MediaItem(url:front,part:"front")]
        let target=MediaItem(url:sample,part:"sidea");let other=MediaItem(url:front,part:"front");m.outputs=[other,target];m.showResults=true;m.selectedID=target.id
        let fingerprint=fileFingerprint(front)
        var approved=ReviewRecord(signature:fingerprint,audit:ImageAudit(path:front.path,signature:fingerprint,readable:true,width:1100,height:1100,part:"front"));approved.visualApproved=true;approved.nameApproved=true;approved.colourApproved=true;approved.notes="Deze voorkant behouden"
        m.reviews[front.path]=approved;m.projectURL=root.appendingPathComponent("Bewerking.sleeveproject");m.editionTitle="Bewerkingstest";m.saveExistingProject()
        let hash=SHA256.hash(data:try Data(contentsOf:sample))
        m.saveCircle(target:target,source:sample,signature:fileFingerprint(sample)!,x:0.5,y:0.5,diameter:0.9,part:"sidea");try await wait(m)
        require(m.errorMessage==nil,m.errorMessage ?? "")
        require(m.outputs.count==2 && m.outputs[0]==other,"Ander onderdeel gewijzigd")
        let cut=m.outputs[1];require(cut.url != sample && cut.previousVersion==sample && cut.id==target.id)
        require(m.beforeURL==sample && m.selected?.url==cut.url,"Vergelijking wijst niet naar vorige versie")
        require(m.selectedInput?.url==cut.url,"Volgende kleurstap gebruikt de oude bron in plaats van de correctie")
        require(m.review(for:other).completed && !m.review(for:cut).completed,"Goedkeuring onterecht overgenomen of verloren")
        require(m.reviews[cut.url.path]?.audit?.round==true)
        let reopen=StudioModel(libraryDirectory:root.appendingPathComponent("OtherLibrary"));reopen.openProject(m.projectURL!);require(reopen.errorMessage==nil,"Heropenen: "+(reopen.errorMessage ?? ""));require(reopen.outputs[1].previousVersion?.path==sample.path && reopen.runs.last?.action=="manualCrop","Vorige versie niet heropend: \(reopen.outputs.map{$0.previousVersion?.absoluteString ?? "nil"}) / \(sample.absoluteString) / \(reopen.runs.last?.action ?? "nil")")
        var settings=m.captureWorkspace();settings.discogs="";settings.useNames=false;settings.useStand=false;settings.useColour=false
        m.retryPart(target:cut,sources:[MediaItem(url:sample,part:"sidea")],settings:settings);try await wait(m)
        require(m.errorMessage==nil,m.errorMessage ?? "")
        let retry=m.outputs[1];require(m.outputs.count==2 && m.outputs[0]==other && retry.previousVersion==cut.url)
        require(m.scanSettings(for:retry).inputs.map{$0.url.path}==[sample.path],"Bronkeuze voor herhalen niet bewaard")
        require(m.originalScanRun(for:other)==nil,"Onaangeraakte voorkant gekoppeld aan de verkeerde herhaling")
        let saved=m.outputs
        m.retryPart(target:retry,sources:[MediaItem(url:root.appendingPathComponent("ontbreekt.png"),part:"sidea")],settings:settings);try await wait(m)
        require(m.outputs==saved && m.review(for:other).completed && m.editingSession==nil,"Fout beschadigt bestaande resultaten")
        m.saveCircle(target:retry,source:sample,signature:fileFingerprint(sample)!,x:0.5,y:0.5,diameter:0.88,part:"sidea");m.saveExistingProject();let during=try ProjectFiles.read(m.projectURL!);require(during.workspace.outputs.map{$0.url.path}==saved.map{$0.url.path},"Tussentijds bewaren verliest bestaande resultaten");m.cancel();try await wait(m)
        require(m.outputs==saved && m.review(for:other).completed,"Annuleren beschadigt bestaande resultaten")
        let afterHash=SHA256.hash(data:try Data(contentsOf:sample));require(afterHash==hash,"Bron gewijzigd")
        let result=["crop_only_replaces_selected_result":true,"previous_version_comparison_and_project_roundtrip":true,"other_results_and_approvals_preserved":true,"retry_uses_and_persists_selected_sources":true,"failed_and_cancelled_edits_restore_results":true,"source_unchanged":true,"autosave_during_edit_keeps_previous_results":true]
        try JSONEncoder().encode(result).write(to:root.appendingPathComponent("RESULTAAT.json"));print(result)
    }
}
