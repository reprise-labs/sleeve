import Foundation
import Vision
import AppKit
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
