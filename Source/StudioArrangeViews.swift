import SwiftUI

/// Indelingsscherm: sleep de scans van één uitgave in vakken (Front, Back, Side A …).
/// Sleeve volgt die indeling precies en raadt niets meer (geen 'Suggest': de oude regels zijn weg)
/// alvast met Sleeve's eigen voorstel, dat je daarna corrigeert.
struct StudioArrangeView: View {
    @ObservedObject var model: StudioModel
    private let columns=[GridItem(.adaptive(minimum:250),spacing:14)]
    var body: some View {
        VStack(spacing:0) {
            HStack(alignment:.top) {
                VStack(alignment:.leading,spacing:4) {
                    Text("Arrange Scans").font(.system(size:20,weight:.semibold,design:.serif))
                    Text("Drag each scan into the slot it belongs to. Sleeve follows this exactly and doesn’t guess.").font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                    .help("Let Sleeve fill the slots for the scans that aren’t in a slot yet")
                Menu {
                    ForEach(slotParts,id:\.self){part in Button(partLabel(part)){model.addSlot(part:part)}}
                } label:{Label("Add Slot",systemImage:"plus.rectangle")}.fixedSize()
                Button("Clear"){model.clearArrangement()}.disabled(model.arrangedCount==0 && model.emptySlots.isEmpty)
                Button("Done"){model.panel=nil}.keyboardShortcut(.defaultAction)
            }.padding(18)
            if !model.suggestStatus.isEmpty {Text(model.suggestStatus).font(.caption).foregroundStyle(.secondary).frame(maxWidth:.infinity,alignment:.leading).padding(.horizontal,18).padding(.bottom,8)}
            Divider()
            HStack(spacing:0) {
                tray.frame(width:230)
                Divider()
                ScrollView {
                    LazyVGrid(columns:columns,alignment:.leading,spacing:14) {
                        ForEach(model.slots) {slot in SlotCard(model:model,slot:slot)}
                        emptyHint
                    }.padding(16)
                }
            }
            Divider()
            HStack {
                Text(model.arrangementSummary).font(.caption).foregroundStyle(.secondary)
                Spacer()
                Text("Scans without a slot are not used.").font(.caption).foregroundStyle(.secondary)
            }.padding(.horizontal,18).padding(.vertical,10)
        }.frame(minWidth:900,minHeight:620).disabled(model.busy)
    }
    var tray: some View {
        VStack(alignment:.leading,spacing:8) {
            Text("NOT IN A SLOT").font(.system(size:10,weight:.bold)).tracking(1.4).foregroundStyle(.secondary)
            ScrollView {
                LazyVGrid(columns:[GridItem(.adaptive(minimum:92),spacing:8)],spacing:8) {
                    ForEach(model.unassignedInputs) {item in ScanChip(item:item)}
                }
            }
            if model.unassignedInputs.isEmpty {Text("All scans are in a slot.").font(.caption).foregroundStyle(.secondary)}
        }
        .padding(12).frame(maxHeight:.infinity,alignment:.top).background(Color(nsColor:.controlBackgroundColor))
        .dropDestination(for:String.self){values,_ in
            for value in values {if let id=UUID(uuidString:value){model.unassign(id)}};return true
        }
    }
    @ViewBuilder var emptyHint: some View {
        if model.slots.isEmpty {
            VStack(alignment:.leading,spacing:8) {
                Text("No slots yet").font(.headline)
                Text("Use ‘Add Slot’ to make the slots yourself (for example Front, Back, Side A and Side B), then drag the scans in.").font(.caption).foregroundStyle(.secondary)
            }.padding(14).frame(maxWidth:.infinity,minHeight:150,alignment:.topLeading).background(studioPaper,in:RoundedRectangle(cornerRadius:12))
        }
    }
}

private struct SlotCard: View {
    @ObservedObject var model: StudioModel
    let slot: ScanSlot
    @State private var targeted=false
    var body: some View {
        VStack(alignment:.leading,spacing:10) {
            HStack {
                // Menu met knoppen i.p.v. een Picker: een Picker in een lijst die van volgorde verandert
                // (vak gevuld -> leeg vak verdwijnt) kon zelf een waarde terugschrijven naar een ander vak
                // (cd werd 'inlay', twee vakken 'Side A'). Een knop doet alleen iets als jij klikt.
                Menu(partLabel(slot.part)) {
                    ForEach(slotParts,id:\.self){part in Button(partLabel(part)){model.setSlotPart(slot.id,part)}}
                }.frame(width:150)
                Text(slot.part.hasPrefix("side") || slot.part.hasPrefix("cd") ? "record" : slot.part=="unknown" ? "Sleeve decides" : "cover").font(.caption2).foregroundStyle(.secondary)
                Spacer()
                Button {model.removeSlot(slot.id)} label:{Image(systemName:"trash")}.buttonStyle(.plain).foregroundStyle(.secondary).help("Remove slot (its scans go back to ‘Not in a slot’)")
            }
            if slot.items.isEmpty {
                Text("Drop scans here").font(.caption).foregroundStyle(.secondary).frame(maxWidth:.infinity,minHeight:86)
            } else {
                LazyVGrid(columns:[GridItem(.adaptive(minimum:76),spacing:6)],spacing:6) {
                    ForEach(slot.items) {item in ScanChip(item:item,size:76,onRemove:{model.unassign(item.id)})}
                }
            }
        }
        .padding(12)
        .background(RoundedRectangle(cornerRadius:12).fill(targeted ? studioAccent.opacity(0.10) : studioPaper))
        .overlay(RoundedRectangle(cornerRadius:12).stroke(targeted ? studioAccent : Color.secondary.opacity(0.25),style:StrokeStyle(lineWidth:targeted ? 2 : 1,dash:slot.items.isEmpty ? [5] : [])))
        .dropDestination(for:String.self,action:{values,_ in
            for value in values {if let id=UUID(uuidString:value){model.assign(id,to:slot.id)}};return true
        },isTargeted:{targeted=$0})
    }
}

private struct ScanChip: View {
    let item: MediaItem
    var size: CGFloat = 92
    var onRemove: (()->Void)? = nil
    var body: some View {
        VStack(spacing:4) {
            ZStack(alignment:.topTrailing) {
                RoundedRectangle(cornerRadius:6).fill(Color.white)
                StudioThumbnail(url:item.url,maxPixel:220).padding(4)
                if let onRemove {
                    Button(action:onRemove){Image(systemName:"xmark.circle.fill")}.buttonStyle(.plain).foregroundStyle(.secondary).padding(3).help("Take out of this slot")
                }
            }.frame(width:size,height:size*0.9)
            Text(item.title).font(.system(size:9)).lineLimit(1).truncationMode(.middle).frame(width:size)
        }
        .draggable(item.id.uuidString) {
            StudioThumbnail(url:item.url,maxPixel:160).frame(width:70,height:64)
        }
    }
}
