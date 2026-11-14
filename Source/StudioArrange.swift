import Foundation
import AppKit

/// Voorstel van Sleeve voor één vak: deze scans samen, eventueel met de gelezen kant.
struct SuggestedGroup: Decodable { var files:[String]; var part:String; var why:String? }

/// Een vak in het indelingsscherm: één onderdeel (Front, Side A …) met zijn scans.
struct ScanSlot: Identifiable, Hashable {
    var id:String
    var part:String
    var items:[MediaItem]
}

/// Onderdelen die je als vak kunt kiezen, in de volgorde van een uitgave.
let slotParts = ["front","back","inside","insert","inlay","sidea","sideb","sidec","sided","cd","cd1","cd2","sticker","unknown"]

extension StudioModel {
    /// Scans die (nog) in geen vak zitten; referenties tellen niet mee.
    var unassignedInputs:[MediaItem] { inputs.filter{!$0.reference && ($0.group ?? "").isEmpty} }

    /// Alle vakken: eerst die met scans (in volgorde van de eerste scan), dan lege vakken.
    var slots:[ScanSlot] {
        var order:[String]=[];var members:[String:[MediaItem]]=[:]
        for item in inputs where !item.reference {
            guard let group=item.group,!group.isEmpty else{continue}
            if members[group]==nil {order.append(group)}
            members[group,default:[]].append(item)
        }
        let filled=order.map{ScanSlot(id:$0,part:members[$0]?.first?.part ?? "unknown",items:members[$0] ?? [])}
        return filled+emptySlots.filter{slot in members[slot.id]==nil}
    }
    var arrangedCount:Int { inputs.filter{!$0.reference && !($0.group ?? "").isEmpty}.count }
    var arrangementSummary:String {
        let filled=slots.filter{!$0.items.isEmpty}.count
        if arrangedCount==0 {return "Not arranged yet · drag the scans into the slots"}
        let rest=unassignedInputs.count
        return "\(filled) slot\(filled==1 ? "" : "s") · \(arrangedCount) scan\(arrangedCount==1 ? "" : "s")"+(rest>0 ? " · \(rest) not in a slot" : "")
    }

    @discardableResult func addSlot(part:String)->String {
        let id=UUID().uuidString
        emptySlots.append(ScanSlot(id:id,part:part,items:[]));return id
    }
    func slotPart(_ slot:String)->String {
        inputs.first(where:{$0.group==slot})?.part ?? emptySlots.first(where:{$0.id==slot})?.part ?? "unknown"
    }
    /// Scan in een vak leggen; hij krijgt het onderdeel van dat vak.
    func assign(_ id:UUID, to slot:String) {
        guard !busy,let i=inputs.firstIndex(where:{$0.id==id}) else{return}
        let part=slotPart(slot)
        inputs[i].group=slot;inputs[i].part=part;inputs[i].reference=false
        emptySlots.removeAll{$0.id==slot}
        proposals=[]
    }
    func unassign(_ id:UUID) {
        guard !busy,let i=inputs.firstIndex(where:{$0.id==id}) else{return}
        let slot=inputs[i].group;let part=inputs[i].part
        inputs[i].group=nil;inputs[i].part="unknown"
        // laatste scan uit een vak: het vak blijft (leeg) staan
        if let slot,!inputs.contains(where:{$0.group==slot}),!emptySlots.contains(where:{$0.id==slot}) {emptySlots.append(ScanSlot(id:slot,part:part,items:[]))}
        proposals=[]
    }
    func setSlotPart(_ slot:String,_ part:String) {
        guard !busy else{return}
        slotNotes[slot]=nil
        for i in inputs.indices where inputs[i].group==slot {inputs[i].part=part}
        if let e=emptySlots.firstIndex(where:{$0.id==slot}) {emptySlots[e].part=part}
        proposals=[]
    }
    func removeSlot(_ slot:String) {
        guard !busy else{return}
        for i in inputs.indices where inputs[i].group==slot {inputs[i].group=nil;inputs[i].part="unknown"}
        emptySlots.removeAll{$0.id==slot};slotNotes[slot]=nil
        proposals=[]
    }
    func clearArrangement() {
        guard !busy else{return}
        for i in inputs.indices {inputs[i].group=nil;if !inputs[i].reference {inputs[i].part="unknown"}}
        emptySlots=[];proposals=[];slotNotes=[:]
    }
    /// Alle scans van een vak in één keer naar een ander vak (bv. één onderdeel dat in twee stapels kwam).
    func moveSlot(_ from:String, to:String) {
        guard !busy,from != to else{return}
        let part=slotPart(to)
        for i in inputs.indices where inputs[i].group==from {inputs[i].group=to;inputs[i].part=part}
        emptySlots.removeAll{$0.id==to||$0.id==from};slotNotes[from]=nil;slotNotes[to]=nil
        proposals=[]
    }
    /// Voorstel van Sleeve toepassen op scans die nog in geen vak zitten (wat jij al
    /// indeelde, blijft staan).
    func applySuggestion(_ groups:[SuggestedGroup]) {
        for group in groups {
            let paths=Set(group.files.map{URL(fileURLWithPath:$0).resolvingSymlinksInPath().standardizedFileURL.path})
            let free=inputs.indices.filter{!inputs[$0].reference && (inputs[$0].group ?? "").isEmpty && paths.contains(inputs[$0].url.resolvingSymlinksInPath().standardizedFileURL.path)}
            guard !free.isEmpty else{continue}
            let part=slotParts.contains(group.part) ? group.part : "unknown"
            // een leeg vak voor dit onderdeel (uit de release) vullen; anders een nieuw vak
            let slot=emptySlots.first(where:{$0.part==part})?.id ?? UUID().uuidString
            for i in free {inputs[i].group=slot;inputs[i].part=part}
            emptySlots.removeAll{$0.id==slot}
            if let why=group.why,!why.isEmpty {slotNotes[slot]=why}
        }
    }

