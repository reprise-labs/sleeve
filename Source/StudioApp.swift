import SwiftUI
import AppKit

@main struct SleeveApp: App {
    @StateObject private var model = StudioModel()
    @NSApplicationDelegateAdaptor(StudioAppDelegate.self) private var delegate
    var body: some Scene {
        WindowGroup("Sleeve") {
            // Feit (André): de donkere modus is onleesbaar; Sleeve is ontworpen op licht.
            StudioView(model:model).frame(minWidth:1100,minHeight:720).preferredColorScheme(.light)
                .onAppear { NSApp.appearance=NSAppearance(named:.aqua); delegate.onQuit = {model.prepareForQuit()}; if CommandLine.arguments.contains("--demo") && model.inputs.isEmpty {model.loadDemo()}
                    // test: --scans <map> laadt die scans meteen (zoals inslepen)
                    if let i=CommandLine.arguments.firstIndex(of:"--scans"),i+1<CommandLine.arguments.count,model.inputs.isEmpty {model.addURLs(CommandLine.arguments[i+1].split(separator:"|").map{URL(fileURLWithPath:String($0))})}
                    // test: --discogs <link> --dump <bestand>: release laden en bevestigen, daarna elke 5 s de indeling wegschrijven
                    if let i=CommandLine.arguments.firstIndex(of:"--discogs"),i+1<CommandLine.arguments.count {
                        let link=CommandLine.arguments[i+1]
                        DispatchQueue.main.asyncAfter(deadline:.now()+2){model.discogs=link;model.loadReleaseInfo()}
                        func waitConfirm(_ n:Int){DispatchQueue.main.asyncAfter(deadline:.now()+1){ if model.releaseInfo != nil && !model.releaseLoading {model.confirmRelease()} else if n<60 {waitConfirm(n+1)} }}
                        waitConfirm(0)
                    }
                    if let i=CommandLine.arguments.firstIndex(of:"--dump"),i+1<CommandLine.arguments.count {
                        let path=CommandLine.arguments[i+1]
                        func dump(_ n:Int){DispatchQueue.main.asyncAfter(deadline:.now()+5){
                            let rows=model.inputs.map{["file":$0.url.lastPathComponent,"part":$0.part,"group":$0.group ?? "","reference":$0.reference ? "yes":"no"]}
                            let slots=model.slots.map{["id":$0.id,"part":$0.part,"files":$0.items.map{$0.url.lastPathComponent}.joined(separator:",")]}
                            let all:[String:Any]=["t":n*5,"inputs":rows,"slots":slots,"suggest":model.suggestStatus,"release":model.releaseStatus]
                            if let d=try? JSONSerialization.data(withJSONObject:all,options:.prettyPrinted){try? d.write(to:URL(fileURLWithPath:path+"_\(n*5)s.json"))}
                            if n<24 {dump(n+1)}
                        }}
                        dump(1)
                    } }
        }.defaultSize(width:1380,height:900)
        .commands {
            CommandGroup(replacing:.newItem) {
                Button("New Release") {model.newEdition()}.keyboardShortcut("n").disabled(model.busy)
                Button("Open Project…") {model.pickProject()}.keyboardShortcut("o",modifiers:[.command,.shift]).disabled(model.busy)
                Button("Save Project") {if model.projectURL==nil{model.saveProjectAs()}else{model.saveExistingProject()}}.keyboardShortcut("s").disabled(model.busy)
                Button("Add Images…") {model.pickImages()}.keyboardShortcut("o").disabled(model.busy)
            }
            CommandGroup(replacing:.help) {
                Button("Sleeve Help") {model.helpTopic=nil;model.panel = .help}.keyboardShortcut("?")
            }
        }
    }
}
let studioInk = Color(red:0.15,green:0.20,blue:0.20)
let studioAccent = Color(red:0.16,green:0.38,blue:0.33)
let studioPaper = Color(red:0.96,green:0.95,blue:0.92)

