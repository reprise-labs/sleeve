import SwiftUI
import AppKit
import ImageIO

struct StudioCircleView:View {
    @ObservedObject var model:StudioModel
    let target:MediaItem
    @State private var source:URL
    @State private var sourceSignature:String?
    @State private var image:NSImage?
    @State private var loading=true
    @State private var width=0.0
    @State private var height=0.0
    @State private var x=0.5
    @State private var y=0.5
    @State private var diameter=0.98
    @State private var showCut=false
    @State private var part:String
    @State private var dragStart:CGPoint?
    init(model:StudioModel,target:MediaItem){self.model=model;self.target=target;_source=State(initialValue:target.url);_part=State(initialValue:target.part.hasPrefix("side") || target.part.hasPrefix("cd") ? target.part : "cd")}
    var radius:Double{diameter*min(width,height)/2}
    var valid:Bool{width>0 && height>0 && diameter*min(width,height)>=16 && x*width-radius >= -0.001 && y*height-radius >= -0.001 && x*width+radius<=width+0.001 && y*height+radius<=height+0.001}
    var body:some View {
        VStack(alignment:.leading,spacing:14) {
            HStack{Text("Ronde uitsnede bijstellen").font(.title2);Spacer();Button("Annuleren"){model.panel=nil}.keyboardShortcut(.cancelAction)}
            Text("Sleep de cirkel naar het middelpunt en pas de diameter aan. Gebruik de oorspronkelijke scan om een eerder weggeknipte rand terug te halen. Een nieuwe versie bewaart de vorige poging.").font(.caption).foregroundStyle(.secondary)
            HStack(alignment:.top,spacing:20) {
                GeometryReader {geo in
                    if let image {
                        let scale=min(geo.size.width/max(1,width),geo.size.height/max(1,height))
                        let w=width*scale;let h=height*scale;let d=diameter*min(width,height)*scale
                        ZStack {
                            Rectangle().fill(Color.gray.opacity(0.18))
                            Image(nsImage:image).resizable().frame(width:w,height:h)
                                .mask {if showCut{Circle().frame(width:d,height:d).position(x:x*w,y:y*h)}else{Rectangle()}}
                            if !showCut {
                                Circle().stroke(valid ? Color.green : .orange,lineWidth:2).frame(width:d,height:d).position(x:x*w,y:y*h)
                                Path{p in p.move(to:CGPoint(x:x*w-10,y:y*h));p.addLine(to:CGPoint(x:x*w+10,y:y*h));p.move(to:CGPoint(x:x*w,y:y*h-10));p.addLine(to:CGPoint(x:x*w,y:y*h+10))}.stroke(Color.green,lineWidth:1)
                            }
                        }.frame(width:w,height:h).contentShape(Rectangle()).clipped()
                            .gesture(DragGesture().onChanged{v in if dragStart==nil{dragStart=CGPoint(x:x,y:y)};if let start=dragStart{x=min(1,max(0,start.x+v.translation.width/max(1,w)));y=min(1,max(0,start.y+v.translation.height/max(1,h)))}}.onEnded{_ in dragStart=nil})
                            .frame(maxWidth:.infinity,maxHeight:.infinity)
                    } else {Group{if loading{ProgressView()}else{Text("Dit bronbeeld kan niet worden geladen. Kies een andere oorspronkelijke scan.")}}.frame(maxWidth:.infinity,maxHeight:.infinity)}
                }.frame(minWidth:480,minHeight:470)
                VStack(alignment:.leading,spacing:16) {
                    Text(source.lastPathComponent).font(.caption).lineLimit(3)
                    Button("Kies oorspronkelijke scan…"){chooseSource()}
                    Picker("Onderdeel",selection:$part){ForEach(partChoices.filter{$0.hasPrefix("side") || $0.hasPrefix("cd")},id:\.self){Text(partLabel($0)).tag($0)}}
                    Stepper(value:$x,in:0...1,step:1/max(1,width)){Text("Horizontaal · \(Int((x*width).rounded())) px").font(.caption)}
                    Slider(value:$x,in:0...1).accessibilityLabel("Middelpunt horizontaal")
                    Stepper(value:$y,in:0...1,step:1/max(1,height)){Text("Verticaal · \(Int((y*height).rounded())) px").font(.caption)}
                    Slider(value:$y,in:0...1).accessibilityLabel("Middelpunt verticaal")
                    Stepper(value:$diameter,in:0.01...1,step:1/max(1,min(width,height))){Text("Diameter · \(Int((diameter*min(width,height)).rounded())) px").font(.caption)}
                    Slider(value:$diameter,in:0.01...1).accessibilityLabel("Diameter uitsnede")
                    Toggle("Toon uitgeknipt voorbeeld",isOn:$showCut)
                    Button("Herstel cirkel"){x=0.5;y=0.5;diameter=0.98}
                    Text(valid ? "Cirkel past binnen het bronbeeld." : "De cirkel valt buiten het bronbeeld of is te klein.").font(.caption).foregroundStyle(valid ? Color.secondary : .orange)
                    Text("Alleen de buitenrand verandert. Het middengat en ontbrekende stukken blijven zoals in de bron. De afbeelding wordt niet uitgerekt.").font(.caption).foregroundStyle(.secondary)
                }.frame(width:260)
            }
            HStack{Text("\(Int(width)) × \(Int(height)) pixels").font(.caption);Spacer();Button("Bewaar nieuwe uitsnede"){if let signature=sourceSignature{model.saveCircle(target:target,source:source,signature:signature,x:x,y:y,diameter:diameter,part:part)}}.buttonStyle(.borderedProminent).disabled(!valid || image==nil || sourceSignature==nil)}
        }.padding(24).frame(minWidth:860,minHeight:650).tint(studioAccent)
        .task(id:source){await loadImage()}
    }
    func chooseSource(){let p=NSOpenPanel();p.title="Kies de oorspronkelijke scan";p.allowedContentTypes=[.image];if p.runModal() == .OK,let url=p.url{image=nil;sourceSignature=nil;width=0;height=0;loading=true;source=url;x=0.5;y=0.5;diameter=0.98}}
    func loadImage() async {
        let url=source;let signature=fileFingerprint(url)
        let result=await Task.detached {()->(NSImage?,Double,Double) in
            guard let file=CGImageSourceCreateWithURL(url as CFURL,nil),let props=CGImageSourceCopyPropertiesAtIndex(file,0,nil) as? [CFString:Any] else{return(nil,0,0)}
            var w=(props[kCGImagePropertyPixelWidth] as? NSNumber)?.doubleValue ?? 0;var h=(props[kCGImagePropertyPixelHeight] as? NSNumber)?.doubleValue ?? 0
            let orientation=(props[kCGImagePropertyOrientation] as? NSNumber)?.intValue ?? 1;if [5,6,7,8].contains(orientation){swap(&w,&h)}
            return(ThumbnailStore.shared.image(url,maxPixel:1800),w,h)
        }.value
        guard !Task.isCancelled,source==url else{return}
        image=result.0;width=result.1;height=result.2;sourceSignature=signature;loading=false
    }
}