    func suggestArrangement() {
        guard !busy,!suggesting,!unassignedInputs.isEmpty,let resources=Bundle.main.resourceURL else{return}
        let cache=FileManager.default.urls(for:.cachesDirectory,in:.userDomainMask)[0].appendingPathComponent("com.repriselabs.Sleeve/Arrange/"+UUID().uuidString)
        do {
            try FileManager.default.createDirectory(at:cache,withIntermediateDirectories:true)
            let request:[String:Any]=["action":"suggestGroups","inputs":unassignedInputs.map{["path":$0.url.path,"part":$0.part,"reference":false]},"discogs":discogs.trimmingCharacters(in:.whitespacesAndNewlines),"format":mediaFormat,"slots":emptySlots.map{$0.part}]
            let path=cache.appendingPathComponent("request.json");try JSONSerialization.data(withJSONObject:request).write(to:path)
            let process=Process()
            let runtime=FileManager.default.urls(for:.applicationSupportDirectory,in:.userDomainMask)[0].appendingPathComponent("com.repriselabs.Sleeve/Runtime/bin/python3")
            process.executableURL=FileManager.default.isExecutableFile(atPath:runtime.path) ? runtime : URL(fileURLWithPath:"/usr/bin/python3")
            process.arguments=[resources.appendingPathComponent("studio_bridge.py").path,path.path]
            var env=ProcessInfo.processInfo.environment;env["PYTHONUNBUFFERED"]="1";env["PYTHONDONTWRITEBYTECODE"]="1";process.environment=env
            let pipe=Pipe();process.standardOutput=pipe;process.standardError=pipe
            let reader=PipeReader{[weak self] event in DispatchQueue.main.async {
                guard let self else{return}
                if let groups=event.groups {self.applySuggestion(groups)}
                if event.event=="complete" || event.event=="error" || event.event=="status" {self.suggestStatus=event.message ?? self.suggestStatus}
            }}
            suggesting=true;suggestStatus="Sorting the scans into stacks…";suggestProcess=process
            try process.run()
            DispatchQueue.global(qos:.utility).async {[weak self] in
                while true {let data=pipe.fileHandleForReading.availableData;if data.isEmpty{break};reader.accept(data)}
                reader.finish();process.waitUntilExit()
                DispatchQueue.main.async {
                    try? FileManager.default.removeItem(at:cache)
                    guard let self else{return}
                    self.suggesting=false;self.suggestProcess=nil
                    if process.terminationStatus != 0 && self.suggestStatus=="Sorting the scans into stacks…" {self.suggestStatus="The suggestion didn’t finish. You can drag the scans into slots yourself."}
                }
            }
        } catch {suggesting=false;suggestStatus="The suggestion couldn’t be started.";try? FileManager.default.removeItem(at:cache)}
    }
    func stopSuggestion() {suggestProcess?.terminate()}
}
