import SwiftUI
import AppKit
import UniformTypeIdentifiers
import ImageIO
import Combine

func durationText(_ interval:TimeInterval)->String {
    let seconds=max(0,Int(interval));let hours=seconds/3600
    return hours>0 ? String(format:"%d:%02d:%02d",hours,(seconds/60)%60,seconds%60) : String(format:"%d:%02d",seconds/60,seconds%60)
}
let supportedExtensions: Set<String> = ["png","jpg","jpeg","tif","tiff","bmp","webp"]
let partChoices = ["unknown","front","back","inside","insert","insert_left","insert_right","inlay","sidea","sideb","sidec","sided","cd","cd1","cd2","sticker"]
func partLabel(_ value: String) -> String {
    ["unknown":"Unassigned","front":"Front","back":"Back","inside":"Inside","insert":"Insert","insert_left":"Insert Left","insert_right":"Insert Right","inlay":"Inlay","sidea":"Side A","sideb":"Side B","sidec":"Side C","sided":"Side D","cd":"CD","cd1":"CD 1","cd2":"CD 2","sticker":"Sticker"][value] ?? value
}
enum WorkMode: String, CaseIterable, Identifiable, Codable {
    case scans = "Scans verwerken", colour = "Kleur aanpassen", names = "Namen aanpassen"
    var id: String { rawValue }
    // rawValue is de opgeslagen sleutel in projecten (Nederlands, ongewijzigd); title is wat de app toont.
    var title: String { switch self {case .scans:return "Process Scans";case .colour:return "Adjust Color";case .names:return "Rename Files"} }
    var icon: String { switch self {case .scans:return "scanner";case .colour:return "slider.horizontal.3";case .names:return "tag"} }
    var caption: String { switch self {case .scans:return "One release · CD and vinyl separately";case .colour:return "Make color copies of the checked images";case .names:return "Check the names and save new copies"} }
}
struct MediaItem: Identifiable, Hashable, Codable {
    var id = UUID()
    var url: URL
    var part: String = "unknown"
    var reference = false
    var source: URL? = nil
    var partial = false
    var previousVersion: URL? = nil
    var colourSource:URL? = nil
    // Vak in het indelingsscherm: scans met hetzelfde vak vormen samen één onderdeel.
    var group:String? = nil
    // Feitenroute: oordeel per onderdeel, en bij twijfel de reden en de keuzes.
    var verdict:String? = nil
    var why:[String]? = nil
    var choices:[String]? = nil
    var scans:[String]? = nil
    var message:String? = nil
    var applied:String? = nil
    var title: String { url.lastPathComponent }
}
struct NameProposal: Codable, Identifiable {
    var source: String
    var newName: String
    var part: String
    var size: Int64
    var mtime: Int64
    var id: String { source }
}
struct BridgeFile: Decodable { var path: String; var source: String?; var title: String?; var partial: Bool?; var part: String?; var verdict:String?; var why:[String]?; var choices:[String]?; var scans:[String]?; var message:String?; var applied:String?; var replace:Bool? }
struct BridgeEvent: Decodable {
    var event: String
    var message: String?
    var path: String?
    var files: [BridgeFile]?
    var rows: [NameProposal]?
    var fraction: Double?
    var index: Int?
    var total: Int?
    var phase: String?
    var scope:String?
    var unitsDone:Int?
    var unitsTotal:Int?
    var completedParts:Int?
    var activeParts:Int?
    var detail:String?
    var advice: ReleaseAdvice?
    var info: ReleaseInfo?
    var audits: [ImageAudit]?
    var groups: [SuggestedGroup]?
}

final class PipeReader: @unchecked Sendable {
    private let lock = NSLock()
    private var pending = Data()
    let callback: (BridgeEvent) -> Void
    init(callback: @escaping (BridgeEvent) -> Void) { self.callback = callback }
    func accept(_ data: Data) {
        lock.lock(); pending.append(data)
        var lines: [Data] = []
        while let end = pending.firstIndex(of: 10) {
            lines.append(pending.prefix(upTo: end)); pending.removeSubrange(...end)
        }
        lock.unlock()
        for line in lines { if let event = try? JSONDecoder().decode(BridgeEvent.self, from: line) { callback(event) } }
    }
    func finish() { lock.lock();let rest=pending;pending=Data();lock.unlock();if let event=try? JSONDecoder().decode(BridgeEvent.self,from:rest) {callback(event)} }
}

