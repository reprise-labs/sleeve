import SwiftUI
import AppKit
import UniformTypeIdentifiers
import ImageIO
import Combine

let supportedExtensions: Set<String> = ["png","jpg","jpeg","tif","tiff","bmp","webp"]
let partChoices = ["front","back","inside","insert","inlay","sidea","sideb","sidec","sided","cd","cd1","cd2","sticker"]
func partLabel(_ value: String) -> String {
    ["front":"Voorkant","back":"Achterkant","inside":"Binnenzijde","insert":"Inlegvel","inlay":"Inlay","sidea":"Kant A","sideb":"Kant B","sidec":"Kant C","sided":"Kant D","cd":"Cd","cd1":"Cd 1","cd2":"Cd 2","sticker":"Sticker"][value] ?? value
}
enum WorkMode: String, CaseIterable, Identifiable, Codable {
    case scans = "Scans verwerken", colour = "Kleur aanpassen", names = "Namen aanpassen"
    var id: String { rawValue }
    var icon: String { switch self {case .scans:return "scanner";case .colour:return "slider.horizontal.3";case .names:return "tag"} }
    var caption: String { switch self {case .scans:return "Eén uitgave · cd en vinyl apart";case .colour:return "Nieuwe kleurvoorstellen voor bestaande afbeeldingen";case .names:return "Controleer de namen en bewaar nieuwe kopieën"} }
}
struct MediaItem: Identifiable, Hashable, Codable {
    var id = UUID()
    var url: URL
    var part: String = "front"
    var reference = false
    var source: URL? = nil
    var partial = false
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
struct BridgeFile: Decodable { var path: String; var source: String?; var title: String?; var partial: Bool? }
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
    var audits: [ImageAudit]?
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
    @Published var useColour = false
    @Published var variant = ""
    @Published var referenceFromDiscogs = true
    @Published var references: [MediaItem] = []
    @Published var referenceURL: URL?
    @Published var strength = 1.0
    @Published var colourScope = "vinyl"
    @Published var colourBatch = false
    @Published var proposals: [NameProposal] = []
    @Published var outputFolder: URL?
    @Published var lastJobFolder: URL?
    @Published var measuredProgress: Double?
    @Published var currentPart: Int?
    @Published var totalParts: Int?
    @Published var progressPhase = ""
    @Published var busy = false
    @Published var cancelled = false
    @Published var stateText = "Klaar om te beginnen"
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
    @Published var projectSaveText = "Nog niet bewaard"
    @Published var projectID = UUID()
    @Published var runs: [StudioRun] = []
    @Published var reviews: [String:ReviewRecord] = [:]
    @Published var queue: [StudioQueueItem] = []
    @Published var recentProjects: [URL] = []
    @Published var queueRunning = false
    @Published var activeQueueID: UUID?
    @Published var panel: StudioPanel?
    var showQueue: Bool {get{panel == .queue} set{if newValue{panel = .queue}else if panel == .queue{panel=nil}}}
    var showReview: Bool {get{panel == .review} set{if newValue{panel = .review}else if panel == .review{panel=nil}}}
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
    var displayItems: [MediaItem] { showResults ? outputs : inputs }
    var selected: MediaItem? { displayItems.first(where: {$0.id == selectedID}) ?? displayItems.first }
    var selectedInput: MediaItem? {
        guard let selected else { return nil }
        if showResults, let source = selected.source { return inputs.first(where: {$0.url.resolvingSymlinksInPath().path == source.resolvingSymlinksInPath().path}) }
        return inputs.first(where: {$0.id == selected.id})
    }
    var selectedProposal: NameProposal? { guard let selected else{return nil};return proposals.first(where: {$0.source == selected.url.path || $0.source == selected.source?.path}) }
    var beforeURL: URL? { showResults ? selected?.source : nil }
    var inputCount: Int { inputs.filter{!$0.reference}.count }
    var canStart: Bool {
        guard !busy, inputCount > 0, outputFolder != nil else { return false }
        switch mode {
        case .scans:return true
        case .colour:return referenceURL != nil && selectedInput != nil
        case .names:return !proposals.isEmpty
        }
    }
    init(libraryDirectory: URL? = nil) {
        if let path=UserDefaults.standard.string(forKey:"outputFolder"),FileManager.default.fileExists(atPath:path){outputFolder=URL(fileURLWithPath:path)}
        libraryURL=(libraryDirectory ?? FileManager.default.urls(for:.applicationSupportDirectory,in:.userDomainMask)[0].appendingPathComponent("com.repriselabs.Sleeve")).appendingPathComponent("StudioLibrary.json")
        initializeLibrary()
    }
    func changeMode(_ newMode: WorkMode) {
        guard !busy else{return}
        if newMode != mode && !outputs.isEmpty {inputs=outputs.map{MediaItem(url:$0.url,part:$0.part)};outputs=[];proposals=[];stateText="Resultaatbeelden klaar voor de volgende stap"}
        mode=newMode;showResults=false;selectedID=inputs.first?.id;errorMessage=nil;zoom=1
    }
    func newEdition() {
        guard !busy else{return}
        saveExistingProject();restoringProject=true;defer{restoringProject=false}
        panel=nil;projectID=UUID();projectURL=nil;editionTitle="";runs=[];reviews=[:];projectSaveText="Nog niet bewaard"
        errorMessage=nil;logText="";cancelled=false;startedAt=nil;inputs=[];outputs=[];selectedID=nil;showResults=false;discogs="";variant="";referenceURL=nil;references=[];proposals=[];demo=false;stateText="Klaar voor een nieuwe uitgave";lastJobFolder=nil
    }
    func pickImages() {
        guard !busy else{return}
        let panel=NSOpenPanel();panel.title="Kies de afbeeldingen van één uitgave";panel.allowsMultipleSelection=true;panel.canChooseDirectories=true;panel.canChooseFiles=true
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
        guard !files.isEmpty else{errorMessage="In deze selectie staan geen ondersteunde afbeeldingen.";return}
        if mode == .scans {
            let folders=Set((inputs.map{$0.url}+files).map{$0.deletingLastPathComponent().path})
            guard folders.count<=1 else{errorMessage="Verwerk één uitgave uit één bronmap. Kies eerst ‘Nieuwe uitgave’ voor een andere map.";return}
        }
        for url in files where !inputs.contains(where:{$0.url==url}) {
            var part=inferredPart(url.lastPathComponent)
            var reference=false
            let profile=url.deletingLastPathComponent().appendingPathComponent(".anouk-referenties.json")
            if let data=try? Data(contentsOf:profile),let json=(try? JSONSerialization.jsonObject(with:data)) as? [String:Any] {
                reference=(json["reference_files"] as? [String] ?? []).contains(url.lastPathComponent)
                for group in json["scan_groups"] as? [[String:Any]] ?? [] where (group["files"] as? [String] ?? []).contains(url.lastPathComponent) {
                    if let name=group["part"] as? String,partChoices.contains(name){part=name}
                }
            }
            inputs.append(MediaItem(url:url,part:part,reference:reference))
        }
        showResults=false;selectedID=inputs.first?.id;proposals=[];demo=false
        if outputFolder==nil {outputFolder=files[0].deletingLastPathComponent()}
        stateText="\(inputCount) bronbeelden · \(inputs.filter{$0.reference}.count) referenties"
    }
    func inferredPart(_ name:String)->String {
        let stem=URL(fileURLWithPath:name).deletingPathExtension().lastPathComponent.lowercased().replacingOccurrences(of:#"(?:_kleur(?:_\d+)?)+$"#,with:"",options:.regularExpression)
        for part in partChoices.sorted(by:{$0.count>$1.count}) where stem.range(of:"_"+part+#"(?:_\d+)?$"#,options:.regularExpression) != nil{return part}
        return "front"
    }
    func selectList(_ results:Bool) {showResults=results;selectedID=displayItems.first?.id;zoom=1}
    func updateSelectedPart(_ part:String) {
        guard !busy,let item=selectedInput,let i=inputs.firstIndex(where:{$0.id==item.id}) else{return}
        inputs[i].part=part;proposals=[]
    }
    func updateReference(_ value:Bool) {
        guard !busy,let item=selectedInput,let i=inputs.firstIndex(where:{$0.id==item.id}) else{return}
        inputs[i].reference=value;proposals=[]
    }
    func removeSelected() {
        guard !busy,let item=selectedInput else{return}
        inputs.removeAll{$0.id==item.id};selectedID=inputs.first?.id;proposals=[]
    }
    func chooseOutput() {
        let p=NSOpenPanel();p.title="Kies waar nieuwe resultaten mogen komen";p.canChooseFiles=false;p.canChooseDirectories=true;p.canCreateDirectories=true
        if p.runModal() == .OK,let url=p.url{outputFolder=url;UserDefaults.standard.set(url.path,forKey:"outputFolder")}
    }
    func chooseReference() {
        guard !busy else{return}
        let p=NSOpenPanel();p.title="Kies een referentiefoto";p.allowedContentTypes=[.image];p.allowsMultipleSelection=false
        if p.runModal() == .OK,let url=p.url{referenceURL=url;referenceFromDiscogs=false}
    }
    func revealOutput() {if let url=lastJobFolder ?? outputFolder{NSWorkspace.shared.open(url)}}
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
    func cancel() {
        guard let p=process,p.isRunning else{return}
        queueRunning=false;cancelled=true;stateText="Stoppen… reeds gemaakte resultaten blijven bewaard";p.terminate()
    }
    func loadDemo() {
        guard !busy,let resources=Bundle.main.resourceURL else{return}
        newEdition();mode = .colour
        let image=resources.appendingPathComponent("Samples/Voorbeeld_sidea.png")
        guard FileManager.default.fileExists(atPath:image.path) else{return}
        inputs=[MediaItem(url:image,part:"sidea")];selectedID=inputs[0].id
        referenceURL=resources.appendingPathComponent("Samples/Oranje-referentie.png");referenceFromDiscogs=false;demo=true
        if outputFolder==nil {outputFolder=FileManager.default.urls(for:.documentDirectory,in:.userDomainMask).first}
        stateText="Voorbeeldbeelden · er is nog niets verwerkt"
    }
    func launch(action:String) {
        guard !busy else{return}
        guard let resources=Bundle.main.resourceURL else{errorMessage="De onderdelen van de app zijn niet beschikbaar.";return}
        if action != "references" && action != "audit" && inputs.isEmpty {errorMessage="Voeg eerst afbeeldingen toe.";return}
        if ["scan","colour","namesApply"].contains(action) && outputFolder==nil {chooseOutput();guard outputFolder != nil else{return}}
        if action=="references" || action=="namesPreview",discogs.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty {errorMessage="Vul eerst de Discogs-link van de juiste uitgave in.";return}
        let rows: [MediaItem]
        if action=="audit" {rows=outputs}
        else if action=="colour" && !colourBatch {rows=selectedInput.map{[$0]} ?? []} else{rows=inputs}
        if action=="colour" && rows.isEmpty {errorMessage="Selecteer een bronbeeld voor het kleurvoorstel.";return}
        let cache=FileManager.default.urls(for:.cachesDirectory,in:.userDomainMask)[0].appendingPathComponent("com.repriselabs.Sleeve/Jobs/"+UUID().uuidString)
        do {
            try FileManager.default.createDirectory(at:cache,withIntermediateDirectories:true)
            var req: [String:Any] = ["action":action,"inputs":rows.map{["path":$0.url.path,"part":$0.part,"reference":$0.reference,"partial":$0.partial,"source":$0.source?.path ?? ""]},"discogs":discogs.trimmingCharacters(in:.whitespacesAndNewlines),"variant":variant,"useNames":useNames,"useStand":useStand,"useColour":useColour,"strength":strength,"scope":colourScope]
            if let folder=outputFolder{req["output"]=folder.path}
            if let ref=referenceURL{req["reference"]=ref.path}
            if action=="namesApply" {req["proposals"]=try JSONSerialization.jsonObject(with:JSONEncoder().encode(proposals))}
            let request=cache.appendingPathComponent("request.json");try JSONSerialization.data(withJSONObject:req,options:.prettyPrinted).write(to:request)
            busy=true;measuredProgress=nil;currentPart=nil;totalParts=nil;progressPhase="";cancelled=false;reportedError=false;receivedComplete=false;activeAction=action;activeLogFolder=cache;startedAt=Date();logText="";warnings=[];errorMessage=nil;stateText=action=="references" ? "Discogs-foto’s ophalen…" : "Voorbereiden…"
            if ["scan","colour","namesApply"].contains(action) {outputs=[];showResults=false}
            let p=Process();let runtime=FileManager.default.urls(for:.applicationSupportDirectory,in:.userDomainMask)[0].appendingPathComponent("com.repriselabs.Sleeve/Runtime/bin/python3");p.executableURL=FileManager.default.isExecutableFile(atPath:runtime.path) ? runtime : URL(fileURLWithPath:"/usr/bin/python3");p.arguments=[resources.appendingPathComponent("studio_bridge.py").path,request.path]
            var env=ProcessInfo.processInfo.environment;env["PYTHONUNBUFFERED"]="1";env["PYTHONDONTWRITEBYTECODE"]="1";p.environment=env
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
            busy=false;stateText="Niet gestart";errorMessage="De verwerking kon niet worden gestart: "+error.localizedDescription
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
            measuredProgress=event.fraction;currentPart=event.index ?? currentPart;totalParts=event.total ?? totalParts;progressPhase=event.phase ?? ""
        case "status":stateText=event.message ?? "Bezig…"
        case "warning":warnings.append(event.message ?? "Controleer het logboek")
        case "log":
            logText += (event.message ?? "")+"\n"
            if logText.count>100_000{logText=String(logText.suffix(100_000))}
        case "destination":if let p=event.path{lastJobFolder=URL(fileURLWithPath:p)}
        case "references":
            references=(event.files ?? []).map{MediaItem(url:URL(fileURLWithPath:$0.path))};referenceURL=nil;referenceFromDiscogs=true
            stateText=event.message ?? "Kies een referentiefoto"
        case "names":proposals=event.rows ?? []
        case "outputs":
            for file in event.files ?? [] {
                let url=URL(fileURLWithPath:file.path)
                if !outputs.contains(where:{$0.url==url}){
                    let source=file.source.flatMap{$0.isEmpty ? nil : URL(fileURLWithPath:$0)}
                    let part=inputs.first(where:{$0.url.resolvingSymlinksInPath().path == source?.resolvingSymlinksInPath().path})?.part ?? inferredPart(url.lastPathComponent)
                    outputs.append(MediaItem(url:url,part:part,source:source,partial:file.partial ?? false))
                }
            }
        case "error":reportedError=true;stateText=cancelled ? "Gestopt" : "Gestopt op een fout";if !cancelled{errorMessage=event.message}
        case "complete":receivedComplete=true;stateText=event.message ?? "Afgerond"
        default:break
        }
    }
    func didFinish(_ status:Int32) {
        busy=false;process=nil;readPipe=nil;reader=nil
        if let folder=activeLogFolder{try? logText.write(to:folder.appendingPathComponent("app-logboek.txt"),atomically:true,encoding:.utf8)}
        if cancelled {stateText="Gestopt door jou"}
        else if status != 0 || !receivedComplete {
            if !reportedError{errorMessage="De verwerking is niet afgerond. Bekijk het logboek voor de oorzaak."}
            stateText="Gestopt op een fout";showLog=true
        }
        if status==0 && !warnings.isEmpty {stateText += " · \(warnings.count) opmerkingen in het logboek";showLog=true}
        if ["scan","colour","namesApply"].contains(activeAction) && !outputs.isEmpty {showResults=true;selectedID=outputs.first?.id;if activeQueueID==nil && panel != .queue{showReview=true}}
        let success=status==0 && receivedComplete && !cancelled
        if !success && ["scan","colour","namesApply"].contains(activeAction) {for i in outputs.indices {outputs[i].partial=true}}
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
