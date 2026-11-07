import Foundation
import AppKit

struct ReleaseHints:Decodable {var artist:String;var title:String;var barcode:String;var catno:String}
struct ReleaseCandidate:Decodable,Identifiable {
    var id:Int;var title:String;var year:String;var country:String;var format:String
    var catno:String;var variant:String;var url:String;var reasons:[String]
    var detail:String {[year,country,format,variant].filter{!$0.isEmpty}.joined(separator:" · ")}
}
struct ReleaseAdvice:Decodable {var hints:ReleaseHints;var candidates:[ReleaseCandidate];var message:String}

extension StudioModel {
    func cancelReleaseAdvice(clear:Bool=false) {
        adviceWorkItem?.cancel();adviceWorkItem=nil;adviceGeneration=UUID()
        if let process=adviceProcess,process.isRunning {process.terminate()}
        adviceProcess=nil
        if discovering {adviceStatus="Search stopped; you can search again later."}
        discovering=false
        if clear {adviceCandidates=[];adviceStatus="";adviceArtist="";adviceTitle="";adviceBarcode="";adviceCatalog="";adviceFormat=""}
    }
    func scheduleReleaseAdvice() {
        cancelReleaseAdvice(clear:true)
        guard mode == .scans,discogs.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty,!queueRunning,!restoringProject else{return}
        let work=DispatchWorkItem{[weak self] in self?.findReleaseAdvice(recognize:true)}
        adviceWorkItem=work;DispatchQueue.main.asyncAfter(deadline:.now()+0.7,execute:work)
    }
    func findReleaseAdvice(recognize:Bool) {
        guard !busy,!inputs.isEmpty,let resources=Bundle.main.resourceURL else{return}
        cancelReleaseAdvice();adviceCandidates=[]
        let generation=UUID();adviceGeneration=generation
        let cache=FileManager.default.urls(for:.cachesDirectory,in:.userDomainMask)[0].appendingPathComponent("com.repriselabs.Sleeve/Advice/"+UUID().uuidString)
        do {
            try FileManager.default.createDirectory(at:cache,withIntermediateDirectories:true)
            let request:[String:Any]=["action":"releaseAdvice","inputs":inputs.map{["path":$0.url.path,"part":$0.part,"reference":$0.reference]},"recognize":recognize,"artist":adviceArtist,"title":adviceTitle,"barcode":adviceBarcode,"catno":adviceCatalog,"format":adviceFormat]
            let path=cache.appendingPathComponent("request.json");try JSONSerialization.data(withJSONObject:request).write(to:path)
            let process=Process()
            let runtime=FileManager.default.urls(for:.applicationSupportDirectory,in:.userDomainMask)[0].appendingPathComponent("com.repriselabs.Sleeve/Runtime/bin/python3")
            process.executableURL=FileManager.default.isExecutableFile(atPath:runtime.path) ? runtime : URL(fileURLWithPath:"/usr/bin/python3")
            process.arguments=[resources.appendingPathComponent("studio_bridge.py").path,path.path]
            var env=ProcessInfo.processInfo.environment;env["PYTHONUNBUFFERED"]="1";env["PYTHONDONTWRITEBYTECODE"]="1";process.environment=env
            let pipe=Pipe();process.standardOutput=pipe;process.standardError=pipe
            let reader=PipeReader{[weak self] event in DispatchQueue.main.async {
                guard let self,self.adviceGeneration==generation else{return}
                if let advice=event.advice {
                    if recognize {self.adviceArtist=advice.hints.artist;self.adviceTitle=advice.hints.title;self.adviceBarcode=advice.hints.barcode;self.adviceCatalog=advice.hints.catno}
                    self.adviceCandidates=advice.candidates;self.adviceStatus=advice.message
                }
                if event.event=="error" {self.adviceStatus=event.message ?? "The search didn't succeed."}
            }}
            let searching=["Reading text and barcodes; then searching Discogs…","Searching Discogs for possible releases…"]
            adviceProcess=process;discovering=true;adviceStatus=recognize ? searching[0] : searching[1]
            try process.run()
            DispatchQueue.global(qos:.utility).async {[weak self] in
                while true {let data=pipe.fileHandleForReading.availableData;if data.isEmpty{break};reader.accept(data)}
                reader.finish();process.waitUntilExit()
                DispatchQueue.main.async {
                    try? FileManager.default.removeItem(at:cache)
                    guard let self,self.adviceGeneration==generation else{return}
                    self.discovering=false;self.adviceProcess=nil
                    if process.terminationStatus != 0 && searching.contains(self.adviceStatus) {   // geen eerdere foutmelding overschrijven
                    self.adviceStatus="The search didn't finish. You can fill in the details yourself and search again."}
                }
            }
        } catch {discovering=false;adviceProcess=nil;adviceStatus="Release suggestions couldn't be started.";try? FileManager.default.removeItem(at:cache)}
    }
    func chooseRelease(_ candidate:ReleaseCandidate) {
        guard !busy,let url=URL(string:candidate.url),url.scheme=="https",url.host=="www.discogs.com",url.path=="/release/\(candidate.id)" else{return}
        discogs=candidate.url;references=[];referenceURL=nil;proposals=[];if panel == .advice {panel=nil}
        adviceStatus="Chosen: \(candidate.title). Check the release on Discogs."
    }
    var discogsSearchURL:URL? {
        let query=[adviceArtist,adviceTitle,adviceBarcode,adviceCatalog].filter{!$0.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty}.joined(separator:" ")
        guard !query.isEmpty else{return nil}
        var url=URLComponents(string:"https://www.discogs.com/search/")!
        url.queryItems=[URLQueryItem(name:"q",value:query),URLQueryItem(name:"type",value:"release")]
        return url.url
    }
}
