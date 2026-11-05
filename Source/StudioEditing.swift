import SwiftUI
import AppKit
import ImageIO

struct StudioScanRecipe:Codable {
    var inputs:[MediaItem]
    var discogs:String
    var variant:String
    var useNames:Bool
    var useStand:Bool
    var useColour:Bool
}
struct StudioEditingSession {
    var workspace:WorkspaceSnapshot
    var target:MediaItem
    var retry:Bool
}
extension StudioModel {
    func openCrop(_ item:MediaItem) {
        guard !busy,!queueRunning,activeQueueID==nil else{return}
        cropTarget=item;panel = .crop
    }
    func openRetry(_ item:MediaItem) {
        guard !busy,!queueRunning,activeQueueID==nil else{return}
        retryTarget=item;panel = .retry
    }
    func originalScanRun(for item:MediaItem)->StudioRun? {
        func key(_ url:URL)->String{url.resolvingSymlinksInPath().standardizedFileURL.path}
        var urls:Set<String>=[key(item.url)];if let source=item.source{urls.insert(key(source))}
        for run in runs.reversed() where run.success {
            let matching=run.workspace.outputs.filter{urls.contains(key($0.url))}
            if !matching.isEmpty && (run.processedPaths==nil || matching.contains{run.processedPaths!.map{key($0)}.contains(key($0.url))}) && (run.action=="scan" || (run.action==nil && run.workspace.mode == .scans)) {return run}
            for previous in matching {if let source=previous.source{urls.insert(key(source))};if let old=previous.previousVersion{urls.insert(key(old))}}
        }
        return nil
    }
    func scanSettings(for item:MediaItem)->WorkspaceSnapshot {
        guard let run=originalScanRun(for:item) else {return captureWorkspace()}
        var value=run.workspace
        if let recipe=run.scanRecipe {value.inputs=recipe.inputs;value.discogs=recipe.discogs;value.variant=recipe.variant;value.useNames=recipe.useNames;value.useStand=recipe.useStand;value.useColour=recipe.useColour}
        return value
    }
    func prepareEditing(_ item:MediaItem,retry:Bool)->Bool {
        guard !busy,!queueRunning,activeQueueID==nil else{return false}
        if outputFolder==nil{chooseOutput();guard outputFolder != nil else{return false}}
        // Preserve the initial result too, including an imported image with no run history.
        runs.append(StudioRun(label:"Vorige versie · "+partLabel(item.part),success:true,workspace:captureWorkspace(),action:"snapshot"))
        editingSession=StudioEditingSession(workspace:captureWorkspace(),target:item,retry:retry)
        lastEditingWasRetry=retry;panel=nil
        return true
    }
    func saveCircle(target:MediaItem,source:URL,signature:String,x:Double,y:Double,diameter:Double,part:String) {
        guard prepareEditing(target,retry:false) else{return}
        launch(action:"manualCrop",rowsOverride:[MediaItem(url:source,part:part)],extra:["sourceSignature":signature,"cropX":x,"cropY":y,"cropDiameter":diameter,"cropPart":part])
        if !busy && editingSession != nil {finishEditing(success:false);lastEditingWasRetry=false}
    }
    func retryPart(target:MediaItem,sources:[MediaItem],settings:WorkspaceSnapshot) {
        guard !sources.isEmpty,prepareEditing(target,retry:true) else{return}
        let rows=sources.map{MediaItem(url:$0.url,part:target.part)}
        launch(action:"scan",rowsOverride:rows,extra:["rerunPart":target.part,"discogs":settings.discogs,"variant":settings.variant,"useNames":settings.useNames,"useStand":settings.useStand,"useColour":settings.useColour])
        if !busy && editingSession != nil {finishEditing(success:false);lastEditingWasRetry=false}
    }
    @discardableResult func finishEditing(success:Bool)->Bool {
        guard let session=editingSession else{return false}
        let produced=outputs;let newReviews=reviews;let destination=lastJobFolder
        let messages=warnings;let log=logText;let state=stateText;let error=errorMessage
        restoreWorkspace(session.workspace)
        warnings=messages;logText=log;stateText=state;errorMessage=error
        if success,produced.count==1 {
            var replacement=produced[0];replacement.id=session.target.id;replacement.previousVersion=session.target.url
            if session.retry{replacement.part=session.target.part}
            if let index=outputs.firstIndex(where:{$0.id==session.target.id}) {outputs[index]=replacement}else{outputs.append(replacement)}
            if let record=newReviews[replacement.url.path]{reviews[replacement.url.path]=record}
            selectedID=replacement.id;showResults=true;compare=0.5;lastJobFolder=destination
        } else {selectedID=session.target.id}
        editingSession=nil
        return true
    }
}