struct StudioRetryView:View {
    @ObservedObject var model:StudioModel
    let target:MediaItem
    let settings:WorkspaceSnapshot
    @State private var candidates:[MediaItem]
    @State private var chosen:Set<URL>
    init(model:StudioModel,target:MediaItem){self.model=model;self.target=target;let original=model.scanSettings(for:target);settings=original;_candidates=State(initialValue:original.inputs.filter{!$0.reference});_chosen=State(initialValue:Set(original.inputs.filter{!$0.reference && $0.part==target.part}.map{$0.url}))}
    var valid:Bool{!chosen.isEmpty && Set(chosen.map{$0.deletingLastPathComponent()}).count==1 && chosen.allSatisfy{FileManager.default.fileExists(atPath:$0.path)}}
    var body:some View {
        VStack(alignment:.leading,spacing:16) {
            HStack{Text("\(partLabel(target.part)) opnieuw verwerken").font(.title2);Spacer();Button("Annuleren"){model.panel=nil}.keyboardShortcut(.cancelAction)}
            Text("Vink alleen de oorspronkelijke scans van dit onderdeel aan. Deze selectie wordt als één onderdeel samengevoegd. Andere resultaten blijven behouden; de vorige poging blijft beschikbaar in de vergelijking.").font(.callout)
            if chosen.isEmpty{Text("Kies hieronder de bronbeelden. Er wordt niet gegokt welke scans bij dit onderdeel horen.").font(.caption).foregroundStyle(.orange)}
            if Set(chosen.map{$0.deletingLastPathComponent()}).count>1{Text("Kies de bronbeelden van dit onderdeel uit één map.").font(.caption).foregroundStyle(.orange)}
            List(candidates){item in
                HStack {
                    Toggle(isOn:Binding(get:{chosen.contains(item.url)},set:{if $0{chosen.insert(item.url)}else{chosen.remove(item.url)}})){HStack{StudioThumbnail(url:item.url,maxPixel:130).frame(width:65,height:65);Text(item.title);Spacer();if !FileManager.default.fileExists(atPath:item.url.path){Text("Bron ontbreekt").foregroundStyle(.orange)}}}
                }.padding(.vertical,4)
            }
            Button("Andere oorspronkelijke scans kiezen…"){let p=NSOpenPanel();p.allowedContentTypes=[.image];p.allowsMultipleSelection=true;if p.runModal() == .OK {chosen=[];for url in p.urls {if !candidates.contains(where:{$0.url==url}){candidates.append(MediaItem(url:url,part:target.part))};chosen.insert(url)}}}
            Text(settings.discogs.isEmpty ? "Zonder Discogs. Een eventuele vinylkleur pas je daarna apart toe." : "Met de Discogs-instellingen van de oorspronkelijke verwerking. Een eventuele vinylkleur pas je daarna apart toe.").font(.caption).foregroundStyle(.secondary)
            HStack{Text(chosen.count==1 ? "1 bronbeeld · één nieuw resultaat" : "\(chosen.count) bronbeelden · één nieuw resultaat").font(.caption);Spacer();Button("Verwerk alleen dit onderdeel"){model.retryPart(target:target,sources:candidates.filter{chosen.contains($0.url)},settings:settings)}.buttonStyle(.borderedProminent).disabled(!valid)}
        }.padding(24).frame(minWidth:800,minHeight:590).tint(studioAccent)
    }
}
