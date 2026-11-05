import SwiftUI
import AppKit

struct StudioQueueView: View {
    @ObservedObject var model:StudioModel
    var body:some View {
        VStack(alignment:.leading,spacing:16) {
            HStack {
                VStack(alignment:.leading,spacing:5){Text("Wachtrij").font(.system(size:26,weight:.semibold,design:.serif));Text("Uitgaven worden één voor één verwerkt met de instellingen waarmee je ze klaarzet.").font(.caption).foregroundStyle(.secondary)}
                Spacer();Button("Sluiten"){model.showQueue=false}.keyboardShortcut(.cancelAction)
            }
            if model.queue.isEmpty {
                VStack(spacing:12){Image(systemName:"list.bullet.rectangle").font(.system(size:36));Text("Nog geen taken klaarstaan");Text("Kies beelden en instellingen op de werktafel en klik op ‘Zet deze taak in de wachtrij’.").font(.caption).foregroundStyle(.secondary)}.frame(maxWidth:.infinity,maxHeight:.infinity)
            } else {
                List {
                    ForEach(model.queue) {item in
                        VStack(alignment:.leading,spacing:7) {
                            HStack {
                                Image(systemName:item.state == .running ? "hourglass" : item.state == .done ? "checkmark.circle" : item.state == .waiting ? "clock" : "exclamationmark.circle").foregroundStyle(item.state == .failed ? .orange : studioAccent)
                                Text(item.project.title).font(.headline);Spacer()
                                Text(item.state.label).font(.caption).foregroundStyle(.secondary)
                            }
                            Text(item.project.workspace.mode.rawValue+" · \(item.project.workspace.inputs.filter{!$0.reference}.count) bronbeelden").font(.caption)
                            if item.state == .running {Text(model.stateText).font(.caption).foregroundStyle(studioAccent)}
                            if item.state == .done {Text(item.project.workspace.reviewComplete ? "Door jou gecontroleerd" : "Eindcontrole staat nog open").font(.caption).foregroundStyle(item.project.workspace.reviewComplete ? studioAccent : .secondary)}
                            if !item.detail.isEmpty && item.state != .done {Text(item.detail).font(.caption).foregroundStyle(.secondary).lineLimit(4)}
                            HStack {
                                Button(item.state == .done ? "Bekijk eindcontrole" : "Bekijk instellingen"){model.viewQueuedItem(item.id)}
                                if [.failed,.cancelled,.interrupted].contains(item.state) {Button("Opnieuw klaarzetten"){model.retryQueuedItem(item.id)}}
                                Spacer()
                                Button{model.moveQueuedItem(item.id,by:-1)}label:{Image(systemName:"arrow.up")}.help("Eerder in de wachtrij")
                                Button{model.moveQueuedItem(item.id,by:1)}label:{Image(systemName:"arrow.down")}.help("Later in de wachtrij")
                                Button("Uit lijst"){model.removeQueuedItem(item.id)}
                            }.controlSize(.small).buttonStyle(.borderless).disabled(model.busy)
                        }.padding(.vertical,9).accessibilityElement(children:.contain)
                    }
                }.listStyle(.inset)
            }
            Text("Bij een fout of onderbreking pauzeert de wachtrij. Sluiten van de app stopt de actieve taak; resterende taken blijven bewaard. ‘Uit lijst’ verwijdert geen afbeeldingen.").font(.caption).foregroundStyle(.secondary)
            HStack {
                Button("Nog een uitgave klaarzetten"){model.showQueue=false;model.newEdition()}.disabled(model.busy)
                Spacer()
                if model.busy {
                    Button(model.queueRunning ? "Pauze na deze taak" : "Wachtrij gepauzeerd"){model.pauseQueue()}.disabled(!model.queueRunning)
                    Button("Stop actieve taak",role:.destructive){model.cancel()}
                } else {
                    Button("Start wachtrij (\(model.pendingCount))"){model.startQueue()}.buttonStyle(.borderedProminent).disabled(model.pendingCount==0 || !model.libraryWritable)
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
                VStack(alignment:.leading,spacing:5){Text("Eindcontrole").font(.system(size:26,weight:.semibold,design:.serif));Text("\(model.reviewCount) van \(model.outputs.count) beelden door jou akkoord · \(model.titleForEdition)").font(.caption).foregroundStyle(.secondary)}
                Spacer();Button("Sluiten"){model.showReview=false}.keyboardShortcut(.cancelAction)
            }
            Text("Leesbaarheid en ronde uitsneden worden gemeten. Volledigheid van het beeld, de juiste uitgave en de gewenste kleur beoordeel je zelf. Verwerkt betekent nog niet goedgekeurd.").font(.caption).foregroundStyle(.secondary)
            ScrollView {
                LazyVStack(spacing:16) {ForEach(model.outputs){item in StudioReviewCard(model:model,item:item)}}
            }
            HStack {
                Button("Bestandscontroles opnieuw"){model.auditCurrentResults()}.disabled(model.busy || model.outputs.isEmpty)
                Button("Bewaar controleverslag"){model.exportReview()}.disabled(model.busy || model.outputs.isEmpty)
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
                Button("Open volledig beeld"){NSWorkspace.shared.open(item.url)}.font(.caption)
            }
            VStack(alignment:.leading,spacing:8) {
                HStack{Text(partLabel(item.part)).font(.headline);Spacer();if record.completed && !item.partial {Label("Door jou akkoord",systemImage:"checkmark.circle.fill").font(.caption).foregroundStyle(studioAccent)}}
                Text(item.title).font(.caption).textSelection(.enabled)
                if let audit=record.audit,!record.stale {
                    Label(audit.readable ? "Bestand leesbaar · \(audit.width) × \(audit.height) pixels" : "Bestand niet goed leesbaar",systemImage:audit.readable ? "checkmark.circle" : "exclamationmark.circle").font(.caption)
                    if let round=audit.round {Label(round ? "Ronde uitsnede gemeten" : "Ronde rand vraagt aandacht",systemImage:round ? "checkmark.circle" : "exclamationmark.circle").font(.caption).foregroundStyle(round ? studioAccent : .orange)}
                    Text(audit.namesApplied ? "Naam via Discogs toegepast · juiste uitgave nog beoordelen" : "Bestandsnaam zelf controleren").font(.caption).foregroundStyle(.secondary)
                    Text(audit.colourApplied ? "Kleurvoorstel toegepast · kleur nog beoordelen" : audit.colourKnown == true ? "Scankleur behouden · kleur is niet aangepast" : "Geen kleurstap bekend · kleur zelf beoordelen").font(.caption).foregroundStyle(.secondary)
                    if !audit.message.isEmpty {Text(audit.message).font(.caption).foregroundStyle(.orange)}
                } else {Text(record.stale ? "Bestand gewijzigd of verplaatst. Voer de bestandscontroles opnieuw uit; eerdere goedkeuringen vervallen." : "Nog geen bestandscontrole beschikbaar.").font(.caption).foregroundStyle(.orange)}
                if item.partial {Text("Deze uitvoer komt uit een afgebroken verwerking.").font(.caption).foregroundStyle(.orange)}
                Group {
                    Toggle("Beeld is volledig en netjes",isOn:Binding(get:{record.visualApproved},set:{v in model.updateReview(item){$0.visualApproved=v}}))
                    Toggle("Bestandsnaam klopt bij deze uitgave",isOn:Binding(get:{record.nameApproved},set:{v in model.updateReview(item){$0.nameApproved=v}}))
                    Toggle(record.audit?.colourApplied == true ? "Referentiefoto en kleur akkoord" : record.audit?.colourKnown == true ? "Scankleur bewust behouden" : "Kleur van dit bestand akkoord",isOn:Binding(get:{record.colourApproved},set:{v in model.updateReview(item){$0.colourApproved=v}}))
                }.font(.system(size:12)).disabled(model.busy || record.audit?.readable != true || record.stale || item.partial)
                TextField("Opmerking (optioneel)",text:Binding(get:{record.notes},set:{v in model.updateReview(item){$0.notes=v}}),axis:.vertical).textFieldStyle(.roundedBorder).font(.caption).disabled(model.busy)
            }
        }.padding(16).background(Color(nsColor:.controlBackgroundColor),in:RoundedRectangle(cornerRadius:12))
    }
}
