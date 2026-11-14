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
            HStack{Text("Adjust Round Crop").font(.title2);Spacer();Button("Cancel"){model.panel=nil}.keyboardShortcut(.cancelAction)}
            Text("Drag the circle to the center and adjust the diameter. Use the original scan to bring back an edge that was cut off earlier. A new version keeps the previous attempt.").font(.caption).foregroundStyle(.secondary)
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
                    } else {Group{if loading{ProgressView()}else{Text("This source image can't be loaded. Choose another original scan.")}}.frame(maxWidth:.infinity,maxHeight:.infinity)}
                }.frame(minWidth:480,minHeight:470)
                VStack(alignment:.leading,spacing:16) {
                    Text(source.lastPathComponent).font(.caption).lineLimit(3)
                    Button("Choose Original Scan…"){chooseSource()}
                    Picker("Part",selection:$part){ForEach(partChoices.filter{$0.hasPrefix("side") || $0.hasPrefix("cd")},id:\.self){Text(partLabel($0)).tag($0)}}
                    Stepper(value:$x,in:0...1,step:1/max(1,width)){Text("Horizontal · \(Int((x*width).rounded())) px").font(.caption)}
                    Slider(value:$x,in:0...1).accessibilityLabel("Center horizontal")
                    Stepper(value:$y,in:0...1,step:1/max(1,height)){Text("Vertical · \(Int((y*height).rounded())) px").font(.caption)}
                    Slider(value:$y,in:0...1).accessibilityLabel("Center vertical")
                    Stepper(value:$diameter,in:0.01...1,step:1/max(1,min(width,height))){Text("Diameter · \(Int((diameter*min(width,height)).rounded())) px").font(.caption)}
                    Slider(value:$diameter,in:0.01...1).accessibilityLabel("Crop diameter")
                    Toggle("Show cut-out preview",isOn:$showCut)
                    Button("Reset Circle"){x=0.5;y=0.5;diameter=0.98}
                    Text(valid ? "The circle fits within the source image." : "The circle extends beyond the source image or is too small.").font(.caption).foregroundStyle(valid ? Color.secondary : .orange)
                    Text("Only the outer edge changes. The center hole and missing pieces stay as in the source. The image is not stretched.").font(.caption).foregroundStyle(.secondary)
                }.frame(width:260)
            }
            HStack{Text("\(Int(width)) × \(Int(height)) pixels").font(.caption);Spacer();Button("Save New Crop"){if let signature=sourceSignature{model.saveCircle(target:target,source:source,signature:signature,x:x,y:y,diameter:diameter,part:part)}}.buttonStyle(.borderedProminent).disabled(!valid || image==nil || sourceSignature==nil)}
        }.padding(24).frame(minWidth:860,minHeight:650).tint(studioAccent)
        .task(id:source){await loadImage()}
    }
    func chooseSource(){let p=NSOpenPanel();p.title="Choose the original scan";p.allowedContentTypes=[.image];if p.runModal() == .OK,let url=p.url{image=nil;sourceSignature=nil;width=0;height=0;loading=true;source=url;x=0.5;y=0.5;diameter=0.98}}
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
    @State private var seamLevel=false
    init(model:StudioModel,target:MediaItem){self.model=model;self.target=target;let original=model.scanSettings(for:target);settings=original;_candidates=State(initialValue:original.inputs.filter{!$0.reference});_chosen=State(initialValue:Set(original.inputs.filter{!$0.reference && $0.part==target.part}.map{$0.url}))}
    var valid:Bool{!chosen.isEmpty && Set(chosen.map{$0.deletingLastPathComponent()}).count==1 && chosen.allSatisfy{FileManager.default.fileExists(atPath:$0.path)}}
    var body:some View {
        VStack(alignment:.leading,spacing:16) {
            HStack{Text("\(partLabel(target.part)) reprocess").font(.title2);Spacer();Button("Cancel"){model.panel=nil}.keyboardShortcut(.cancelAction)}
            Text("Check only the original scans of this part. This selection is merged into one part. Other results are kept; the previous attempt stays available in the comparison.").font(.callout)
            if chosen.isEmpty{Text("Choose the source images below. Sleeve doesn't guess which scans belong to this part.").font(.caption).foregroundStyle(.orange)}
            if Set(chosen.map{$0.deletingLastPathComponent()}).count>1{Text("Choose the source images of this part from one folder.").font(.caption).foregroundStyle(.orange)}
            List(candidates){item in
                HStack {
                    Toggle(isOn:Binding(get:{chosen.contains(item.url)},set:{if $0{chosen.insert(item.url)}else{chosen.remove(item.url)}})){HStack{StudioThumbnail(url:item.url,maxPixel:130).frame(width:65,height:65);Text(item.title);Spacer();if !FileManager.default.fileExists(atPath:item.url.path){Text("Source missing").foregroundStyle(.orange)}}}
                }.padding(.vertical,4)
            }
            Button("Choose Other Original Scans…"){let p=NSOpenPanel();p.allowedContentTypes=[.image];p.allowsMultipleSelection=true;if p.runModal() == .OK {chosen=[];for url in p.urls {if !candidates.contains(where:{$0.url==url}){candidates.append(MediaItem(url:url,part:target.part))};chosen.insert(url)}}}
            Toggle(isOn:$seamLevel){VStack(alignment:.leading,spacing:2){Text("Level tone across the seams");Text("For a light or dark band where two partial scans meet. Edges are still found on the normal merge, so the size doesn't change. Takes about twice as long.").font(.caption).foregroundStyle(.secondary)}}.disabled(chosen.count<2)
            Text(settings.discogs.isEmpty ? "Without Discogs. Apply any vinyl color separately afterwards." : "With the Discogs settings of the original run. Apply any vinyl color separately afterwards.").font(.caption).foregroundStyle(.secondary)
            HStack{Text(chosen.count==1 ? "1 source image · one new result" : "\(chosen.count) source images · one new result").font(.caption);Spacer();Button("Process Only This Part"){model.retryPart(target:target,sources:candidates.filter{chosen.contains($0.url)},settings:settings,seamLevel:seamLevel)}.buttonStyle(.borderedProminent).disabled(!valid)}
        }.padding(24).frame(minWidth:800,minHeight:590).tint(studioAccent)
    }
}
