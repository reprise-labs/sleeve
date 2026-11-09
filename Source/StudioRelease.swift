import Foundation
import AppKit

/// Release-gegevens van Discogs (scan_release.py) voor het bevestigingsvenster.
struct ReleaseInfo: Codable, Equatable {
    var id:Int; var url:String; var artist:String; var title:String; var year:String
    var country:String; var label:String; var catno:String; var format:String; var formatText:String
    var qty:Int; var colour:String; var packaging:String; var packagingLabel:String
    var packagingFromDiscogs:Bool; var sides:[String]; var slots:[String]; var thumbs:[String]?
}

let packagingChoices:[(String,String)] = [("jewel","Jewel case"),("slimjewel","Slim jewel case"),("superjewel","Super Jewel Box"),
                                          ("digipak","Digipak"),("cardsleeve","Cardboard sleeve"),("sleeve","Sleeve (vinyl)"),("gatefold","Gatefold sleeve (vinyl)"),("unknown","Other / unknown")]

extension StudioModel {
    private var releaseMemoryURL:URL? { inputs.first.map{$0.url.deletingLastPathComponent().appendingPathComponent(".sleeve-release.json")} }

    /// Na het inslepen: een eerder bevestigde release van deze map overnemen, anders het venster tonen.
    func offerReleaseConfirmation() {
        guard !inputs.isEmpty,!restoringProject,!queueRunning else{return}
        if releaseConfirmed {return}
        // per set scans onthouden: een map kan meerdere releases bevatten (bv. promo's in één map)
        let names=Set(inputs.filter{!$0.reference}.map{$0.url.lastPathComponent})
        if let saved=savedReleases().first(where:{!names.isEmpty && names.isSubset(of:Set($0.files ?? []))}) {
            discogs=saved.discogs;releaseYear=saved.year;packaging=saved.packaging;mediaFormat=saved.format;releaseInfo=saved.info;releaseConfirmed=true
            releaseStatus="Release remembered for these scans: \(saved.info?.title ?? saved.discogs)"
            if emptySlots.isEmpty && arrangedCount==0, let parts=saved.info?.slots {for part in parts {addSlot(part:part)}}
            return
        }
        DispatchQueue.main.async {[weak self] in
            guard let self,self.panel==nil,!self.busy else{return}
            self.panel = .release
            if !self.discogs.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty && self.releaseInfo==nil {self.loadReleaseInfo()}
        }
    }

    /// Release-gegevens ophalen (bridge: action releaseInfo).
    func loadReleaseInfo() {
        let link=discogs.trimmingCharacters(in:.whitespacesAndNewlines)
        guard !link.isEmpty,let resources=Bundle.main.resourceURL else{releaseStatus="Paste a Discogs link or choose a release first.";return}
        let cache=FileManager.default.urls(for:.cachesDirectory,in:.userDomainMask)[0].appendingPathComponent("com.repriselabs.Sleeve/Release/"+UUID().uuidString)
        do {
            try FileManager.default.createDirectory(at:cache,withIntermediateDirectories:true)
            let request:[String:Any]=["action":"releaseInfo","discogs":link,"inputs":[]]
            let path=cache.appendingPathComponent("request.json");try JSONSerialization.data(withJSONObject:request).write(to:path)
            let process=Process()
            let runtime=FileManager.default.urls(for:.applicationSupportDirectory,in:.userDomainMask)[0].appendingPathComponent("com.repriselabs.Sleeve/Runtime/bin/python3")
            process.executableURL=FileManager.default.isExecutableFile(atPath:runtime.path) ? runtime : URL(fileURLWithPath:"/usr/bin/python3")
            process.arguments=[resources.appendingPathComponent("studio_bridge.py").path,path.path]
            var env=ProcessInfo.processInfo.environment;env["PYTHONUNBUFFERED"]="1";env["PYTHONDONTWRITEBYTECODE"]="1";process.environment=env
            let pipe=Pipe();process.standardOutput=pipe;process.standardError=pipe
            let reader=PipeReader{[weak self] event in DispatchQueue.main.async {
                guard let self else{return}
                if let info=event.info {
                    self.releaseInfo=info;self.releaseYear=info.year
                    self.packaging=info.packaging=="unknown" ? "unknown" : info.packaging
                    self.releaseStatus=info.packagingFromDiscogs ? "Found on Discogs. Check the details." : "Discogs doesn't say how this release is packed. Choose the packaging."
                }
                if event.event=="error" {self.releaseStatus=event.message ?? "The release couldn't be loaded."}
            }}
            releaseLoading=true;releaseStatus="Fetching the release from Discogs…"
            try process.run()
            DispatchQueue.global(qos:.utility).async {[weak self] in
                while true {let data=pipe.fileHandleForReading.availableData;if data.isEmpty{break};reader.accept(data)}
                reader.finish();process.waitUntilExit()
                DispatchQueue.main.async {self?.releaseLoading=false}
            }
        } catch {releaseLoading=false;releaseStatus="The release couldn't be loaded."}
    }