struct StudioView: View {
    @ObservedObject var model: StudioModel
    var body: some View {
        VStack(spacing:0) {
            HStack(spacing:14) {
                Image(systemName:"opticaldisc.fill").font(.system(size:30)).foregroundStyle(studioAccent)
                VStack(alignment:.leading,spacing:2) {
                    Text("REPRISE LABS").font(.system(size:10,weight:.bold,design:.rounded)).tracking(2)
                    Text("Sleeve").font(.system(size:22,weight:.semibold,design:.serif))
                }
                Spacer()
                Text("Your scans. Carefully finished.").font(.system(size:13)).foregroundStyle(.secondary)
                Menu {
                    Button("Open Project…"){model.pickProject()}
                    Button(model.projectURL==nil ? "Save Project…" : "Save As…"){model.saveProjectAs()}
                    ForEach(model.recentProjects,id:\.self){url in Button(url.deletingPathExtension().lastPathComponent){model.openProject(url)}}
                } label:{Label("Project",systemImage:"folder")}.disabled(model.busy)
                Button{model.showQueue=true} label:{Label("Queue (\(model.pendingCount))",systemImage:"list.bullet.rectangle")}
                Button {model.newEdition()} label:{Label("New Release",systemImage:"plus")}.disabled(model.busy)
                Button {model.helpTopic=nil;model.panel = .help} label:{Label("Help",systemImage:"questionmark.circle")}
            }.padding(.horizontal,24).padding(.vertical,17).background(studioPaper)
            Divider()
            HStack(spacing:0) {
                sidebar.frame(width:190)
                Divider()
                VStack(spacing:0) {
                    HStack {
                        VStack(alignment:.leading,spacing:5) {
                            Text(model.mode.title).font(.system(size:23,weight:.semibold,design:.serif))
                            Text(model.mode.caption).font(.system(size:12)).foregroundStyle(.secondary)
                        }
                        Spacer()
                        if !model.outputs.isEmpty {
                            Picker("Images",selection:Binding(get:{model.showResults},set:{model.selectList($0)})) {
                                Text(model.mode == .colour ? "Originals" : "Sources").tag(false);Text(model.mode == .colour ? "New Colors" : "Results").tag(true)
                            }.pickerStyle(.segmented).labelsHidden().frame(width:205)
                        }
                    }.padding(22)
                    if let item=model.selected {
                        HStack {
                            Button("Adjust Round Crop…"){model.openCrop(item)}
                            if model.showResults {Button("Reprocess This Part…"){model.openRetry(item)}}
                            if item.previousVersion != nil {Text("Before = previous attempt · After = new attempt").font(.caption).foregroundStyle(.secondary)}
                            Spacer()
                        }.padding(.horizontal,22).disabled(model.busy || model.queueRunning)
                    }
                    preview.frame(maxWidth:.infinity,maxHeight:.infinity)
                    if !model.displayItems.isEmpty {filmstrip}
                }.frame(minWidth:500,maxWidth:.infinity)
                Divider()
                VStack(spacing:0) {ScrollView { inspector.padding(20) };Divider();saveControls.padding(20)}.frame(width:302).background(Color(nsColor:.controlBackgroundColor))
            }
            Divider()
            footer
            if model.showLog {
                ScrollView {Text(model.logText.isEmpty ? "The log appears as soon as processing starts." : model.logText).font(.system(size:11,design:.monospaced)).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading).padding(12)}.frame(height:140).background(Color(nsColor:.textBackgroundColor))
            }
        }
        .foregroundStyle(studioInk).tint(studioAccent)
        .onOpenURL{url in model.openProject(url)}
        .sheet(item:$model.panel){panel in
            switch panel {
            case .advice:ReleaseAdviceSheet(model:model)
            case .queue:StudioQueueView(model:model)
            case .review:StudioReviewView(model:model)
            case .crop:if let item=model.cropTarget{StudioCircleView(model:model,target:item)}
            case .retry:if let item=model.retryTarget{StudioRetryView(model:model,target:item)}
            case .arrange:StudioArrangeView(model:model)
            case .release:ReleaseConfirmSheet(model:model)
            case .help:StudioHelpView(model:model)
            }
        }
        .onDrop(of:["public.file-url"],isTargeted:nil) {providers in
            guard !model.busy else{return false}
            for provider in providers { _ = provider.loadObject(ofClass:URL.self){url,_ in if let url {Task{@MainActor in model.addURLs([url])}}} }
            return true
        }
        .alert("Quick check",isPresented:Binding(get:{model.errorMessage != nil},set:{if !$0{model.errorMessage=nil}})) {
            Button("Got it",role:.cancel){model.errorMessage=nil}
        } message: {Text(model.errorMessage ?? "")}
    }
    var sidebar: some View {
        VStack(alignment:.leading,spacing:7) {
            Text("WORKSPACE").font(.system(size:10,weight:.bold)).tracking(1.6).foregroundStyle(.secondary).padding(.horizontal,10).padding(.bottom,9)
            ForEach(WorkMode.allCases) {mode in
                Button {model.changeMode(mode)} label: {
                    Label(mode.title,systemImage:mode.icon).font(.system(size:13,weight:model.mode==mode ? .semibold : .regular)).frame(maxWidth:.infinity,alignment:.leading).padding(.horizontal,11).padding(.vertical,12)
                        .background(model.mode==mode ? studioAccent.opacity(0.11) : .clear,in:RoundedRectangle(cornerRadius:9))
                }.buttonStyle(.plain).disabled(model.busy)
            }
            Button{model.showReview=true} label:{Label("Final Check",systemImage:"checklist").frame(maxWidth:.infinity,alignment:.leading).padding(11)}.buttonStyle(.plain).disabled(model.outputs.isEmpty)
            if !model.runs.isEmpty {
                Menu("Earlier edits") {ForEach(model.runs.reversed()){run in Button(run.label+" · "+run.date.formatted(date:.abbreviated,time:.shortened)){model.showRun(run.id)}}}.disabled(model.busy)
            }
            Divider().padding(.vertical,13)
            Button {model.pickImages()} label:{Label("Add images",systemImage:"photo.on.rectangle.angled").frame(maxWidth:.infinity,alignment:.leading)}.buttonStyle(.plain).padding(10).disabled(model.busy)
            Text("Or drag a folder or images onto the workspace.").font(.system(size:11)).foregroundStyle(.secondary).padding(.horizontal,10)
            Spacer()
            Button("Open Preview") {model.loadDemo()}.buttonStyle(.plain).foregroundStyle(studioAccent).padding(10).disabled(model.busy)
            VStack(alignment:.leading,spacing:6) {
                Label("Locally on your Mac",systemImage:"desktopcomputer").font(.system(size:11,weight:.medium))
                Text("Originals are kept. Every run gets a new folder.").font(.system(size:11)).foregroundStyle(.secondary)
            }.padding(12).background(studioPaper,in:RoundedRectangle(cornerRadius:10))
        }.padding(14).padding(.top,14).background(Color(nsColor:.windowBackgroundColor))
    }
    @ViewBuilder var preview: some View {
        if let item=model.selected {
            VStack(spacing:12) {
                if model.mode == .colour {StudioColourResultHeader(model:model)}
                HStack {
                    Text(item.title).font(.system(size:12,weight:.medium)).lineLimit(1).truncationMode(.middle)
                    Spacer()
                    if item.reference {Text("Reference").font(.caption).foregroundStyle(.secondary)}
                    if item.partial {Text("Not finished").font(.caption).foregroundStyle(.orange)}
                    Button {model.openSelected()} label:{Image(systemName:"arrow.up.right.square")}.buttonStyle(.plain).help("Open the full image")
                }
                GeometryReader {geo in
                    ZStack {
                        Checkerboard().clipShape(RoundedRectangle(cornerRadius:14))
                        Group {
                            StudioThumbnail(url:item.url,maxPixel:2000).padding(12)
                            if let beforeURL=model.beforeURL,model.mode == .colour {
                                StudioThumbnail(url:beforeURL,maxPixel:2000).padding(12).frame(width:geo.size.width,height:geo.size.height)
                                    .mask(alignment:.leading){Rectangle().frame(width:geo.size.width*model.compare)}
                                if model.compare>0 && model.compare<1 {
                                    Rectangle().fill(.white).frame(width:2).offset(x:(model.compare-0.5)*geo.size.width)
                                    VStack {HStack{Text("Original");Spacer();Text("New color")}.font(.system(size:11,weight:.semibold)).padding(8).background(.regularMaterial);Spacer()}.padding(12)
                                }
                            }
                        }
                    }
                }
                if model.mode == .colour && model.beforeURL != nil {
                    HStack {Text("Original");Slider(value:Binding(get:{1-model.compare},set:{model.compare=1-$0}),in:0...1);Text("New color")}.font(.caption).padding(.horizontal,30)
                }
                if model.mode == .names,let row=model.selectedProposal {
                    VStack(alignment:.leading,spacing:5) {Text("SUGGESTED NAME").font(.system(size:9,weight:.bold)).tracking(1);Text(row.newName).font(.system(size:12,weight:.medium)).textSelection(.enabled)}.padding(12).frame(maxWidth:.infinity,alignment:.leading).background(studioAccent.opacity(0.08),in:RoundedRectangle(cornerRadius:9))
                }
            }.padding(.horizontal,22).padding(.bottom,18)
        } else {
            VStack(spacing:16) {
                Image(systemName:"opticaldisc").font(.system(size:66,weight:.ultraLight)).foregroundStyle(studioAccent.opacity(0.65))
                Text("Give your scans some room").font(.system(size:29,weight:.medium,design:.serif))
                Text("Choose the images of one release.\nThe result is saved in a new folder.").font(.system(size:14)).foregroundStyle(.secondary).multilineTextAlignment(.center).lineSpacing(5)
                Button("Choose Images…") {model.pickImages()}.buttonStyle(.borderedProminent).controlSize(.large).disabled(model.busy)
                Text("Process CD and vinyl separately").font(.caption).foregroundStyle(.secondary)
            }.frame(maxWidth:.infinity,maxHeight:.infinity).padding(30)
        }
    }
    var filmstrip: some View {
        ScrollView(.horizontal) {
            LazyHStack(spacing:12) {
                ForEach(model.displayItems) {item in
                    Button {model.selectedID=item.id} label:{
                        VStack(spacing:6) {
                            ZStack(alignment:.topTrailing) {
                                RoundedRectangle(cornerRadius:7).fill(Color.white)
                                StudioThumbnail(url:item.url,maxPixel:220).padding(5)
                                if item.reference {Image(systemName:"bookmark.fill").font(.caption).padding(4).background(.regularMaterial,in:Circle())}
                            }.frame(width:88,height:80).overlay(RoundedRectangle(cornerRadius:7).stroke(model.selected?.id==item.id ? studioAccent : .clear,lineWidth:2))
                            Text(model.mode == .colour ? partLabel(item.part) : model.showResults ? partLabel(item.part) : item.title).font(.system(size:10)).lineLimit(1).truncationMode(.middle).frame(width:88)
                        }.opacity(item.reference ? 0.65 : 1)
                    }.buttonStyle(.plain)
                }
            }.padding(16)
        }.frame(height:132).background(studioPaper)
    }
    @ViewBuilder var inspector: some View {
        if model.mode == .colour {StudioColourControls(model:model)} else {standardInspector}
    }
    var standardInspector: some View {
        VStack(alignment:.leading,spacing:18) {
            TextField("Project / release name",text:$model.editionTitle).textFieldStyle(.roundedBorder)
            HStack{Text(model.projectURL?.lastPathComponent ?? "Project not saved yet").lineLimit(1).truncationMode(.middle);Spacer();if model.projectURL != nil {Image(systemName:"externaldrive.badge.checkmark")}}.font(.caption).foregroundStyle(.secondary)
            if model.projectURL != nil {Text(model.projectSaveText).font(.caption).foregroundStyle(.secondary)}
            sectionTitle("01", "Release & reference")
            if model.mode == .scans {
                VStack(alignment:.leading,spacing:6) {
                    if let info=model.releaseInfo,model.releaseConfirmed {
                        Text("\(info.artist) – \(info.title)").font(.system(size:13,weight:.semibold))
                        Text([model.releaseYear,info.country,info.formatText,packagingChoices.first{$0.0==model.packaging}?.1 ?? ""].filter{!$0.isEmpty}.joined(separator:" · ")).font(.caption).foregroundStyle(.secondary)
                    } else {
                        Text(model.releaseConfirmed ? "No Discogs release – choose the format and packaging below." : "No release confirmed yet.").font(.caption).foregroundStyle(model.releaseConfirmed ? Color.secondary : Color.orange)
                    }
                    Button(model.releaseInfo==nil ? "Choose Release…" : "Change Release…"){model.panel = .release}.disabled(model.busy || model.inputs.isEmpty)
                }.padding(10).frame(maxWidth:.infinity,alignment:.leading).background(studioAccent.opacity(0.07),in:RoundedRectangle(cornerRadius:8))
            }
            TextField("Discogs link (optional for scans)",text:$model.discogs).textFieldStyle(.roundedBorder).disabled(model.busy)
                .onChange(of:model.discogs){ model.cancelReleaseAdvice();model.proposals=[];model.references=[];if model.referenceFromDiscogs {model.referenceURL=nil}}
            if model.mode == .scans {
                Text("Format").font(.system(size:12,weight:.semibold))
                Picker("Format",selection:$model.mediaFormat){Text("Automatic").tag("auto");Text("CD").tag("cd");Text("Vinyl").tag("vinyl")}
                    .pickerStyle(.segmented).labelsHidden().disabled(model.busy)
                Text(model.mediaFormat=="auto" ? "From the Discogs link, or CD when there is a CD slot." : "You chose \(model.mediaFormat=="cd" ? "CD" : "vinyl"): Sleeve cuts to those sizes, with or without Discogs.").font(.caption).foregroundStyle(.secondary)
                Picker("Packaging",selection:$model.packaging) {
                    Text("From Discogs").tag("auto")
                    ForEach(packagingChoices,id:\.0) {Text($0.1).tag($0.0)}
                }.disabled(model.busy)
                Text("Use of Discogs").font(.system(size:12,weight:.semibold))
                Toggle("Use file names",isOn:$model.useNames)
                Toggle("Rotate cover and record correctly",isOn:$model.useStand)
                Text("Check your results first. You can then fine-tune cover and record colors under ‘Adjust Color’.").font(.caption).foregroundStyle(.secondary)
            }
            if model.mode == .scans && !model.inputs.isEmpty {
                VStack(alignment:.leading,spacing:7) {
                    Text("Arrangement").font(.system(size:12,weight:.semibold))
                    Text(model.arrangementSummary).font(.caption).foregroundStyle(.secondary)
                    Button("Arrange Scans…"){model.panel = .arrange}.help("Drag the scans into slots: Front, Back, Side A, Side B …")
                }
            }
            if !model.inputs.isEmpty {
                VStack(alignment:.leading,spacing:7) {
                    HStack {
                        if model.discovering {ProgressView().controlSize(.small)}
                        Text(model.discovering ? "Identify Release…" : model.adviceCandidates.isEmpty ? "Find the Release" : "\(model.adviceCandidates.count) possible Discogs releases").font(.caption).foregroundStyle(.secondary)
                    }
                    Button("View Release Suggestions…"){model.panel = .advice}
                }
            }
            if model.mode == .names {
                TextField("Extra variant (optional)",text:$model.variant).textFieldStyle(.roundedBorder).onChange(of:model.variant){ model.proposals=[]}
                Text("Choose the part for each image below. Then fetch the names to check them.").font(.caption).foregroundStyle(.secondary)
                Button("Fetch Suggested Names") {model.previewNames()}.disabled(model.busy || model.discogs.isEmpty || model.inputCount==0)
                if !model.proposals.isEmpty {Label("\(model.proposals.count) names to review",systemImage:"checkmark.circle").font(.caption).foregroundStyle(studioAccent)}
            }
            if let item=model.selectedInput,!model.showResults {
                Divider();sectionTitle(model.mode == .colour ? "03" : "02","Selected image")
                Text(item.title).font(.caption).lineLimit(2)
                if model.mode == .names {
                    Picker("Part",selection:Binding(get:{model.selectedInput?.part ?? "front"},set:{model.updateSelectedPart($0)})) {ForEach(partChoices,id:\.self){Text(partLabel($0)).tag($0)}}
                }
                if model.mode == .scans {
                    Toggle("Use as reference only",isOn:Binding(get:{model.selectedInput?.reference ?? false},set:{model.updateReference($0)}))
                    Text("Label close-ups and other references are not processed as separate records. Known scan layouts are taken into account.").font(.caption).foregroundStyle(.secondary)
                }
                Button("Remove from Selection",role:.destructive) {model.removeSelected()}.buttonStyle(.plain).font(.caption).disabled(model.busy)
            }

        }.font(.system(size:12)).disabled(model.busy)
    }
    var saveControls: some View {
        VStack(alignment:.leading,spacing:12) {
            sectionTitle("↗",model.mode == .colour ? "Save New Color" : "Save")
            if model.mode == .colour {
                Label("Next to the source images",systemImage:"folder")
            } else {
            Button {model.chooseOutput()} label:{HStack{Image(systemName:"folder");Text(model.outputFolder?.lastPathComponent ?? "Choose an Output Folder…").lineLimit(1);Spacer();Image(systemName:"chevron.down").font(.caption2)}}.disabled(model.busy)
            }
            Text(model.mode == .colour ? "New color copies go into the same folder as the chosen images, with _kleur in the file name. Originals are kept." : "A new subfolder for every run. Originals are kept.").font(.caption).foregroundStyle(.secondary)
            Button {model.start()} label:{Text(model.mode == .scans ? "Process Scans" : model.mode == .colour ? model.colourActionTitle : "Save with New Names").frame(maxWidth:.infinity).padding(.vertical,5)}.buttonStyle(.borderedProminent).controlSize(.large).disabled(!model.canStart)
            Button("Add This Task to the Queue"){model.enqueueCurrent()}.disabled(!model.canStart)
            if model.projectURL==nil {Button("Save as Project…"){model.saveProjectAs()}.font(.caption)}
            if model.demo {Text("These are reduced sample images for trying out the app.").font(.caption).foregroundStyle(.secondary)}
        }.font(.system(size:12)).disabled(model.busy)
    }
    func sectionTitle(_ number:String,_ title:String)->some View {
        HStack(spacing:8){Text(number).font(.system(size:10,weight:.semibold)).foregroundStyle(studioAccent);Text(title).font(.system(size:13,weight:.semibold))}
    }
    var footer: some View {
        VStack(alignment:.leading,spacing:8) {
            if model.busy {
                TimelineView(.periodic(from:.now,by:1)) {context in
                    VStack(alignment:.leading,spacing:7) {
                        HStack {
                            if model.activePartCount>1 {Text("\(model.activePartCount) parts in progress").fontWeight(.semibold)}
                            else if let index=model.currentPart,let total=model.totalParts {Text(model.progressPhase=="Final Check" ? "File \(index) of \(total) checking" : "Part \(index) of \(total)").fontWeight(.semibold)}
                            else {Text(model.completedParts>0 ? "Finishing" : "Preparing").fontWeight(.semibold)}
                            if model.mode == .scans,let total=model.totalParts {Text("· \(model.completedParts) of \(total) parts processed").foregroundStyle(.secondary)}
                            Spacer()
                            if let start=model.startedAt {Text("Total time "+durationText(context.date.timeIntervalSince(start))).monospacedDigit()}
                        }.font(.system(size:12))
                        HStack {
                            if model.activePartCount>1,let index=model.currentPart {Text("Part \(index) ·").foregroundStyle(.secondary)}
                            Text(model.progressPhase.isEmpty ? "Preparing" : model.progressPhase)
                            Spacer()
                            if let start=model.phaseStartedAt {Text("This step "+durationText(context.date.timeIntervalSince(start))).monospacedDigit().foregroundStyle(.secondary)}
                        }.font(.system(size:12))
                        if let progress=model.measuredProgress {
                            ProgressView(value:progress,total:1).progressViewStyle(.linear).tint(studioAccent).scaleEffect(x:1,y:2).frame(height:10).accessibilityLabel("Measured progress of the current step")
                            HStack {Text("\(Int((progress*100).rounded()))% of this step");if let done=model.progressUnitsDone,let total=model.progressUnitsTotal {Text("· \(done) / \(total)")}}.font(.caption).monospacedDigit().foregroundStyle(.secondary)
                        } else {
                            ProgressView().progressViewStyle(.linear).tint(studioAccent).scaleEffect(x:1,y:2).frame(height:10).accessibilityLabel("Step running, percentage unknown")
                            Text("Working · no reliable percentage is available for this step.").font(.caption).foregroundStyle(.secondary)
                        }
                        if !model.progressDetail.isEmpty {Text(model.progressDetail).font(.caption).foregroundStyle(.secondary)}
                        if let last=model.lastProgressAt,context.date.timeIntervalSince(last)>20 {Text("Last progress update "+durationText(context.date.timeIntervalSince(last))+" ago. Remaining time can't be estimated reliably yet.").font(.caption).foregroundStyle(.secondary)}
                    }
                }
            }
        HStack(spacing:12) {
            if model.busy {ProgressView().controlSize(.small)} else {Image(systemName:model.cancelled ? "stop.circle" : "circle.fill").font(.system(size:9)).foregroundStyle(model.errorMessage != nil ? .orange : studioAccent)}
            Text(model.stateText).font(.system(size:12)).lineLimit(2)
            Spacer()
            if model.busy {Button("Stop Processing",role:.destructive){model.cancel()}}
            if model.lastJobFolder != nil {Button("Show Results"){model.revealOutput()}}
            Button{model.showLog.toggle()} label:{Label("Log",systemImage:"text.alignleft")}.buttonStyle(.plain).font(.caption)
        }
        }.padding(.horizontal,22).padding(.vertical,13).background(studioPaper)
    }
}
struct Checkerboard: View {
    var body:some View {
        Canvas {context,size in
            context.fill(Path(CGRect(origin:.zero,size:size)),with:.color(Color(red:0.91,green:0.91,blue:0.89)))
            let step:CGFloat=18
            for y in 0...Int(size.height/step) {for x in 0...Int(size.width/step) where (x+y)%2==0 {context.fill(Path(CGRect(x:CGFloat(x)*step,y:CGFloat(y)*step,width:step,height:step)),with:.color(.white.opacity(0.65)))}}
        }
    }
}

@MainActor final class StudioAppDelegate: NSObject, NSApplicationDelegate {
    var onQuit: (() -> Void)?
    func applicationWillTerminate(_ notification: Notification) {onQuit?()}
}

struct StudioThumbnail: View {
    let url: URL
    let maxPixel: Int
    @State private var loaded: NSImage?
    @State private var failed = false
    var body: some View {
        ZStack {
            if let loaded {Image(nsImage:loaded).resizable().scaledToFit()}
            else if failed {Image(systemName:"photo.badge.exclamationmark").foregroundStyle(.secondary)}
            else {ProgressView().controlSize(.small)}
        }.task(id:url.path+String(maxPixel)+(fileFingerprint(url) ?? "")) {
            loaded=nil;failed=false
            let result: NSImage? = await withCheckedContinuation { continuation in
                ThumbnailStore.worker.async {
                    let image=autoreleasepool {ThumbnailStore.shared.image(url,maxPixel:maxPixel)}
                    continuation.resume(returning:image)
                }
            }
            guard !Task.isCancelled else{return}
            loaded=result;failed=result==nil
        }
    }
}
