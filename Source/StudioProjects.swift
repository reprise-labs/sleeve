import Foundation
import AppKit
import Combine
import UniformTypeIdentifiers
import Darwin
import CryptoKit

enum StudioPanel: String, Identifiable {case queue, review, crop, retry;var id:String{rawValue}}

let studioProjectType = UTType(exportedAs:"com.repriselabs.sleeve-project",conformingTo:.package)
let legacyStudioProjectType = UTType(importedAs:"nl.anoukmusic.scan-project",conformingTo:.package)
func fileFingerprint(_ url: URL) -> String? {
    var info = stat()
    guard url.resolvingSymlinksInPath().path.withCString({ lstat($0,&info) }) == 0 else {return nil}
    return "\(info.st_size):\(info.st_mtimespec.tv_sec):\(info.st_mtimespec.tv_nsec)"
}
struct ImageAudit: Codable {
    var path: String
    var signature: String?
    var readable: Bool
    var width: Int = 0
    var height: Int = 0
    var part: String = "front"
    var round: Bool?
    var missingInteriorPercent: Double?
    var namesApplied: Bool = false
    var colourApplied: Bool = false
    var colourKnown: Bool?
    var message: String = ""
}
struct ReviewRecord: Codable {
    var signature: String?
    var audit: ImageAudit?
    var visualApproved = false
    var nameApproved = false
    var colourApproved = false
    var notes = ""
    var stale = false
    var completed: Bool {
        audit?.readable == true && !stale && audit?.round != false && (audit?.missingInteriorPercent ?? 0) < 0.2 && visualApproved && nameApproved && colourApproved
    }
}
struct WorkspaceSnapshot: Codable {
    var mode: WorkMode
    var inputs: [MediaItem]
    var outputs: [MediaItem]
    var selectedID: UUID?
    var showResults: Bool
    var discogs: String
    var useNames: Bool
    var useStand: Bool
    var useColour: Bool
    var variant: String
    var referenceFromDiscogs: Bool
    var references: [MediaItem]
    var referenceURL: URL?
    var strength: Double
    var colourScope: String
    var colourBatch: Bool
    var proposals: [NameProposal]
    var outputFolder: URL?
    var lastJobFolder: URL?
    var reviews: [String:ReviewRecord]
    var warnings: [String]
    var logText: String
    var stateText: String
    var compare: Double
    var demo: Bool
    var reviewComplete: Bool { !outputs.isEmpty && outputs.allSatisfy { reviews[$0.url.path]?.completed == true && reviews[$0.url.path]?.signature == fileFingerprint($0.url) && !$0.partial } }
}
struct StudioRun: Codable, Identifiable {
    var id = UUID()
    var date = Date()
    var label: String
    var success: Bool
    var workspace: WorkspaceSnapshot
    var action: String? = nil
    var scanRecipe: StudioScanRecipe? = nil
    var processedPaths: [URL]? = nil
}
struct StudioProject: Codable {
    var schemaVersion = 1
    var id: UUID
    var title: String
    var modified = Date()
    var workspace: WorkspaceSnapshot
    var runs: [StudioRun]
}
enum QueueState: String, Codable {
    case waiting, running, done, failed, cancelled, interrupted
    var label: String {
        switch self {
        case .waiting:return "Klaar om te starten"
        case .running:return "Wordt verwerkt"
        case .done:return "Verwerkt"
        case .failed:return "Fout · wachtrij gepauzeerd"
        case .cancelled:return "Gestopt door jou"
        case .interrupted:return "Onderbroken · opnieuw klaarzetten"
        }
    }
}
struct StudioQueueItem: Codable, Identifiable {
    var id = UUID()
    var created = Date()
    var project: StudioProject
    var projectURL: URL?
    var state: QueueState = .waiting
    var detail = ""
}
struct StudioLibrary: Codable {
    var schemaVersion = 1
    var queue: [StudioQueueItem] = []
    var recentProjects: [URL] = []
}
enum ProjectFiles {
    static func write(_ document: StudioProject, to folder: URL) throws {
        guard ["sleeveproject","anoukproject"].contains(folder.pathExtension.lowercased()) else {throw CocoaError(.fileWriteInvalidFileName)}
        try FileManager.default.createDirectory(at:folder,withIntermediateDirectories:true)
        var stored=document
        stored.workspace=try retainReferences(stored.workspace,at:folder,portable:true)
        for i in stored.runs.indices {stored.runs[i].workspace=try retainReferences(stored.runs[i].workspace,at:folder,portable:true)}
        try JSONEncoder.studio.encode(stored).write(to:folder.appendingPathComponent("Project.json"),options:.atomic)
    }
    static func read(_ folder: URL) throws -> StudioProject {
        var document=try JSONDecoder().decode(StudioProject.self,from:Data(contentsOf:folder.appendingPathComponent("Project.json")))
        guard document.schemaVersion==1 else {throw CocoaError(.fileReadCorruptFile)}
        document.workspace=try resolveReferences(document.workspace,at:folder)
        for i in document.runs.indices {document.runs[i].workspace=try resolveReferences(document.runs[i].workspace,at:folder)}
        return document
    }
    static func retainReferences(_ workspace: WorkspaceSnapshot,at folder:URL,portable:Bool) throws -> WorkspaceSnapshot {
        var copy=workspace
        let assets=folder.appendingPathComponent("Assets");try FileManager.default.createDirectory(at:assets,withIntermediateDirectories:true)
        func retained(_ url:URL) throws -> URL {
            guard FileManager.default.fileExists(atPath:url.path) else {return url}
            if url.deletingLastPathComponent().standardizedFileURL == assets.standardizedFileURL {
                return portable ? URL(string:"studio-asset:///"+url.lastPathComponent)! : url
            }
            let signature=fileFingerprint(url) ?? ""
            let digest=SHA256.hash(data:Data((url.path+signature).utf8)).prefix(12).map{String(format:"%02x",$0)}.joined()
            let name=digest+"."+url.pathExtension.lowercased()
            let target=assets.appendingPathComponent(name)
            if !FileManager.default.fileExists(atPath:target.path) {try FileManager.default.copyItem(at:url,to:target)}
            return portable ? URL(string:"studio-asset:///"+name)! : target
        }
        copy.referenceURL=try copy.referenceURL.map{try retained($0)}
        for i in copy.references.indices {copy.references[i].url=try retained(copy.references[i].url)}
        return copy
    }
    static func resolveReferences(_ workspace: WorkspaceSnapshot,at folder:URL) throws -> WorkspaceSnapshot {
        var copy=workspace
        func resolved(_ url:URL) throws -> URL {
            guard url.scheme=="studio-asset" else{return url}
            let name=url.lastPathComponent
            guard !name.isEmpty,name != ".",name != "..",url.path=="/"+name else{throw CocoaError(.fileReadCorruptFile)}
            return folder.appendingPathComponent("Assets").appendingPathComponent(name)
        }
        copy.referenceURL=try copy.referenceURL.map{try resolved($0)}
        for i in copy.references.indices {copy.references[i].url=try resolved(copy.references[i].url)}
        return copy
    }
}
extension JSONEncoder {
    static var studio: JSONEncoder {let encoder=JSONEncoder();encoder.outputFormatting=[.prettyPrinted,.sortedKeys];return encoder}
}

