import Foundation
import Vision
import AppKit
import ImageIO
if CommandLine.arguments.count < 2 { exit(1) }
if CommandLine.arguments.contains("--boxes") {
  // gebruik: sleeve_ocr <png> --boxes -> per regel: zekerheid \t tekst \t hoeken (tl,tr,br,bl; genormaliseerd, oorsprong linksonder)
  let url = URL(fileURLWithPath: CommandLine.arguments[1])
  guard let img = NSImage(contentsOf: url), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { exit(1) }
  let req = VNRecognizeTextRequest()
  req.recognitionLevel = .accurate
  req.usesLanguageCorrection = false
  try? VNImageRequestHandler(cgImage: cg, orientation: .up, options: [:]).perform([req])
  for r in (req.results ?? []) {
    if let c = r.topCandidates(1).first {
      let q = [r.topLeft, r.topRight, r.bottomRight, r.bottomLeft].map { String(format: "%.5f,%.5f", $0.x, $0.y) }.joined(separator: ";")
      print("\(c.confidence)\t\(c.string)\t\(q)")
    }
  }
  exit(0)
}
if CommandLine.arguments.contains("--identify") {
  let url = URL(fileURLWithPath: CommandLine.arguments[1])
  guard let source = CGImageSourceCreateWithURL(url as CFURL, [kCGImageSourceShouldCache:false] as CFDictionary),
    let image = CGImageSourceCreateThumbnailAtIndex(source, 0, [kCGImageSourceCreateThumbnailFromImageAlways:true,kCGImageSourceCreateThumbnailWithTransform:true,kCGImageSourceThumbnailMaxPixelSize:2200] as CFDictionary) else {exit(1)}
  var lines:[[String:Any]] = []
  for (degree,orientation):(Int,CGImagePropertyOrientation) in [(0,.up),(90,.right),(180,.down),(270,.left)] {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .fast
    request.usesLanguageCorrection = false
    try? VNImageRequestHandler(cgImage:image,orientation:orientation,options:[:]).perform([request])
    for observation in request.results ?? [] {
      if let candidate=observation.topCandidates(1).first {
        lines.append(["text":candidate.string,"confidence":candidate.confidence,"height":observation.boundingBox.height,"rotation":degree])
      }
    }
  }
  let barcodeRequest = VNDetectBarcodesRequest()
  try? VNImageRequestHandler(cgImage:image,options:[:]).perform([barcodeRequest])
  let codes=(barcodeRequest.results ?? []).compactMap{$0.payloadStringValue}
  if let data=try? JSONSerialization.data(withJSONObject:["lines":lines,"barcodes":codes]),let text=String(data:data,encoding:.utf8){print(text)}
  exit(0)
}
// gebruik: sleeve_ocr <png> -> per gelezen regel: stand \t zekerheid \t tekst
// Snelle tekstherkenning in alle vier de standen (0/90/180/270 tegen de klok in).
// Het script kiest de stand waarin de meeste echte woorden gelezen worden.
// (De snelle variant hangt niet als de Neural Engine bezig is.)
let url = URL(fileURLWithPath: CommandLine.arguments[1])
guard let img = NSImage(contentsOf: url), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { exit(1) }
let orients: [(Int, CGImagePropertyOrientation)] = [(0, .up), (90, .right), (180, .down), (270, .left)]
for (deg, o) in orients {
  let req = VNRecognizeTextRequest()
  req.recognitionLevel = .fast
  req.usesLanguageCorrection = false
  try? VNImageRequestHandler(cgImage: cg, orientation: o, options: [:]).perform([req])
  for r in (req.results ?? []) {
    if let c = r.topCandidates(1).first { print("\(deg)\t\(c.confidence)\t\(c.string)") }
  }
}