    /// "Ja, dit klopt": formaat, verpakking en jaartal vastleggen, vakken aanmaken, per map onthouden.
    func confirmRelease() {
        guard let info=releaseInfo else{return}
        if info.format=="cd" || info.format=="vinyl" {mediaFormat=info.format}
        if releaseYear.trimmingCharacters(in:.whitespaces).isEmpty {releaseYear=info.year}
        var parts=info.slots
        if info.format=="vinyl" && packaging=="gatefold" && !parts.contains("inside") {parts.insert("inside",at:min(2,parts.count))}
        if info.format=="vinyl" && packaging != "gatefold" {parts.removeAll{$0=="inside"}}
        let existing=Set(slots.map{$0.part})
        if arrangedCount==0 {
            for part in parts where !existing.contains(part) {
                let slot=addSlot(part:part)
                // een scan die al naar dit onderdeel heet (front.jpeg, cd.png …) gaat meteen in dit vak
                if let item=unassignedInputs.first(where:{$0.url.deletingPathExtension().lastPathComponent.lowercased()==part}) {assign(item.id,to:slot)}
            }
        }
        releaseConfirmed=true;panel=nil
        releaseStatus="Release confirmed: \(info.artist) – \(info.title) (\(releaseYear))"
        if let url=releaseMemoryURL {
            let files=inputs.filter{!$0.reference}.map{$0.url.lastPathComponent}
            let saved=SavedRelease(discogs:discogs,year:releaseYear,packaging:packaging,format:mediaFormat,info:info,files:files)
            // andere sets in dezelfde map blijven bewaard; een set met (deels) dezelfde scans wordt vervangen
            let others=savedReleases().filter{Set($0.files ?? []).isDisjoint(with:Set(files))}
            try? JSONEncoder().encode(others+[saved]).write(to:url)
        }
        if !unassignedInputs.isEmpty {   // Sleeve vult op feiten in wat vaststaat; de rest sleep je zelf
            suggestArrangement()
            DispatchQueue.main.asyncAfter(deadline:.now()+0.5) {[weak self] in if self?.panel==nil {self?.panel = .arrange}}
        }
    }
    func rejectRelease() {releaseInfo=nil;discogs="";releaseStatus="Choose another release.";findReleaseAdvice(recognize:false)}
    func skipRelease() {releaseConfirmed=true;panel=nil;releaseStatus="No Discogs release. Choose CD or vinyl and the packaging yourself."}
}

struct SavedRelease: Codable {var discogs:String;var year:String;var packaging:String;var format:String;var info:ReleaseInfo?;var files:[String]?}

extension StudioModel {
    /// Bevestigde releases in de map van de scans (oude opslag zonder bestandenlijst telt niet mee).
    func savedReleases()->[SavedRelease] {
        guard let url=inputs.first.map({$0.url.deletingLastPathComponent().appendingPathComponent(".sleeve-release.json")}),let data=try? Data(contentsOf:url) else{return []}
        return (try? JSONDecoder().decode([SavedRelease].self,from:data)) ?? []
    }
}
