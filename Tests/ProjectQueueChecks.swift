import Foundation
import SwiftUI
import CryptoKit

@main struct ProjectQueueChecks {
    @MainActor static func waitForIdle(_ model:StudioModel) async throws {
        // Ruim: tijdens een zware verwerking ernaast duurt het langer. Bij een
        // time-out netjes stoppen (exit 1), geen crash met macOS-meldvenster.
        let deadline=Date().addingTimeInterval(120)
        while model.busy || model.queueRunning {
            if Date()>deadline {model.cancel();fputs("Wachtrij-test liep vast\n",stderr);exit(1)}
            try await Task.sleep(nanoseconds:50_000_000)
        }
    }
    @MainActor static func main() async throws {
        let root=URL(fileURLWithPath:CommandLine.arguments[1]);try FileManager.default.createDirectory(at:root,withIntermediateDirectories:true)
        let library=root.appendingPathComponent("Library");let out=root.appendingPathComponent("Resultaten");try FileManager.default.createDirectory(at:out,withIntermediateDirectories:true)
        let sample=root.appendingPathComponent("source_sidea.png")
        try FileManager.default.copyItem(at:Bundle.main.resourceURL!.appendingPathComponent("Samples/Voorbeeld_sidea.png"),to:sample)
        let originalRef=root.appendingPathComponent("Tijdelijke-referentie.png")
        try FileManager.default.copyItem(at:Bundle.main.resourceURL!.appendingPathComponent("Samples/Oranje-referentie.png"),to:originalRef)
        let sourceHash=SHA256.hash(data:try Data(contentsOf:sample))
        let m=StudioModel(libraryDirectory:library);m.mode = .colour;m.inputs=[MediaItem(url:sample,part:"sidea")];m.selectedID=m.inputs[0].id;m.resetColourSelection();m.referenceURL=originalRef;m.references=[MediaItem(url:originalRef)];m.outputFolder=out;m.editionTitle="Uitgave één";m.strength=0.6
        let project=root.appendingPathComponent("Eerste.sleeveproject");m.projectURL=project;m.saveExistingProject()
        let legacy=root.appendingPathComponent("Legacy.anoukproject");try FileManager.default.copyItem(at:project,to:legacy);let legacyDocument=try ProjectFiles.read(legacy);precondition(legacyDocument.title==m.titleForEdition,"Oud project niet leesbaar")
        let moved=root.appendingPathComponent("Verplaatst.sleeveproject");try FileManager.default.moveItem(at:project,to:moved)
        try FileManager.default.removeItem(at:originalRef)
        let doc=try ProjectFiles.read(moved);precondition(doc.workspace.selectedID==doc.workspace.inputs[0].id,"Selectie-ID niet bewaard")
        precondition(FileManager.default.fileExists(atPath:doc.workspace.referenceURL!.path),"Referentie niet in project bewaard")
        m.projectURL=nil;m.openProject(moved);precondition(m.strength==0.6 && m.titleForEdition=="Uitgave één" && m.inputs.count==1)
        m.enqueueCurrent();precondition(m.queue.count==1);let first=m.queue[0].id
        m.strength=0.1;m.editionTitle="Later gewijzigd"
        precondition(m.queue[0].project.workspace.strength==0.6 && m.queue[0].project.title=="Uitgave één","Wachtrij-instellingen veranderen mee")
        let retained=m.queue[0].project.workspace.referenceURL!;precondition(retained.path != doc.workspace.referenceURL!.path && FileManager.default.fileExists(atPath:retained.path))
        m.newEdition();m.mode = .colour;m.inputs=[MediaItem(url:sample,part:"sideb")];m.selectedID=m.inputs[0].id;m.resetColourSelection();m.referenceURL=retained;m.outputFolder=out;m.editionTitle="Uitgave twee";m.strength=0.8;m.projectURL=root.appendingPathComponent("Tweede.sleeveproject");m.saveExistingProject();m.enqueueCurrent()
        let second=m.queue[1].id;m.moveQueuedItem(second,by:-1);precondition(m.queue[0].id==second);m.moveQueuedItem(second,by:1)
        let restarted=StudioModel(libraryDirectory:library);precondition(restarted.pendingCount==2 && !restarted.queueRunning)
        m.startQueue();try await waitForIdle(m)
        precondition(m.queue.count==2 && m.queue.allSatisfy{$0.state == .done},m.errorMessage ?? "Niet beide taken afgerond")
        let firstOut=m.queue[0].project.workspace.outputs[0].url;let secondOut=m.queue[1].project.workspace.outputs[0].url
        precondition(firstOut != secondOut,"Uitvoer overschreven")
        precondition(m.queue[0].project.workspace.reviews[firstOut.path]?.audit?.round == true,"Geen echte rondheidscontrole")
        precondition(m.queue[0].project.workspace.reviews[firstOut.path]?.audit?.colourApplied == true)
        precondition(!m.queue[0].project.workspace.reviewComplete,"Automatisch als visueel akkoord gemarkeerd")
        precondition(m.queue[0].project.runs.count==1 && m.queue[1].project.runs.count==1,"Bewerkingen niet bewaard")
        m.viewQueuedItem(first);let result=m.outputs[0]
        m.updateReview(result){$0.visualApproved=true;$0.nameApproved=true;$0.colourApproved=true;$0.notes="Handmatig bekeken"};m.saveExistingProject()
        precondition(m.reviewCount==1 && m.queue[0].project.workspace.reviewComplete)
        let reopened=StudioModel(libraryDirectory:root.appendingPathComponent("OtherLibrary"));reopened.openProject(moved)
        precondition(reopened.reviewCount==1 && reopened.runs.count==1 && reopened.reviews[result.url.path]?.notes=="Handmatig bekeken","Eindcontrole niet bewaard")
        precondition(reopened.selected?.id==result.id,"Geselecteerd resultaat verloren")
        let handle=try FileHandle(forWritingTo:result.url);try handle.seekToEnd();try handle.write(contentsOf:Data("veranderd".utf8));try handle.close()
        precondition(reopened.review(for:result).stale && !reopened.review(for:result).completed,"Oude goedkeuring blijft geldig na wijziging")
        precondition(reopened.review(for:result).notes=="Handmatig bekeken")
        precondition(!m.queue[0].project.workspace.reviewComplete,"Wachtrij toont oude goedkeuring")
        reopened.auditCurrentResults();try await waitForIdle(reopened)
        precondition(reopened.reviews[result.url.path]?.audit?.readable==true && reopened.reviewCount==0,"Opnieuw controleren neemt oude goedkeuring over")
        reopened.exportReview();let exported=try FileManager.default.contentsOfDirectory(atPath:result.url.deletingLastPathComponent().path);precondition(exported.contains{$0.hasPrefix("Eindcontrole-")})
        m.queue=[];m.newEdition();m.mode = .colour;m.inputs=[MediaItem(url:root.appendingPathComponent("ontbreekt.png"),part:"sidea")];m.selectedID=m.inputs[0].id;m.resetColourSelection();m.referenceURL=retained;m.outputFolder=out;m.editionTitle="Opzettelijk ontbrekende bron";m.enqueueCurrent()
        m.newEdition();m.mode = .colour;m.inputs=[MediaItem(url:sample,part:"sidea")];m.selectedID=m.inputs[0].id;m.resetColourSelection();m.referenceURL=retained;m.outputFolder=out;m.editionTitle="Wachten na fout";m.enqueueCurrent();m.startQueue();try await waitForIdle(m)
        precondition(m.queue[0].state == .failed && m.queue[1].state == .waiting && !m.queueRunning,"Fout stopt de wachtrij niet")
        m.removeQueuedItem(m.queue[0].id);m.startQueue();precondition(m.busy);m.cancel();try await waitForIdle(m)
        precondition(m.queue[0].state == .cancelled && !m.queueRunning,"Stoppen niet correct vastgelegd")
        var interrupted=m.queue[0];interrupted.state = .running
        try JSONEncoder.studio.encode(StudioLibrary(queue:[interrupted],recentProjects:[moved])).write(to:library.appendingPathComponent("StudioLibrary.json"),options:.atomic)
        let recovered=StudioModel(libraryDirectory:library);precondition(recovered.queue[0].state == .interrupted && !recovered.busy && !recovered.queueRunning,"Onderbroken taak automatisch herhaald")
        recovered.retryQueuedItem(recovered.queue[0].id);precondition(recovered.pendingCount==1)
        let bad=root.appendingPathComponent("Ongeldig.sleeveproject");try FileManager.default.createDirectory(at:bad,withIntermediateDirectories:true);try Data("geen project".utf8).write(to:bad.appendingPathComponent("Project.json"))
        let previousID=reopened.projectID;reopened.openProject(bad);precondition(reopened.projectID==previousID && reopened.errorMessage != nil,"Ongeldig project wist de werktafel")
        let corruptLibrary=root.appendingPathComponent("CorruptLibrary");try FileManager.default.createDirectory(at:corruptLibrary,withIntermediateDirectories:true);try Data("kapot".utf8).write(to:corruptLibrary.appendingPathComponent("StudioLibrary.json"));let corrupt=StudioModel(libraryDirectory:corruptLibrary);precondition(!corrupt.libraryWritable && corrupt.errorMessage != nil)
        let sourceAfter=try Data(contentsOf:sample);precondition(SHA256.hash(data:sourceAfter)==sourceHash,"Bronbestand gewijzigd")
        let report:[String:Bool]=["project_reference_survives_cache_removal_and_project_move":true,"selection_settings_results_history_and_reviews_roundtrip":true,"queue_immutable_persistent_and_sequential":true,"queue_reorder_and_distinct_output_folders":true,"queue_pauses_on_worker_failure":true,"cancel_and_restart_recovery":true,"no_automatic_visual_approval":true,"modified_file_invalidates_approval":true,"review_recheck_and_export":true,"corrupt_project_and_queue_do_not_erase_data":true,"source_unchanged":true]
        try JSONSerialization.data(withJSONObject:report,options:[.prettyPrinted,.sortedKeys]).write(to:root.appendingPathComponent("RESULTAAT.json"));print(String(data:try JSONSerialization.data(withJSONObject:report,options:.prettyPrinted),encoding:.utf8)!)
    }
}
