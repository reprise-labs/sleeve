import SwiftUI
import AppKit

@main struct SleeveApp: App {
    @StateObject private var model = StudioModel()
    @NSApplicationDelegateAdaptor(StudioAppDelegate.self) private var delegate
    var body: some Scene {
        WindowGroup("Sleeve") {
            StudioView(model:model).frame(minWidth:1100,minHeight:720)
                .onAppear { delegate.onQuit = {model.prepareForQuit()}; if CommandLine.arguments.contains("--demo") && model.inputs.isEmpty {model.loadDemo()} }
        }.defaultSize(width:1380,height:900)
        .commands {
            CommandGroup(replacing:.newItem) {
                Button("Nieuwe uitgave") {model.newEdition()}.keyboardShortcut("n").disabled(model.busy)
                Button("Open project…") {model.pickProject()}.keyboardShortcut("o",modifiers:[.command,.shift]).disabled(model.busy)
                Button("Bewaar project") {if model.projectURL==nil{model.saveProjectAs()}else{model.saveExistingProject()}}.keyboardShortcut("s").disabled(model.busy)
                Button("Afbeeldingen toevoegen…") {model.pickImages()}.keyboardShortcut("o").disabled(model.busy)
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
                Text("Jouw scans. Zorgvuldig afgewerkt.").font(.system(size:13)).foregroundStyle(.secondary)
                Menu {
                    Button("Open project…"){model.pickProject()}
                    Button(model.projectURL==nil ? "Bewaar project…" : "Bewaar als…"){model.saveProjectAs()}
                    ForEach(model.recentProjects,id:\.self){url in Button(url.deletingPathExtension().lastPathComponent){model.openProject(url)}}
                } label:{Label("Project",systemImage:"folder")}.disabled(model.busy)
                Button{model.showQueue=true} label:{Label("Wachtrij (\(model.pendingCount))",systemImage:"list.bullet.rectangle")}
                Button {model.newEdition()} label:{Label("Nieuwe uitgave",systemImage:"plus")}.disabled(model.busy)
            }.padding(.horizontal,24).padding(.vertical,17).background(studioPaper)
            Divider()
            HStack(spacing:0) {
                sidebar.frame(width:190)
                Divider()
                VStack(spacing:0) {
                    HStack {
                        VStack(alignment:.leading,spacing:5) {
                            Text(model.mode.rawValue).font(.system(size:23,weight:.semibold,design:.serif))
                            Text(model.mode.caption).font(.system(size:12)).foregroundStyle(.secondary)
                        }
                        Spacer()
                        if !model.outputs.isEmpty {
                            Picker("Beelden",selection:Binding(get:{model.showResults},set:{model.selectList($0)})) {
                                Text(model.mode == .colour ? "Originelen" : "Bronnen").tag(false);Text(model.mode == .colour ? "Nieuwe kleuren" : "Resultaten").tag(true)
                            }.pickerStyle(.segmented).labelsHidden().frame(width:205)
                        }
                    }.padding(22)
                    if let item=model.selected {
                        HStack {
                            Button("Ronde uitsnede bijstellen…"){model.openCrop(item)}
                            if model.showResults {Button("Dit onderdeel opnieuw verwerken…"){model.openRetry(item)}}
                            if item.previousVersion != nil {Text("Voor = vorige poging · Na = nieuwe poging").font(.caption).foregroundStyle(.secondary)}
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
                ScrollView {Text(model.logText.isEmpty ? "Het logboek verschijnt zodra de verwerking begint." : model.logText).font(.system(size:11,design:.monospaced)).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading).padding(12)}.frame(height:140).background(Color(nsColor:.textBackgroundColor))
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
            }
        }
        .onDrop(of:["public.file-url"],isTargeted:nil) {providers in
            guard !model.busy else{return false}
            for provider in providers { _ = provider.loadObject(ofClass:URL.self){url,_ in if let url {Task{@MainActor in model.addURLs([url])}}} }
            return true
        }
        .alert("Even controleren",isPresented:Binding(get:{model.errorMessage != nil},set:{if !$0{model.errorMessage=nil}})) {
            Button("Begrepen",role:.cancel){model.errorMessage=nil}
        } message: {Text(model.errorMessage ?? "")}
    }
    var sidebar: some View {
        VStack(alignment:.leading,spacing:7) {
            Text("WERKTAFEL").font(.system(size:10,weight:.bold)).tracking(1.6).foregroundStyle(.secondary).padding(.horizontal,10).padding(.bottom,9)
            ForEach(WorkMode.allCases) {mode in
                Button {model.changeMode(mode)} label: {
                    Label(mode.rawValue,systemImage:mode.icon).font(.system(size:13,weight:model.mode==mode ? .semibold : .regular)).frame(maxWidth:.infinity,alignment:.leading).padding(.horizontal,11).padding(.vertical,12)
                        .background(model.mode==mode ? studioAccent.opacity(0.11) : .clear,in:RoundedRectangle(cornerRadius:9))
                }.buttonStyle(.plain).disabled(model.busy)
            }
            Button{model.showReview=true} label:{Label("Eindcontrole",systemImage:"checklist").frame(maxWidth:.infinity,alignment:.leading).padding(11)}.buttonStyle(.plain).disabled(model.outputs.isEmpty)
            if !model.runs.isEmpty {
                Menu("Eerdere bewerkingen") {ForEach(model.runs.reversed()){run in Button(run.label+" · "+run.date.formatted(date:.abbreviated,time:.shortened)){model.showRun(run.id)}}}.disabled(model.busy)
            }
            Divider().padding(.vertical,13)
            Button {model.pickImages()} label:{Label("Voeg beelden toe",systemImage:"photo.on.rectangle.angled").frame(maxWidth:.infinity,alignment:.leading)}.buttonStyle(.plain).padding(10).disabled(model.busy)
            Text("Of sleep een map of afbeeldingen op de werktafel.").font(.system(size:11)).foregroundStyle(.secondary).padding(.horizontal,10)
            Spacer()
            Button("Open voorbeeld") {model.loadDemo()}.buttonStyle(.plain).foregroundStyle(studioAccent).padding(10).disabled(model.busy)
            VStack(alignment:.leading,spacing:6) {
                Label("Lokaal op je Mac",systemImage:"desktopcomputer").font(.system(size:11,weight:.medium))
                Text("Originelen blijven behouden. Elke verwerking krijgt een nieuwe map.").font(.system(size:11)).foregroundStyle(.secondary)
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
                    if item.reference {Text("Referentie").font(.caption).foregroundStyle(.secondary)}
                    if item.partial {Text("Niet afgerond").font(.caption).foregroundStyle(.orange)}
                    Button {model.openSelected()} label:{Image(systemName:"arrow.up.right.square")}.buttonStyle(.plain).help("Open het volledige beeld")
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
                                    VStack {HStack{Text("Origineel");Spacer();Text("Nieuwe kleur")}.font(.system(size:11,weight:.semibold)).padding(8).background(.regularMaterial);Spacer()}.padding(12)
                                }
                            }
                        }
                    }
                }
                if model.mode == .colour && model.beforeURL != nil {
                    HStack {Text("Origineel");Slider(value:Binding(get:{1-model.compare},set:{model.compare=1-$0}),in:0...1);Text("Nieuwe kleur")}.font(.caption).padding(.horizontal,30)
                }
                if model.mode == .names,let row=model.selectedProposal {
                    VStack(alignment:.leading,spacing:5) {Text("VOORGESTELDE NAAM").font(.system(size:9,weight:.bold)).tracking(1);Text(row.newName).font(.system(size:12,weight:.medium)).textSelection(.enabled)}.padding(12).frame(maxWidth:.infinity,alignment:.leading).background(studioAccent.opacity(0.08),in:RoundedRectangle(cornerRadius:9))
                }
            }.padding(.horizontal,22).padding(.bottom,18)
        } else {
            VStack(spacing:16) {
                Image(systemName:"opticaldisc").font(.system(size:66,weight:.ultraLight)).foregroundStyle(studioAccent.opacity(0.65))
                Text("Geef je scans de ruimte").font(.system(size:29,weight:.medium,design:.serif))
                Text("Kies de beelden van één uitgave.\nWe bewaren het resultaat in een nieuwe map.").font(.system(size:14)).foregroundStyle(.secondary).multilineTextAlignment(.center).lineSpacing(5)
                Button("Kies afbeeldingen…") {model.pickImages()}.buttonStyle(.borderedProminent).controlSize(.large).disabled(model.busy)
                Text("Cd en vinyl apart verwerken").font(.caption).foregroundStyle(.secondary)
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
            TextField("Naam van project / uitgave",text:$model.editionTitle).textFieldStyle(.roundedBorder)
            HStack{Text(model.projectURL?.lastPathComponent ?? "Project nog niet bewaard").lineLimit(1).truncationMode(.middle);Spacer();if model.projectURL != nil {Image(systemName:"externaldrive.badge.checkmark")}}.font(.caption).foregroundStyle(.secondary)
            if model.projectURL != nil {Text(model.projectSaveText).font(.caption).foregroundStyle(.secondary)}
            sectionTitle("01", "Uitgave & referentie")
            TextField("Discogs-link (optioneel bij scans)",text:$model.discogs).textFieldStyle(.roundedBorder).disabled(model.busy)
                .onChange(of:model.discogs){ model.cancelReleaseAdvice();model.proposals=[];model.references=[];if model.referenceFromDiscogs {model.referenceURL=nil}}
            if model.mode == .scans {
                Text("Gebruik van Discogs").font(.system(size:12,weight:.semibold))
                Toggle("Bestandsnamen overnemen",isOn:$model.useNames)
                Toggle("Hoes en plaat juist draaien",isOn:$model.useStand)
                Text("Bekijk eerst je resultaten. Kleuren van hoezen en platen kun je daarna onder ‘Kleur aanpassen’ bijstellen.").font(.caption).foregroundStyle(.secondary)
            }
            if !model.inputs.isEmpty {
                VStack(alignment:.leading,spacing:7) {
                    HStack {
                        if model.discovering {ProgressView().controlSize(.small)}
                        Text(model.discovering ? "Uitgave herkennen…" : model.adviceCandidates.isEmpty ? "Hulp bij de juiste uitgave" : "\(model.adviceCandidates.count) mogelijke Discogs-uitgaven").font(.caption).foregroundStyle(.secondary)
                    }
                    Button("Bekijk releasevoorstellen…"){model.panel = .advice}
                }
            }
            if model.mode == .names {
                TextField("Extra variant (optioneel)",text:$model.variant).textFieldStyle(.roundedBorder).onChange(of:model.variant){ model.proposals=[]}
                Text("Kies per beeld hieronder het onderdeel. Haal daarna de namen op om ze te controleren.").font(.caption).foregroundStyle(.secondary)
                Button("Namenvoorstel ophalen") {model.previewNames()}.disabled(model.busy || model.discogs.isEmpty || model.inputCount==0)
                if !model.proposals.isEmpty {Label("\(model.proposals.count) namen ter controle",systemImage:"checkmark.circle").font(.caption).foregroundStyle(studioAccent)}
            }
            if let item=model.selectedInput,!model.showResults {
                Divider();sectionTitle(model.mode == .colour ? "03" : "02","Geselecteerd beeld")
                Text(item.title).font(.caption).lineLimit(2)
                if model.mode == .names {
                    Picker("Onderdeel",selection:Binding(get:{model.selectedInput?.part ?? "front"},set:{model.updateSelectedPart($0)})) {ForEach(partChoices,id:\.self){Text(partLabel($0)).tag($0)}}
                }
                if model.mode == .scans {
                    Toggle("Alleen als referentie gebruiken",isOn:Binding(get:{model.selectedInput?.reference ?? false},set:{model.updateReference($0)}))
                    Text("Etiketclose-ups en andere referenties worden niet als losse platen verwerkt. Bekende scanindelingen worden meegenomen.").font(.caption).foregroundStyle(.secondary)
                }
                Button("Verwijder uit selectie",role:.destructive) {model.removeSelected()}.buttonStyle(.plain).font(.caption).disabled(model.busy)
            }

        }.font(.system(size:12)).disabled(model.busy)
    }
    var saveControls: some View {
        VStack(alignment:.leading,spacing:12) {
            sectionTitle("↗",model.mode == .colour ? "Nieuwe kleur bewaren" : "Bewaren")
            Button {model.chooseOutput()} label:{HStack{Image(systemName:"folder");Text(model.outputFolder?.lastPathComponent ?? "Kies een resultatenmap…").lineLimit(1);Spacer();Image(systemName:"chevron.down").font(.caption2)}}.disabled(model.busy)
            Text(model.mode == .colour ? "Je krijgt nieuwe kleurkopieën in een aparte map. De originele beelden blijven behouden." : "Een nieuwe submap per verwerking. Originelen blijven behouden.").font(.caption).foregroundStyle(.secondary)
            Button {model.start()} label:{Text(model.mode == .scans ? "Verwerk scans" : model.mode == .colour ? model.colourActionTitle : "Bewaar met nieuwe namen").frame(maxWidth:.infinity).padding(.vertical,5)}.buttonStyle(.borderedProminent).controlSize(.large).disabled(!model.canStart)
            Button("Zet deze taak in de wachtrij"){model.enqueueCurrent()}.disabled(!model.canStart)
            if model.projectURL==nil {Button("Bewaar als project…"){model.saveProjectAs()}.font(.caption)}
            if model.demo {Text("Dit zijn verkleinde voorbeeldbeelden om de app uit te proberen.").font(.caption).foregroundStyle(.secondary)}
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
                            if let index=model.currentPart,let total=model.totalParts {Text(model.progressPhase=="Eindcontrole" ? "Bestand \(index) van \(total) controleren" : "Onderdeel \(index) van \(total)").fontWeight(.semibold)}
                            else {Text(model.completedParts>0 ? "Verwerking afronden" : "Verwerking voorbereiden").fontWeight(.semibold)}
                            if model.mode == .scans,let total=model.totalParts {Text("· \(model.completedParts) van \(total) onderdelen verwerkt").foregroundStyle(.secondary)}
                            Spacer()
                            if let start=model.startedAt {Text("Totale tijd "+durationText(context.date.timeIntervalSince(start))).monospacedDigit()}
                        }.font(.system(size:12))
                        HStack {
                            Text(model.progressPhase.isEmpty ? "Voorbereiden" : model.progressPhase)
                            Spacer()
                            if let start=model.phaseStartedAt {Text("Deze stap "+durationText(context.date.timeIntervalSince(start))).monospacedDigit().foregroundStyle(.secondary)}
                        }.font(.system(size:12))
                        if let progress=model.measuredProgress {
                            ProgressView(value:progress,total:1).progressViewStyle(.linear).tint(studioAccent).scaleEffect(x:1,y:2).frame(height:10).accessibilityLabel("Gemeten voortgang van de huidige stap")
                            HStack {Text("\(Int((progress*100).rounded()))% van deze stap");if let done=model.progressUnitsDone,let total=model.progressUnitsTotal {Text("· \(done) / \(total)")}}.font(.caption).monospacedDigit().foregroundStyle(.secondary)
                        } else {
                            ProgressView().progressViewStyle(.linear).tint(studioAccent).scaleEffect(x:1,y:2).frame(height:10).accessibilityLabel("Stap bezig, percentage onbekend")
                            Text("Bezig · voor deze stap is geen betrouwbaar percentage beschikbaar.").font(.caption).foregroundStyle(.secondary)
                        }
                        if !model.progressDetail.isEmpty {Text(model.progressDetail).font(.caption).foregroundStyle(.secondary)}
                        if let last=model.lastProgressAt,context.date.timeIntervalSince(last)>20 {Text("Laatste voortgangsmelding "+durationText(context.date.timeIntervalSince(last))+" geleden. Resterende tijd is nog niet betrouwbaar te bepalen.").font(.caption).foregroundStyle(.secondary)}
                    }
                }
            }
        HStack(spacing:12) {
            if model.busy {ProgressView().controlSize(.small)} else {Image(systemName:model.cancelled ? "stop.circle" : "circle.fill").font(.system(size:9)).foregroundStyle(model.errorMessage != nil ? .orange : studioAccent)}
            Text(model.stateText).font(.system(size:12)).lineLimit(2)
            Spacer()
            if model.busy {Button("Stop verwerking",role:.destructive){model.cancel()}}
            if model.lastJobFolder != nil {Button("Toon resultaten"){model.revealOutput()}}
            Button{model.showLog.toggle()} label:{Label("Logboek",systemImage:"text.alignleft")}.buttonStyle(.plain).font(.caption)
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