@MainActor extension StudioModel {
    var titleForEdition: String {
        let value=editionTitle.trimmingCharacters(in:.whitespacesAndNewlines)
        return value.isEmpty ? (inputs.first?.url.deletingLastPathComponent().lastPathComponent ?? "Nieuwe uitgave") : value
    }
    var pendingCount: Int {queue.filter{$0.state == .waiting}.count}
    var reviewCount: Int {outputs.filter{review(for:$0).completed}.count}
    var selectedResult: MediaItem? {showResults ? selected : nil}
    func review(for item:MediaItem) -> ReviewRecord {
        let fingerprint=fileFingerprint(item.url)
        var value=reviews[item.url.path] ?? ReviewRecord(signature:fingerprint)
        if value.signature != fingerprint {
            let notes=value.notes;value=ReviewRecord(signature:fingerprint,notes:notes,stale:true)
        }
        return value
    }
    func updateReview(_ item:MediaItem,_ change:(inout ReviewRecord)->Void) {
        guard !busy else{return}
        var value=review(for:item);change(&value);reviews[item.url.path]=value
        for i in runs.indices {if runs[i].workspace.outputs.contains(where:{$0.url.path==item.url.path}) {runs[i].workspace.reviews[item.url.path]=value}}
        for i in queue.indices {if queue[i].project.workspace.outputs.contains(where:{$0.url.path==item.url.path}) {queue[i].project.workspace.reviews[item.url.path]=value}}
        persistLibrary();scheduleProjectSave()
    }
    func captureWorkspace() -> WorkspaceSnapshot {
        if busy,let session=editingSession{return session.workspace}
        var checked=reviews
        for item in outputs {checked[item.url.path]=review(for:item)}
        return WorkspaceSnapshot(mode:mode,inputs:inputs,outputs:outputs,selectedID:selectedID,showResults:showResults,discogs:discogs,useNames:useNames,useStand:useStand,useColour:useColour,variant:variant,referenceFromDiscogs:referenceFromDiscogs,references:references,referenceURL:referenceURL,strength:strength,colourScope:colourScope,colourBatch:colourBatch,proposals:proposals,outputFolder:outputFolder,lastJobFolder:lastJobFolder,reviews:checked,warnings:warnings,logText:logText,stateText:stateText,compare:compare,demo:demo)
    }
    func captureProject() -> StudioProject {StudioProject(id:projectID,title:titleForEdition,workspace:captureWorkspace(),runs:runs)}
    func restoreWorkspace(_ snapshot: WorkspaceSnapshot) {
        restoringProject=true;defer{restoringProject=false}
        mode=snapshot.mode;inputs=snapshot.inputs;outputs=snapshot.outputs;selectedID=snapshot.selectedID;showResults=snapshot.showResults
        discogs=snapshot.discogs;useNames=snapshot.useNames;useStand=snapshot.useStand;useColour=snapshot.useColour;variant=snapshot.variant
        referenceFromDiscogs=snapshot.referenceFromDiscogs;references=snapshot.references;referenceURL=snapshot.referenceURL;strength=snapshot.strength
        colourScope=snapshot.colourScope;colourBatch=snapshot.colourBatch;proposals=snapshot.proposals;outputFolder=snapshot.outputFolder;lastJobFolder=snapshot.lastJobFolder
        reviews=snapshot.reviews;warnings=snapshot.warnings;logText=snapshot.logText;stateText=snapshot.stateText;compare=snapshot.compare;demo=snapshot.demo
        cancelled=false;errorMessage=nil;startedAt=nil;measuredProgress=nil;currentPart=nil;totalParts=nil;progressPhase=""
        for item in outputs {reviews[item.url.path]=review(for:item)}
    }
    func initializeLibrary() {
        guard let file=libraryURL else{return}
        if FileManager.default.fileExists(atPath:file.path) {
            do {
                let library=try JSONDecoder().decode(StudioLibrary.self,from:Data(contentsOf:file))
                guard library.schemaVersion==1 else{throw CocoaError(.fileReadCorruptFile)}
                queue=library.queue;recentProjects=library.recentProjects
                for i in queue.indices where queue[i].state == .running {queue[i].state = .interrupted;queue[i].detail="De vorige sessie eindigde tijdens deze taak. Er wordt niets automatisch herhaald."}
                persistLibrary()
            } catch {errorMessage="De bewaarde wachtrij kon niet worden gelezen. Het bestand blijft behouden; je scans en resultaten zijn niet gewijzigd.";libraryWritable=false}
        }
        projectObservation=objectWillChange.sink{[weak self] _ in self?.scheduleProjectSave()}
    }
    func scheduleProjectSave() {
        guard projectURL != nil,!restoringProject,!savingProject,!busy else{return}
        projectSaveWork?.cancel()
        let task=DispatchWorkItem{[weak self] in Task{@MainActor in self?.saveExistingProject()}}
        projectSaveWork=task;DispatchQueue.main.asyncAfter(deadline:.now()+0.7,execute:task)
    }
    func saveExistingProject() {
        guard let url=projectURL,!savingProject,!restoringProject else{return}
        savingProject=true;defer{savingProject=false}
        projectSaveWork?.cancel()
        do {try ProjectFiles.write(captureProject(),to:url);projectSaveText="Project bewaard"}
        catch {queueRunning=false;projectSaveText="Bewaren mislukt";errorMessage="Het project kon niet worden bewaard: "+error.localizedDescription}
    }
    func saveProjectAs() {
        guard !busy else{return}
        let panel=NSSavePanel();panel.title="Bewaar je uitgave als project";panel.allowedContentTypes=[studioProjectType];panel.canCreateDirectories=true
        panel.nameFieldStringValue=titleForEdition+".sleeveproject"
        guard panel.runModal() == .OK,let url=panel.url else{return}
        projectURL=url;saveExistingProject();rememberProject(url)
    }
    func pickProject() {
        guard !busy else{return}
        let panel=NSOpenPanel();panel.title="Open een Sleeve-project";panel.allowedContentTypes=[studioProjectType,legacyStudioProjectType];panel.canChooseDirectories=false;panel.canChooseFiles=true
        if panel.runModal() == .OK,let url=panel.url {openProject(url)}
    }
    func openProject(_ url:URL) {
        guard !busy else{errorMessage="Laat de actieve taak eerst afronden of stop de verwerking.";return}
        saveExistingProject()
        do {
            let document=try ProjectFiles.read(url)
            restoreWorkspace(document.workspace);restoringProject=true
            projectID=document.id;editionTitle=document.title;runs=document.runs;projectURL=url;projectSaveText="Project geopend";restoringProject=false
            rememberProject(url);showQueue=false
            let missing=inputs.filter{!FileManager.default.fileExists(atPath:$0.url.path)}.count
            if missing>0 {errorMessage="\(missing) bronbestanden staan niet meer op hun bewaarde plek. De resultaten en instellingen zijn behouden; voeg de bronnen opnieuw toe als je ze wilt verwerken."}
        } catch {errorMessage="Dit project kon niet worden geopend: "+error.localizedDescription}
    }
    func rememberProject(_ url:URL) {recentProjects.removeAll{$0==url};recentProjects.insert(url,at:0);recentProjects=Array(recentProjects.prefix(10));persistLibrary()}
    @discardableResult func persistLibrary() -> Bool {
        guard libraryWritable,let url=libraryURL else{return false}
        do {
            try FileManager.default.createDirectory(at:url.deletingLastPathComponent(),withIntermediateDirectories:true)
            try JSONEncoder.studio.encode(StudioLibrary(queue:queue,recentProjects:recentProjects)).write(to:url,options:.atomic)
            return true
        } catch {queueRunning=false;errorMessage="De wachtrij kon niet worden bewaard. Automatisch doorgaan is gepauzeerd: "+error.localizedDescription;return false}
    }
    func enqueueCurrent() {
        guard libraryWritable,canStart,let libraryURL else{errorMessage="Kies eerst bronbeelden, de benodigde instellingen en een resultatenmap.";return}
        do {
            var project=captureProject()
            project.workspace=try ProjectFiles.retainReferences(project.workspace,at:libraryURL.deletingLastPathComponent().appendingPathComponent("QueueReferences"),portable:false)
            queue.append(StudioQueueItem(project:project,projectURL:projectURL));guard persistLibrary() else {queue.removeLast();return};saveExistingProject();showQueue=true
        } catch {errorMessage="De referentiefoto kon niet bij de wachtrij worden bewaard: "+error.localizedDescription}
    }
    func startQueue() {
        guard libraryWritable,!busy,pendingCount>0 else{return}
        saveExistingProject();queueRunning=true;showQueue=true;runNextQueuedItem()
    }
    func pauseQueue() {queueRunning=false;persistLibrary()}
    func runNextQueuedItem() {
        guard queueRunning,!busy,activeQueueID==nil else{return}
        guard let i=queue.firstIndex(where:{$0.state == .waiting}) else{queueRunning=false;return}
        let item=queue[i]
        restoreWorkspace(item.project.workspace);projectID=item.project.id;editionTitle=item.project.title;runs=item.project.runs;projectURL=item.projectURL
        mergeSavedRuns();activeQueueID=item.id;queue[i].state = .running;queue[i].detail=""
        guard persistLibrary() else {queue[i].state = .waiting;activeQueueID=nil;return}
        launch(action:mode == .scans ? "scan" : mode == .colour ? "colour" : "namesApply")
        if !busy && activeQueueID==item.id {finishQueueItem(success:false,detail:errorMessage ?? "De taak kon niet worden gestart.")}
    }
    func mergeSavedRuns() {
        if let url=projectURL,let previous=try? ProjectFiles.read(url),previous.id==projectID {
            let ids=Set(runs.map{$0.id});runs += previous.runs.filter{!ids.contains($0.id)}
            runs.sort{$0.date<$1.date}
        }
    }
    func finishQueueItem(success:Bool,detail:String) {
        guard let id=activeQueueID,let i=queue.firstIndex(where:{$0.id==id}) else{return}
        queue[i].state=cancelled ? .cancelled : success ? .done : .failed;queue[i].detail=detail;queue[i].project=captureProject();activeQueueID=nil
        if !success || cancelled {queueRunning=false}
        persistLibrary()
        if queueRunning {Task{@MainActor [weak self] in self?.runNextQueuedItem()}}
    }
    func retryQueuedItem(_ id:UUID) {
        guard !busy,let i=queue.firstIndex(where:{$0.id==id}),queue[i].state != .running else{return}
        queue[i].state = .waiting;queue[i].detail="";persistLibrary()
    }
    func removeQueuedItem(_ id:UUID) {guard !busy else{return};queue.removeAll{$0.id==id};persistLibrary()}
    func moveQueuedItem(_ id:UUID,by offset:Int) {
        guard !busy,let i=queue.firstIndex(where:{$0.id==id}) else{return}
        let target=i+offset;guard queue.indices.contains(target) else{return};queue.swapAt(i,target);persistLibrary()
    }
    func viewQueuedItem(_ id:UUID) {
        guard !busy,let item=queue.first(where:{$0.id==id}) else{return}
        queueRunning=false;saveExistingProject();restoreWorkspace(item.project.workspace);projectID=item.project.id;editionTitle=item.project.title;runs=item.project.runs;projectURL=item.projectURL;panel=item.project.workspace.outputs.isEmpty ? nil : .review
    }
    func showRun(_ id:UUID) {
        guard !busy,let run=runs.first(where:{$0.id==id}) else{return}
        restoreWorkspace(run.workspace);showReview=true
    }
    func recordFinishedRun(action:String,success:Bool) {
        guard ["scan","colour","namesApply","manualCrop"].contains(action) else{return}
        mergeSavedRuns();runs.append(StudioRun(label:action=="manualCrop" ? "Ronde uitsnede bijgesteld" : lastEditingWasRetry ? "Eén onderdeel opnieuw verwerkt" : mode.rawValue,success:success,workspace:captureWorkspace(),action:action,scanRecipe:action=="scan" ? activeScanRecipe : nil,processedPaths:activeProcessedPaths));lastEditingWasRetry=false
        saveExistingProject()
    }
    func prepareForQuit() {
        queueRunning=false
        if let id=activeQueueID,let i=queue.firstIndex(where:{$0.id==id}) {queue[i].state = .interrupted;queue[i].detail="De app is gesloten tijdens de taak.";queue[i].project=captureProject()}
        persistLibrary();saveExistingProject();cancel()
    }
    func exportReview() {
        guard let folder=lastJobFolder ?? outputFolder else{return}
        let stem="Eindcontrole-"+UUID().uuidString.prefix(8)
        do {
            let document=captureProject()
            try JSONEncoder.studio.encode(document).write(to:folder.appendingPathComponent(String(stem)+".json"),options:.atomic)
            var lines=[titleForEdition,"EINDCONTROLE", "Door jou akkoord: \(reviewCount) van \(outputs.count)", ""]
            for item in outputs {
                let r=review(for:item)
                lines += [item.title,"Bestand leesbaar: \(r.audit?.readable == true ? "ja" : "niet bevestigd")","Rond gemeten: \(r.audit?.round.map{$0 ? "ja" : "nee"} ?? "niet meetbaar / niet van toepassing")","Beeld / naam / kleur door jou akkoord: \(r.visualApproved) / \(r.nameApproved) / \(r.colourApproved)",r.audit?.message ?? "",r.notes,""]
            }
            try lines.joined(separator:"\n").write(to:folder.appendingPathComponent(String(stem)+".txt"),atomically:true,encoding:.utf8)
            stateText="Controleverslag bewaard bij de resultaten"
        } catch {errorMessage="Het controleverslag kon niet worden bewaard: "+error.localizedDescription}
    }
    func auditCurrentResults() {guard !outputs.isEmpty,!busy else{return};launch(action:"audit")}
}