@MainActor final class StudioModel: ObservableObject {
    @Published var mode: WorkMode = .scans
    @Published var inputs: [MediaItem] = []
    @Published var outputs: [MediaItem] = []
    @Published var selectedID: UUID?
    @Published var showResults = false
    @Published var discogs = ""
    @Published var useNames = true
    @Published var useStand = true
    // Feit van de gebruiker: cd of vinyl ("auto" = uit Discogs, of cd als er een cd-vak is).
    @Published var mediaFormat = "auto"
    // Bevestigde release (Discogs): gegevens, verbeterd jaartal en verpakking
    @Published var releaseInfo: ReleaseInfo? = nil
    @Published var releaseYear = ""
    @Published var packaging = "auto"
    @Published var releaseLoading = false
    @Published var releaseStatus = ""
    @Published var releaseConfirmed = false
    // Kept for decoding older projects; scan requests always disable reference colour.
    @Published var useColour = false
    @Published var discovering = false
    @Published var adviceCandidates:[ReleaseCandidate] = []
    @Published var adviceStatus = ""
    @Published var adviceArtist = ""
    @Published var adviceTitle = ""
    @Published var adviceBarcode = ""
    @Published var adviceCatalog = ""
    @Published var adviceFormat = ""
    var adviceProcess:Process?
    var adviceWorkItem:DispatchWorkItem?
    var adviceGeneration=UUID()
    @Published var variant = ""
    @Published var referenceFromDiscogs = true
    @Published var references: [MediaItem] = []
    @Published var referenceURL: URL?
    @Published var strength = 1.0
    @Published var colourScope = "vinyl"
    @Published var colourBatch = false // Older saved projects.
    @Published var colourSelection:Set<UUID> = []
    var activeColourSourcePaths:Set<String> = []
    var activeColourOutputPaths:Set<String> = []
    @Published var proposals: [NameProposal] = []
    @Published var outputFolder: URL?
    @Published var lastJobFolder: URL?
    @Published var measuredProgress: Double?
    @Published var currentPart: Int?
    @Published var totalParts: Int?
    @Published var progressPhase = ""
    @Published var phaseStartedAt:Date?
    @Published var lastProgressAt:Date?
    @Published var progressUnitsDone:Int?
    @Published var progressUnitsTotal:Int?
    @Published var activePartCount=1
    var componentPhaseClocks:[Int:(phase:String,date:Date)]=[:]
    var componentDetails:[Int:String]=[:]
    @Published var completedParts=0
    @Published var progressDetail=""
    @Published var busy = false
    @Published var cancelled = false
    @Published var stateText = "Ready to begin"
    @Published var errorMessage: String?
    @Published var logText = ""
    @Published var warnings: [String] = []
    @Published var startedAt: Date?
    @Published var compare = 0.5
    @Published var zoom = 1.0
    @Published var showLog = false
    @Published var demo = false
    @Published var editionTitle = ""
    @Published var projectURL: URL?
    @Published var projectSaveText = "Not saved yet"
    @Published var projectID = UUID()
    @Published var runs: [StudioRun] = []
    @Published var reviews: [String:ReviewRecord] = [:]
    @Published var queue: [StudioQueueItem] = []
    @Published var recentProjects: [URL] = []
    @Published var queueRunning = false
    @Published var activeQueueID: UUID?
    @Published var panel: StudioPanel?
    @Published var emptySlots: [ScanSlot] = []
    @Published var suggesting = false
    @Published var suggestStatus = ""
    /// Waarom Sleeve een stapel zo noemde (of geen naam gaf), per vak.
    @Published var slotNotes: [String:String] = [:]
    /// Het onderwerp waarop het hulpvenster opent (nil: bovenaan).
    @Published var helpTopic: String? = nil
    var suggestProcess:Process?
    var showQueue: Bool {get{panel == .queue} set{if newValue{panel = .queue}else if panel == .queue{panel=nil}}}
    var showReview: Bool {get{panel == .review} set{if newValue{panel = .review}else if panel == .review{panel=nil}}}
    @Published var cropTarget: MediaItem?
    @Published var retryTarget: MediaItem?
    var editingSession: StudioEditingSession?
    var lastEditingWasRetry=false
    var activeScanRecipe: StudioScanRecipe?
    var activeProcessedPaths:[URL]?
    var libraryURL: URL?
    var libraryWritable = true
    var restoringProject = false
    var savingProject = false
    var projectSaveWork: DispatchWorkItem?
    var projectObservation: AnyCancellable?
    private var process: Process?
    private var reader: PipeReader?
    private var readPipe: Pipe?
    private var currentToken = UUID()
    private var reportedError = false
    private var receivedComplete = false
    private var activeAction = ""
    private var activeLogFolder: URL?
    var displayItems: [MediaItem] { mode == .colour ? (showResults ? colourResults : colourCandidates) : (showResults ? outputs : inputs) }
    var selected: MediaItem? { displayItems.first(where: {$0.id == selectedID}) ?? displayItems.first }
    var selectedInput: MediaItem? {
        guard let selected else { return nil }
        if showResults && selected.previousVersion != nil {return selected}
        if showResults, let source = selected.source { return inputs.first(where: {$0.url.resolvingSymlinksInPath().path == source.resolvingSymlinksInPath().path}) }
        return inputs.first(where: {$0.id == selected.id})
    }
    var selectedProposal: NameProposal? { guard let selected else{return nil};return proposals.first(where: {$0.source == selected.url.path || $0.source == selected.source?.path}) }
    var beforeURL: URL? { showResults ? (selected?.previousVersion ?? selected?.source) : nil }
    var inputCount: Int { inputs.filter{!$0.reference}.count }
    var canStart: Bool {
        guard !busy, inputCount > 0, (mode == .colour || outputFolder != nil) else { return false }
        switch mode {
        case .scans:return true
        case .colour:return referenceURL != nil && !colourTargets.isEmpty
        case .names:return !proposals.isEmpty
        }
    }
    init(libraryDirectory: URL? = nil) {
        if let path=UserDefaults.standard.string(forKey:"outputFolder"),FileManager.default.fileExists(atPath:path){outputFolder=URL(fileURLWithPath:path)}
        libraryURL=(libraryDirectory ?? FileManager.default.urls(for:.applicationSupportDirectory,in:.userDomainMask)[0].appendingPathComponent("com.repriselabs.Sleeve")).appendingPathComponent("StudioLibrary.json")
        initializeLibrary()
    }
    func changeMode(_ newMode: WorkMode) {
        guard !busy,newMode != mode else{return}
        let preferredURL=selected?.url
        cancelReleaseAdvice(clear:true)
        if newMode != mode && !outputs.isEmpty {inputs=mode == .colour ? mergedColourInputs : outputs.map{MediaItem(url:$0.url,part:$0.part)};outputs=[];proposals=[];stateText="Result images ready for the next step"}
        mode=newMode;showResults=false;selectedID=inputs.first(where:{$0.url==preferredURL})?.id ?? inputs.first?.id;errorMessage=nil;zoom=1
        if newMode == .colour {chooseColourKind(inputs.isEmpty || inputs.contains(where:{$0.part.hasPrefix("side")}) ? "vinyl" : "photo")}
    }
    func newEdition() {
        guard !busy else{return}
        cancelReleaseAdvice(clear:true)
        saveExistingProject();restoringProject=true;defer{restoringProject=false}
        panel=nil;projectID=UUID();projectURL=nil;editionTitle="";runs=[];reviews=[:];projectSaveText="Not saved yet"
        errorMessage=nil;logText="";cancelled=false;startedAt=nil;inputs=[];outputs=[];emptySlots=[];suggestStatus="";slotNotes=[:];selectedID=nil;showResults=false;discogs="";variant="";referenceURL=nil;references=[];proposals=[];colourSelection=[];demo=false;stateText="Ready for a new release";lastJobFolder=nil
        releaseInfo=nil;releaseYear="";packaging="auto";releaseConfirmed=false;releaseStatus="";mediaFormat="auto"
        mode = .scans   // een nieuwe release begint altijd bij Process Scans (bleef in Adjust Color hangen)
    }
    func pickImages() {
        guard !busy else{return}
        let panel=NSOpenPanel();panel.title="Choose the images of one release";panel.allowsMultipleSelection=true;panel.canChooseDirectories=true;panel.canChooseFiles=true
        if panel.runModal() == .OK { addURLs(panel.urls) }
    }
    func addURLs(_ values: [URL]) {
        guard !busy else{return}
        var files:[URL]=[]
        for url in values {
            var isDir: ObjCBool=false
            if FileManager.default.fileExists(atPath:url.path,isDirectory:&isDir),isDir.boolValue {
                files += ((try? FileManager.default.contentsOfDirectory(at:url,includingPropertiesForKeys:nil,options:[.skipsHiddenFiles])) ?? []).filter{supportedExtensions.contains($0.pathExtension.lowercased())}
            } else if supportedExtensions.contains(url.pathExtension.lowercased()) {files.append(url)}
        }
        files=files.map{$0.resolvingSymlinksInPath().standardizedFileURL}.sorted{$0.lastPathComponent.localizedStandardCompare($1.lastPathComponent) == .orderedAscending}
        guard !files.isEmpty else{errorMessage="This selection contains no supported images.";return}
        if mode == .scans {
            let folders=Set((inputs.map{$0.url}+files).map{$0.deletingLastPathComponent().path})
            guard folders.count<=1 else{errorMessage="Process one release from one source folder. Choose ‘New Release’ first for another folder.";return}
        }
        for url in files where !inputs.contains(where:{$0.url==url}) {
            var part=inferredPart(url.lastPathComponent)
            var reference=false
            var group:String?=nil
            let profile=url.deletingLastPathComponent().appendingPathComponent(".anouk-referenties.json")
            if let data=try? Data(contentsOf:profile),let json=(try? JSONSerialization.jsonObject(with:data)) as? [String:Any] {
                reference=(json["reference_files"] as? [String] ?? []).contains(url.lastPathComponent)
                for (index,saved) in (json["scan_groups"] as? [[String:Any]] ?? []).enumerated() where (saved["files"] as? [String] ?? []).contains(url.lastPathComponent) {
                    if let name=saved["part"] as? String,partChoices.contains(name){part=name}
                    group="saved-\(index)"     // eerder opgeslagen indeling van deze map
                }
            }
            inputs.append(MediaItem(url:url,part:part,reference:reference,group:group))
        }
        showResults=false;selectedID=inputs.first?.id;proposals=[];demo=false
        if outputFolder==nil {outputFolder=files[0].deletingLastPathComponent()}
        stateText="\(inputCount) source images · \(inputs.filter{$0.reference}.count) references"
        if mode == .colour {resetColourSelection()}
        if mode == .scans {offerReleaseConfirmation()}
        scheduleReleaseAdvice()
    }
    func inferredPart(_ name:String)->String {
        let stem=URL(fileURLWithPath:name).deletingPathExtension().lastPathComponent.lowercased().replacingOccurrences(of:#"(?:_kleur(?:_\d+)?)+$"#,with:"",options:.regularExpression)
        for part in partChoices.sorted(by:{$0.count>$1.count}) where stem.range(of:"_"+part+#"(?:_\d+)?$"#,options:.regularExpression) != nil{return part}
        return "unknown"
    }
    func repairLegacyResultPart(_ value:MediaItem)->MediaItem {
        guard value.partial,value.part=="front",value.url.deletingPathExtension().lastPathComponent.range(of:#"_hoes(?:_\d+)?$"#,options:.regularExpression) != nil else{return value}
        var item=value;item.part="unknown"
        let manifest=value.url.deletingLastPathComponent().appendingPathComponent("Studio-onderdelen.json")
        if let data=try? Data(contentsOf:manifest),let json=(try? JSONSerialization.jsonObject(with:data)) as? [String:Any],
           let row=(json["files"] as? [[String:Any]])?.first(where:{$0["name"] as? String == value.url.lastPathComponent}),let part=row["part"] as? String,partChoices.contains(part) {item.part=part}
        return item
    }
    func selectList(_ results:Bool) {showResults=results;selectedID=displayItems.first?.id;zoom=1}
    func updateSelectedPart(_ part:String) {
        guard !busy,let item=selectedInput,let i=inputs.firstIndex(where:{$0.id==item.id}) else{return}
        inputs[i].part=part;proposals=[]
    }
    func updateReference(_ value:Bool) {
        guard !busy,let item=selectedInput,let i=inputs.firstIndex(where:{$0.id==item.id}) else{return}
        inputs[i].reference=value;proposals=[];cancelReleaseAdvice(clear:true)
    }
    func removeSelected() {
        guard !busy,let item=selectedInput else{return}
        inputs.removeAll{$0.id==item.id};selectedID=inputs.first?.id;proposals=[];cancelReleaseAdvice(clear:true)
    }
    func chooseOutput() {
        let p=NSOpenPanel();p.title="Choose where new results may go";p.canChooseFiles=false;p.canChooseDirectories=true;p.canCreateDirectories=true
        if p.runModal() == .OK,let url=p.url{outputFolder=url;UserDefaults.standard.set(url.path,forKey:"outputFolder")}
    }
    func chooseReference() {
        guard !busy else{return}
        let p=NSOpenPanel();p.title="Choose a reference photo";p.allowedContentTypes=[.image];p.allowsMultipleSelection=false
        if p.runModal() == .OK,let url=p.url{referenceURL=url;referenceFromDiscogs=false}
    }
    func revealOutput() {if mode == .colour,showResults,let selected {NSWorkspace.shared.activateFileViewerSelecting([selected.url])} else if let url=lastJobFolder ?? outputFolder{NSWorkspace.shared.open(url)}}
    func openSelected() {if let url=selected?.url{NSWorkspace.shared.open(url)}}
    func loadReferences() {launch(action:"references")}
    func previewNames() {proposals=[];launch(action:"namesPreview")}
    func start() {
        switch mode {
        case .scans:launch(action:"scan")
        case .colour:launch(action:"colour")
        case .names:launch(action:"namesApply")
        }
    }
    func decide(_ item:MediaItem,_ choice:String) {
        guard let scans=item.scans,!scans.isEmpty else{errorMessage="This part has no scans recorded; process it again with slots.";return}
        launch(action:"decide",rowsOverride:[item],extra:["part":item.part,"scans":scans,"choice":choice,"path":item.url.path])
    }
    func cancel() {
        guard let p=process,p.isRunning else{return}
        queueRunning=false;cancelled=true;stateText="Stopping… results already made are kept";p.terminate()
    }
    func loadDemo() {
        guard !busy,let resources=Bundle.main.resourceURL else{return}
        newEdition();mode = .colour
        let image=resources.appendingPathComponent("Samples/Voorbeeld_sidea.png")
        guard FileManager.default.fileExists(atPath:image.path) else{return}
        inputs=[MediaItem(url:image,part:"sidea")];selectedID=inputs[0].id
        referenceURL=resources.appendingPathComponent("Samples/Oranje-referentie.png");referenceFromDiscogs=false;demo=true
        if outputFolder==nil {outputFolder=FileManager.default.urls(for:.documentDirectory,in:.userDomainMask).first}
        colourScope="vinyl";resetColourSelection()
        stateText="Sample images · nothing has been processed yet"
    }
    func launch(action:String, rowsOverride:[MediaItem]? = nil, extra:[String:Any] = [:]) {
        guard !busy else{return}
        cancelReleaseAdvice()
        guard let resources=Bundle.main.resourceURL else{errorMessage="The app's components aren't available.";return}
        if action != "references" && action != "audit" && (rowsOverride ?? inputs).isEmpty {errorMessage="Add images first.";return}
        if ["scan","namesApply","manualCrop"].contains(action) && outputFolder==nil {chooseOutput();guard outputFolder != nil else{return}}
        if action=="references" || action=="namesPreview",discogs.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty {errorMessage="First enter the Discogs link of the right release.";return}
        let rows: [MediaItem]
        if let supplied=rowsOverride {rows=supplied}
        else if action=="audit" {rows=outputs}
        else if action=="colour" {rows=colourTargets} else{rows=inputs}
        if action=="colour" && rows.isEmpty {errorMessage="First check the vinyl sides, or choose one cover.";return}
        let cache=FileManager.default.urls(for:.cachesDirectory,in:.userDomainMask)[0].appendingPathComponent("com.repriselabs.Sleeve/Jobs/"+UUID().uuidString)
        do {
            try FileManager.default.createDirectory(at:cache,withIntermediateDirectories:true)
            var req: [String:Any] = ["action":action,"inputs":rows.map{["path":$0.url.path,"part":$0.part,"reference":$0.reference,"partial":$0.partial,"source":$0.source?.path ?? "","group":$0.group ?? ""]},"discogs":discogs.trimmingCharacters(in:.whitespacesAndNewlines),"variant":variant,"useNames":useNames,"useStand":useStand,"useColour":false,"strength":strength,"scope":colourScope,"format":mediaFormat,"year":releaseYear,"packaging":packaging]
            if let folder=outputFolder{req["output"]=folder.path}
            if let ref=referenceURL{req["reference"]=ref.path}
            if action=="namesApply" {req["proposals"]=try JSONSerialization.jsonObject(with:JSONEncoder().encode(proposals))}
            for (key,value) in extra {req[key]=value}
            if action=="scan" {req["useColour"]=false}
            activeScanRecipe=action=="scan" ? StudioScanRecipe(inputs:rows,discogs:req["discogs"] as? String ?? "",variant:req["variant"] as? String ?? "",useNames:req["useNames"] as? Bool ?? true,useStand:req["useStand"] as? Bool ?? true,useColour:req["useColour"] as? Bool ?? false) : nil
            let request=cache.appendingPathComponent("request.json");try JSONSerialization.data(withJSONObject:req,options:.prettyPrinted).write(to:request)
            componentPhaseClocks=[:];componentDetails=[:];activePartCount=1
            busy=true;measuredProgress=nil;currentPart=nil;totalParts=nil;progressPhase="Preparing";phaseStartedAt=Date();lastProgressAt=Date();progressUnitsDone=nil;progressUnitsTotal=nil;completedParts=0;progressDetail="";cancelled=false;reportedError=false;receivedComplete=false;activeAction=action;activeLogFolder=cache;startedAt=Date();logText="";warnings=[];errorMessage=nil;stateText=action=="references" ? "Fetching Discogs photos…" : "Preparing…"
            if action=="colour" {activeColourSourcePaths=Set(rows.map{$0.url.path});activeColourOutputPaths=[]}
            else if ["scan","namesApply","manualCrop"].contains(action) {outputs=[];showResults=false}
            let p=Process();let runtime=FileManager.default.urls(for:.applicationSupportDirectory,in:.userDomainMask)[0].appendingPathComponent("com.repriselabs.Sleeve/Runtime/bin/python3");p.executableURL=FileManager.default.isExecutableFile(atPath:runtime.path) ? runtime : URL(fileURLWithPath:"/usr/bin/python3");p.arguments=[resources.appendingPathComponent("studio_bridge.py").path,request.path]
            var env=ProcessInfo.processInfo.environment;env["PYTHONUNBUFFERED"]="1";env["PYTHONDONTWRITEBYTECODE"]="1";env["OPENBLAS_NUM_THREADS"]="1";env["OMP_NUM_THREADS"]="2";env["VECLIB_MAXIMUM_THREADS"]="1";p.environment=env
            let pipe=Pipe();p.standardOutput=pipe;p.standardError=pipe;let token=UUID();currentToken=token
            let lineReader=PipeReader{[weak self] event in
                DispatchQueue.main.async {guard let self,self.currentToken==token else{return};self.receive(event)}
            }
            reader=lineReader;readPipe=pipe;process=p;try p.run()
            DispatchQueue.global(qos:.userInitiated).async { [weak self] in
                while true {
                    let data=pipe.fileHandleForReading.availableData
                    if data.isEmpty {break}
                    lineReader.accept(data)
                }
                lineReader.finish();p.waitUntilExit()
                DispatchQueue.main.async {guard let self,self.currentToken==token else{return};self.didFinish(p.terminationStatus)}
            }
        } catch {
            busy=false;finishEditing(success:false);lastEditingWasRetry=false;stateText="Not started";errorMessage="Processing couldn't be started: "+error.localizedDescription
        }
    }
    func receive(_ event:BridgeEvent) {
        switch event.event {
        case "audit":
            for var audit in event.audits ?? [] {
                if let source=outputs.first(where:{$0.url.path==audit.path})?.source,
                   let previous=reviews[source.path],previous.signature==fileFingerprint(source) {
                    audit.colourApplied = audit.colourApplied || (previous.audit?.colourApplied ?? false)
                    audit.namesApplied = audit.namesApplied || (previous.audit?.namesApplied ?? false)
                    audit.colourKnown = (audit.colourKnown == true) || (previous.audit?.colourKnown == true)
                }
                if var previous=reviews[audit.path],previous.signature==audit.signature,!previous.stale {
                    audit.colourApplied = audit.colourApplied || (previous.audit?.colourApplied ?? false)
                    audit.namesApplied = audit.namesApplied || (previous.audit?.namesApplied ?? false)
                    audit.colourKnown = (audit.colourKnown == true) || (previous.audit?.colourKnown == true)
                    previous.audit=audit;reviews[audit.path]=previous
                } else {reviews[audit.path]=ReviewRecord(signature:audit.signature,audit:audit)}
            }
        case "progress":
            let nextIndex=event.scope=="preparation" || event.scope=="finishing" ? nil : (event.index ?? currentPart)
            if let oldIndex=currentPart,let start=phaseStartedAt {componentPhaseClocks[oldIndex]=(progressPhase,start)}
            if event.phase != progressPhase || nextIndex != currentPart {
                if let index=nextIndex,let clock=componentPhaseClocks[index],clock.phase==event.phase {phaseStartedAt=clock.date}
                else {phaseStartedAt=Date()}
            }
            if nextIndex != currentPart {progressDetail=nextIndex.flatMap{componentDetails[$0]} ?? ""}
            activePartCount=max(0,event.activeParts ?? 1)
            lastProgressAt=Date();measuredProgress=event.fraction;currentPart=nextIndex;totalParts=event.total ?? totalParts;progressPhase=event.phase ?? ""
            progressUnitsDone=event.unitsDone;progressUnitsTotal=event.unitsTotal
            if let count=event.completedParts {completedParts=count}
            if let detail=event.detail,!detail.isEmpty {progressDetail=detail;if let index=nextIndex {componentDetails[index]=detail}}
            if event.scope=="preparation" || event.scope=="finishing" {progressDetail=""}
        case "status":stateText=event.message ?? "Working…"
        case "warning":warnings.append(event.message ?? "Check the log")
        case "log":
            logText += (event.message ?? "")+"\n"
            if logText.count>100_000{logText=String(logText.suffix(100_000))}
        case "destination":if let p=event.path{lastJobFolder=URL(fileURLWithPath:p)}
        case "references":
            references=(event.files ?? []).map{MediaItem(url:URL(fileURLWithPath:$0.path))};referenceURL=nil;referenceFromDiscogs=true
            stateText=event.message ?? "Choose a reference photo"
        case "names":proposals=event.rows ?? []
        case "outputs":
            for file in event.files ?? [] {
                let url=URL(fileURLWithPath:file.path)
                if let i=outputs.firstIndex(where:{$0.url==url}),file.verdict != nil {
                    // beslissing toegepast: zelfde bestand, nieuw oordeel (nieuwe id zodat het voorbeeld ververst)
                    var item=outputs[i];item.id=UUID();item.verdict=file.verdict;item.why=file.why;item.choices=file.choices;item.message=file.message;item.applied=file.applied
                    if let scans=file.scans {item.scans=scans}
                    outputs[i]=item;reviews[url.path]=nil
                } else if !outputs.contains(where:{$0.url==url}){
                    let source=file.source.flatMap{$0.isEmpty ? nil : URL(fileURLWithPath:$0)}
                    let part=file.part ?? inferredPart(url.lastPathComponent)
                    var item=MediaItem(url:url,part:part,source:source,partial:file.partial ?? false)
                    item.verdict=file.verdict;item.why=file.why;item.choices=file.choices;item.scans=file.scans;item.message=file.message;item.applied=file.applied
                    if activeAction=="colour" {mergeColourOutput(item)} else {outputs.append(item)}
                }
            }
        case "error":reportedError=true;stateText=cancelled ? "Stopped" : "Stopped on an error";if !cancelled{errorMessage=event.message}
        case "complete":receivedComplete=true;stateText=event.message ?? "Finished"
            // een onderdeel dat niet gemaakt kon worden, staat niet in de eindcontrole: meteen laten zien
            if let message=event.message,message.contains("NOT MADE") {errorMessage=message}
        default:break
        }
    }
    func didFinish(_ status:Int32) {
        busy=false;activePartCount=1;process=nil;readPipe=nil;reader=nil
        if let folder=activeLogFolder{try? logText.write(to:folder.appendingPathComponent("app-logboek.txt"),atomically:true,encoding:.utf8)}
        if cancelled {stateText="Stopped by you"}
        else if status != 0 || !receivedComplete {
            if !reportedError{errorMessage="Processing didn't finish. See the log for the cause."}
            stateText="Stopped on an error";showLog=true
        }
        if status==0 && !warnings.isEmpty {stateText += " · \(warnings.count) notes in the log";showLog=true}
        if ["scan","colour","namesApply","manualCrop"].contains(activeAction) && !outputs.isEmpty {showResults=true;selectedID=outputs.first?.id;if status==0 && receivedComplete && !cancelled && activeAction != "colour" && activeQueueID==nil && panel != .queue{showReview=true}}
        if activeAction=="colour",!activeColourOutputPaths.isEmpty {
            showResults=true;selectedID=outputs.first(where:{activeColourOutputPaths.contains($0.url.path)})?.id;compare=0
        }
        if editingSession != nil && outputs.count != 1 && status==0 && receivedComplete && !cancelled {errorMessage="The new run didn't produce exactly one image. The previous results are kept."}
        let success=status==0 && receivedComplete && !cancelled && (editingSession==nil || outputs.count==1)
        if !success && ["scan","colour","namesApply","manualCrop"].contains(activeAction) {for i in outputs.indices where activeAction != "colour" || activeColourOutputPaths.contains(outputs[i].url.path) {outputs[i].partial=true}}
        activeProcessedPaths=outputs.filter{activeAction != "colour" || activeColourOutputPaths.contains($0.url.path)}.map{$0.url}
        let edited=finishEditing(success:success)
        if edited {showResults=true;if success{showReview=true}}
        recordFinishedRun(action:activeAction,success:success)
        saveExistingProject()
        finishQueueItem(success:success,detail:stateText)
    }
}

final class ThumbnailStore: @unchecked Sendable {
    static let shared=ThumbnailStore()
    static let worker=DispatchQueue(label:"com.repriselabs.sleeve.preview",qos:.utility)
    private let cache=NSCache<NSString,NSImage>()
    init(){cache.totalCostLimit=120*1024*1024}
    func image(_ url:URL,maxPixel:Int)->NSImage? {
        let key=(url.path+"@"+String(maxPixel)+(fileFingerprint(url) ?? "")) as NSString
        if let image=cache.object(forKey:key){return image}
        guard let source=CGImageSourceCreateWithURL(url as CFURL,[kCGImageSourceShouldCache:false] as CFDictionary),let cg=CGImageSourceCreateThumbnailAtIndex(source,0,[kCGImageSourceCreateThumbnailFromImageAlways:true,kCGImageSourceThumbnailMaxPixelSize:maxPixel,kCGImageSourceCreateThumbnailWithTransform:true] as CFDictionary) else{return nil}
        let image=NSImage(cgImage:cg,size:NSSize(width:cg.width,height:cg.height));cache.setObject(image,forKey:key,cost:cg.width*cg.height*4);return image
    }
}
