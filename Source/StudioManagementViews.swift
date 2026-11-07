import SwiftUI
import AppKit

struct StudioQueueView: View {
    @ObservedObject var model:StudioModel
    var body:some View {
        VStack(alignment:.leading,spacing:16) {
            HStack {
                VStack(alignment:.leading,spacing:5){Text("Queue").font(.system(size:26,weight:.semibold,design:.serif));Text("Releases are processed one by one with the settings you queued them with.").font(.caption).foregroundStyle(.secondary)}
                Spacer();Button("Close"){model.showQueue=false}.keyboardShortcut(.cancelAction)
            }
            if model.queue.isEmpty {
                VStack(spacing:12){Image(systemName:"list.bullet.rectangle").font(.system(size:36));Text("No tasks queued yet");Text("Choose images and settings on the workspace and click ‘Add This Task to the Queue’.").font(.caption).foregroundStyle(.secondary)}.frame(maxWidth:.infinity,maxHeight:.infinity)
            } else {
                List {
                    ForEach(model.queue) {item in
                        VStack(alignment:.leading,spacing:7) {
                            HStack {
                                Image(systemName:item.state == .running ? "hourglass" : item.state == .done ? "checkmark.circle" : item.state == .waiting ? "clock" : "exclamationmark.circle").foregroundStyle(item.state == .failed ? .orange : studioAccent)
                                Text(item.project.title).font(.headline);Spacer()
                                Text(item.state.label).font(.caption).foregroundStyle(.secondary)
                            }
                            Text(item.project.workspace.mode.title+" · \(item.project.workspace.inputs.filter{!$0.reference}.count) source images").font(.caption)
                            if item.state == .running {Text(model.stateText).font(.caption).foregroundStyle(studioAccent)}
                            if item.state == .done {Text(item.project.workspace.reviewComplete ? "Reviewed by you" : "Final check still open").font(.caption).foregroundStyle(item.project.workspace.reviewComplete ? studioAccent : .secondary)}
                            if !item.detail.isEmpty && item.state != .done {Text(item.detail).font(.caption).foregroundStyle(.secondary).lineLimit(4)}
                            HStack {
                                Button(item.state == .done ? "View Final Check" : "View Settings"){model.viewQueuedItem(item.id)}
                                if [.failed,.cancelled,.interrupted].contains(item.state) {Button("Queue Again"){model.retryQueuedItem(item.id)}}
                                Spacer()
                                Button{model.moveQueuedItem(item.id,by:-1)}label:{Image(systemName:"arrow.up")}.help("Earlier in Queue")
                                Button{model.moveQueuedItem(item.id,by:1)}label:{Image(systemName:"arrow.down")}.help("Later in Queue")
                                Button("Remove from List"){model.removeQueuedItem(item.id)}
                            }.controlSize(.small).buttonStyle(.borderless).disabled(model.busy)
                        }.padding(.vertical,9).accessibilityElement(children:.contain)
                    }
                }.listStyle(.inset)
            }
            Text("On an error or interruption the queue pauses. Quitting the app stops the active task; remaining tasks are kept. ‘Remove from List’ doesn't delete any images.").font(.caption).foregroundStyle(.secondary)
            HStack {
                Button("Queue Another Release"){model.showQueue=false;model.newEdition()}.disabled(model.busy)
                Spacer()
                if model.busy {
                    Button(model.queueRunning ? "Pause After This Task" : "Queue paused"){model.pauseQueue()}.disabled(!model.queueRunning)
                    Button("Stop Active Task",role:.destructive){model.cancel()}
                } else {
                    Button("Start Queue (\(model.pendingCount))"){model.startQueue()}.buttonStyle(.borderedProminent).disabled(model.pendingCount==0 || !model.libraryWritable)
                }
            }
        }.padding(24).frame(minWidth:760,idealWidth:840,minHeight:550,idealHeight:680).tint(studioAccent)
    }
}
struct StudioReviewView: View {
    @ObservedObject var model:StudioModel
    var body:some View {
        VStack(alignment:.leading,spacing:14) {
            HStack {
                VStack(alignment:.leading,spacing:5){Text("Final Check").font(.system(size:26,weight:.semibold,design:.serif));Text("\(model.reviewCount) of \(model.outputs.count) images approved by you · \(model.titleForEdition)").font(.caption).foregroundStyle(.secondary)}
                Spacer();Button("Close"){model.showReview=false}.keyboardShortcut(.cancelAction)
            }
            Text("Readability and round crops are measured. You judge whether the image is complete, the release is right and the color is as wanted. Processed doesn't mean approved yet.").font(.caption).foregroundStyle(.secondary)
            ScrollView {
                LazyVStack(spacing:16) {ForEach(model.outputs){item in StudioReviewCard(model:model,item:item)}}
            }
            HStack {
                Button("Recheck Files"){model.auditCurrentResults()}.disabled(model.busy || model.outputs.isEmpty)
                Button("Save Check Report"){model.exportReview()}.disabled(model.busy || model.outputs.isEmpty)
                Spacer()
                if model.busy {ProgressView().controlSize(.small);Text(model.stateText).font(.caption).lineLimit(2)}
            }
        }.padding(24).frame(minWidth:820,idealWidth:920,minHeight:580,idealHeight:740).tint(studioAccent)
    }
}
struct StudioReviewCard:View {
    @ObservedObject var model:StudioModel
    let item:MediaItem
    var record:ReviewRecord{model.review(for:item)}
    var body:some View {
        HStack(alignment:.top,spacing:18) {
            VStack(spacing:10) {
                StudioThumbnail(url:item.url,maxPixel:320).frame(width:140,height:140).background(studioPaper,in:RoundedRectangle(cornerRadius:10))
                Button("Open Full Image"){NSWorkspace.shared.open(item.url)}.font(.caption)
                if item.part.hasPrefix("side") || item.part.hasPrefix("cd") {Button("Adjust Crop…"){model.openCrop(item)}.font(.caption).disabled(model.busy || model.queueRunning)}
                Button("Reprocess Part…"){model.openRetry(item)}.font(.caption).disabled(model.busy || model.queueRunning)
            }
            VStack(alignment:.leading,spacing:8) {
                HStack{Text(partLabel(item.part)).font(.headline);Spacer();if record.completed && !item.partial {Label("Approved by you",systemImage:"checkmark.circle.fill").font(.caption).foregroundStyle(studioAccent)}}
                Text(item.title).font(.caption).textSelection(.enabled)
                if let audit=record.audit,!record.stale {
                    Label(audit.readable ? "File readable · \(audit.width) × \(audit.height) pixels" : "File not readable",systemImage:audit.readable ? "checkmark.circle" : "exclamationmark.circle").font(.caption)
                    if let round=audit.round {Label(round ? "Round crop measured" : "Round edge needs attention",systemImage:round ? "checkmark.circle" : "exclamationmark.circle").font(.caption).foregroundStyle(round ? studioAccent : .orange)}
                    Text(audit.namesApplied ? "Name applied via Discogs · still check the release" : "Check the file name yourself").font(.caption).foregroundStyle(.secondary)
                    Text(audit.colourApplied ? "Color suggestion applied · still check the color" : audit.colourKnown == true ? "Scan color kept · color not adjusted" : "No color step known · check the color yourself").font(.caption).foregroundStyle(.secondary)
                    if !audit.message.isEmpty {Text(audit.message).font(.caption).foregroundStyle(.orange)}
                } else {Text(record.stale ? "File changed or moved. Run the file checks again; earlier approvals are cleared." : "No file check available yet.").font(.caption).foregroundStyle(.orange)}
                if item.partial {Text("This output comes from an interrupted run.").font(.caption).foregroundStyle(.orange)}
                Group {
                    Toggle("Image is complete and clean",isOn:Binding(get:{record.visualApproved},set:{v in model.updateReview(item){$0.visualApproved=v}}))
                    Toggle("File name matches this release",isOn:Binding(get:{record.nameApproved},set:{v in model.updateReview(item){$0.nameApproved=v}}))
                    Toggle(record.audit?.colourApplied == true ? "Reference photo and color approved" : record.audit?.colourKnown == true ? "Scan color kept on purpose" : "Color of this file approved",isOn:Binding(get:{record.colourApproved},set:{v in model.updateReview(item){$0.colourApproved=v}}))
                }.font(.system(size:12)).disabled(model.busy || record.audit?.readable != true || record.stale || item.partial)
                TextField("Note (optional)",text:Binding(get:{record.notes},set:{v in model.updateReview(item){$0.notes=v}}),axis:.vertical).textFieldStyle(.roundedBorder).font(.caption).disabled(model.busy)
            }
        }.padding(16).background(Color(nsColor:.controlBackgroundColor),in:RoundedRectangle(cornerRadius:12))
    }
}
