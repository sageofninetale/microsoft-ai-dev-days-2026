const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, VerticalAlign, PageNumber, PageBreak, LevelFormat,
  ExternalHyperlink, TableOfContents
} = require('docx');
const fs = require('fs');

// ── Colour palette ──────────────────────────────────────────────────────────
const NAVY   = "1B3A6B";
const TEAL   = "0D7C8F";
const LIGHT  = "E8F4F7";
const MID    = "D0E8EE";
const DARK   = "1B3A6B";
const WHITE  = "FFFFFF";
const GREY   = "F5F7F9";
const BODY   = "2D2D2D";

// ── Border helpers ───────────────────────────────────────────────────────────
const cellBorder  = (color) => ({ style: BorderStyle.SINGLE, size: 4, color });
const noBorder    = () => ({ style: BorderStyle.NIL, size: 0, color: "FFFFFF" });
const allBorders  = (c) => ({ top: cellBorder(c), bottom: cellBorder(c), left: cellBorder(c), right: cellBorder(c) });
const noAllBorders = () => ({ top: noBorder(), bottom: noBorder(), left: noBorder(), right: noBorder() });

// ── Helpers ──────────────────────────────────────────────────────────────────
function h(level, text, opts = {}) {
  const sizes = { 1: 36, 2: 28, 3: 24 };
  const spacing = { 1: { before: 360, after: 200 }, 2: { before: 300, after: 160 }, 3: { before: 240, after: 120 } };
  return new Paragraph({
    heading: HeadingLevel[`HEADING_${level}`],
    spacing: spacing[level],
    pageBreakBefore: opts.pageBreak || false,
    children: [new TextRun({ text, bold: true, size: sizes[level], color: level === 1 ? NAVY : TEAL, font: "Arial" })],
  });
}

function body(text, opts = {}) {
  return new Paragraph({
    spacing: { before: 80, after: 120, line: 280 },
    alignment: opts.center ? AlignmentType.CENTER : AlignmentType.LEFT,
    children: [new TextRun({ text, size: 22, color: BODY, font: "Arial", bold: opts.bold || false, italics: opts.italic || false })],
  });
}

function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "bullets", level },
    spacing: { before: 60, after: 80 },
    children: [new TextRun({ text, size: 22, color: BODY, font: "Arial" })],
  });
}

function spacer(n = 1) {
  return Array.from({ length: n }, () =>
    new Paragraph({ spacing: { before: 0, after: 0 }, children: [new TextRun({ text: "", size: 22 })] })
  );
}

function divider(color = TEAL) {
  return new Paragraph({
    spacing: { before: 160, after: 160 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color, space: 1 } },
    children: [new TextRun({ text: "" })],
  });
}

function callout(heading, text, bgColor = LIGHT) {
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [9360],
    rows: [
      new TableRow({
        children: [new TableCell({
          borders: allBorders(TEAL),
          width: { size: 9360, type: WidthType.DXA },
          shading: { fill: bgColor, type: ShadingType.CLEAR },
          margins: { top: 160, bottom: 160, left: 240, right: 240 },
          children: [
            new Paragraph({
              spacing: { before: 40, after: 80 },
              children: [new TextRun({ text: heading, bold: true, size: 22, color: TEAL, font: "Arial" })]
            }),
            new Paragraph({
              spacing: { before: 40, after: 40 },
              children: [new TextRun({ text, size: 22, color: BODY, font: "Arial" })]
            }),
          ],
        })]
      })
    ]
  });
}

function twoColTable(rows, colWidths = [3000, 6360]) {
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: rows.map(([left, right], i) =>
      new TableRow({
        children: [
          new TableCell({
            borders: allBorders("CCDDEE"),
            width: { size: colWidths[0], type: WidthType.DXA },
            shading: { fill: i % 2 === 0 ? MID : LIGHT, type: ShadingType.CLEAR },
            margins: { top: 100, bottom: 100, left: 160, right: 160 },
            children: [new Paragraph({ children: [new TextRun({ text: left, bold: true, size: 21, color: DARK, font: "Arial" })] })],
          }),
          new TableCell({
            borders: allBorders("CCDDEE"),
            width: { size: colWidths[1], type: WidthType.DXA },
            shading: { fill: i % 2 === 0 ? WHITE : GREY, type: ShadingType.CLEAR },
            margins: { top: 100, bottom: 100, left: 160, right: 160 },
            children: [new Paragraph({ children: [new TextRun({ text: right, size: 21, color: BODY, font: "Arial" })] })],
          }),
        ]
      })
    )
  });
}

function agentBox(agent, current, replacement, role) {
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2400, 2880, 2880, 1200],
    rows: [
      new TableRow({
        children: [
          new TableCell({
            borders: allBorders("CCDDEE"),
            width: { size: 2400, type: WidthType.DXA },
            shading: { fill: NAVY, type: ShadingType.CLEAR },
            margins: { top: 100, bottom: 100, left: 160, right: 160 },
            verticalAlign: VerticalAlign.CENTER,
            children: [new Paragraph({ children: [new TextRun({ text: agent, bold: true, size: 21, color: WHITE, font: "Arial" })] })],
          }),
          new TableCell({
            borders: allBorders("CCDDEE"),
            width: { size: 2880, type: WidthType.DXA },
            shading: { fill: LIGHT, type: ShadingType.CLEAR },
            margins: { top: 100, bottom: 100, left: 160, right: 160 },
            children: [
              new Paragraph({ children: [new TextRun({ text: "Currently uses", size: 19, italic: true, color: "888888", font: "Arial" })] }),
              new Paragraph({ children: [new TextRun({ text: current, size: 21, color: BODY, font: "Arial" })] }),
            ],
          }),
          new TableCell({
            borders: allBorders("CCDDEE"),
            width: { size: 2880, type: WidthType.DXA },
            shading: { fill: GREY, type: ShadingType.CLEAR },
            margins: { top: 100, bottom: 100, left: 160, right: 160 },
            children: [
              new Paragraph({ children: [new TextRun({ text: "Replaced with", size: 19, italic: true, color: "888888", font: "Arial" })] }),
              new Paragraph({ children: [new TextRun({ text: replacement, bold: true, size: 21, color: TEAL, font: "Arial" })] }),
            ],
          }),
          new TableCell({
            borders: allBorders("CCDDEE"),
            width: { size: 1200, type: WidthType.DXA },
            shading: { fill: MID, type: ShadingType.CLEAR },
            margins: { top: 100, bottom: 100, left: 120, right: 120 },
            verticalAlign: VerticalAlign.CENTER,
            children: [new Paragraph({ children: [new TextRun({ text: role, size: 19, color: DARK, font: "Arial" })] })],
          }),
        ]
      })
    ]
  });
}

function sectionLabel(text) {
  return new Paragraph({
    spacing: { before: 0, after: 80 },
    children: [new TextRun({ text: text.toUpperCase(), size: 18, color: TEAL, bold: true, font: "Arial" })]
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
//  DOCUMENT
// ═══════════════════════════════════════════════════════════════════════════════
const doc = new Document({
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [{
          level: 0, format: LevelFormat.BULLET, text: "\u2022",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 600, hanging: 300 } } }
        }, {
          level: 1, format: LevelFormat.BULLET, text: "\u25E6",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 1080, hanging: 300 } } }
        }]
      }
    ]
  },
  styles: {
    default: {
      document: { run: { font: "Arial", size: 22, color: BODY } }
    },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: "Arial", color: NAVY },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 }
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: TEAL },
        paragraph: { spacing: { before: 300, after: 160 }, outlineLevel: 1 }
      },
      {
        id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: TEAL },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 2 }
      },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    headers: {
      default: new Header({
        children: [
          new Paragraph({
            spacing: { before: 0, after: 80 },
            border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: TEAL, space: 1 } },
            children: [
              new TextRun({ text: "CascadeAI \u2014 Open Source Demo Rebuild", size: 18, color: TEAL, font: "Arial" }),
              new TextRun({ text: "  |  Internal Working Document  |  April 2026", size: 18, color: "888888", font: "Arial" }),
            ]
          })
        ]
      })
    },
    footers: {
      default: new Footer({
        children: [
          new Paragraph({
            alignment: AlignmentType.RIGHT,
            border: { top: { style: BorderStyle.SINGLE, size: 4, color: TEAL, space: 1 } },
            spacing: { before: 80 },
            children: [
              new TextRun({ text: "Page ", size: 18, color: "888888", font: "Arial" }),
              new TextRun({ children: [PageNumber.CURRENT], size: 18, color: "888888", font: "Arial" }),
              new TextRun({ text: " of ", size: 18, color: "888888", font: "Arial" }),
              new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 18, color: "888888", font: "Arial" }),
            ]
          })
        ]
      })
    },
    children: [

      // ── COVER ──────────────────────────────────────────────────────────────
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [9360],
        rows: [new TableRow({ children: [new TableCell({
          borders: noAllBorders(),
          width: { size: 9360, type: WidthType.DXA },
          shading: { fill: NAVY, type: ShadingType.CLEAR },
          margins: { top: 480, bottom: 480, left: 480, right: 480 },
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              spacing: { before: 240, after: 120 },
              children: [new TextRun({ text: "CASCADE", size: 64, bold: true, color: WHITE, font: "Arial" }),
                         new TextRun({ text: "AI", size: 64, bold: true, color: "4EC9DF", font: "Arial" })]
            }),
            new Paragraph({
              alignment: AlignmentType.CENTER,
              spacing: { before: 0, after: 160 },
              children: [new TextRun({ text: "Open Source Demo Rebuild", size: 32, color: MID, font: "Arial" })]
            }),
            new Paragraph({
              alignment: AlignmentType.CENTER,
              spacing: { before: 0, after: 240 },
              children: [new TextRun({ text: "A Plain-English Guide for the Founding Team", size: 24, color: "AAD4DE", italic: true, font: "Arial" })]
            }),
          ]
        })]})],
      }),

      ...spacer(1),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [3120, 3120, 3120],
        rows: [new TableRow({ children: [
          new TableCell({
            borders: allBorders(MID),
            width: { size: 3120, type: WidthType.DXA },
            shading: { fill: GREY, type: ShadingType.CLEAR },
            margins: { top: 120, bottom: 120, left: 160, right: 160 },
            children: [
              new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Prepared for", size: 18, italic: true, color: "888888", font: "Arial" })] }),
              new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "CascadeAI Founding Team", size: 20, bold: true, color: DARK, font: "Arial" })] }),
            ]
          }),
          new TableCell({
            borders: allBorders(MID),
            width: { size: 3120, type: WidthType.DXA },
            shading: { fill: GREY, type: ShadingType.CLEAR },
            margins: { top: 120, bottom: 120, left: 160, right: 160 },
            children: [
              new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Date", size: 18, italic: true, color: "888888", font: "Arial" })] }),
              new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "April 2026", size: 20, bold: true, color: DARK, font: "Arial" })] }),
            ]
          }),
          new TableCell({
            borders: allBorders(MID),
            width: { size: 3120, type: WidthType.DXA },
            shading: { fill: GREY, type: ShadingType.CLEAR },
            margins: { top: 120, bottom: 120, left: 160, right: 160 },
            children: [
              new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Status", size: 18, italic: true, color: "888888", font: "Arial" })] }),
              new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Internal Draft", size: 20, bold: true, color: DARK, font: "Arial" })] }),
            ]
          }),
        ]})],
      }),

      ...spacer(2),
      new Paragraph({ children: [new PageBreak()] }),

      // ── TABLE OF CONTENTS ──────────────────────────────────────────────────
      h(1, "Contents"),
      divider(),
      new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-3" }),
      new Paragraph({ children: [new PageBreak()] }),

      // ══════════════════════════════════════════════════════════════════════
      // SECTION 0 – EXECUTIVE SUMMARY
      // ══════════════════════════════════════════════════════════════════════
      h(1, "Executive Summary"),
      divider(),
      body("CascadeAI turns spoken nurse handovers into a verified, plain-English clinical report in under two minutes. Right now, the product runs on Microsoft Azure and Azure OpenAI \u2014 paid cloud services that cost money every time the demo is run. Before we have paying customers, we need to be able to show the demo to hospitals, care homes, and investors without a running cost attached to every conversation."),
      ...spacer(1),
      body("This document explains how we can replace every paid component with free, open source tools \u2014 tools that run entirely on our own computers, cost nothing to operate, and can match or exceed the quality of the current setup. It also addresses every clinical concern raised by Dr Ameya Jagtap (MRCP) so that the founding team has a clear picture of what needs to happen before we can go to market with confidence."),
      ...spacer(1),
      callout(
        "The bottom line",
        "Three open source tools \u2014 WhisperX for transcription, MedCAT for clinical language understanding, and Llama 3 for report writing \u2014 can replace the Azure stack entirely. The total ongoing cost is zero. The system runs locally on a laptop or a modest server. No data leaves our premises, which is a meaningful advantage in healthcare where patient privacy is non-negotiable."
      ),
      ...spacer(1),
      new Paragraph({ children: [new PageBreak()] }),

      // ══════════════════════════════════════════════════════════════════════
      // SECTION 1 – WHAT CASCADEAI DOES
      // ══════════════════════════════════════════════════════════════════════
      h(1, "1.  What CascadeAI Does"),
      divider(),
      body("Before explaining the technical choices, it helps to be clear about what the system actually does and why it matters. This section is a brief reminder for anyone joining the conversation."),
      ...spacer(1),
      h(2, "The Problem We Solve"),
      body("At the end of every nursing shift, a handover takes place. A nurse from the departing team walks the incoming team through every patient or resident: what happened, what medication was given, what to watch out for, and what still needs doing. This usually takes 30 to 45 minutes and relies heavily on verbal memory and handwritten notes. If something gets missed, the incoming team has no record of it."),
      ...spacer(1),
      body("CascadeAI allows the nurse to speak their handover naturally \u2014 as if talking to a colleague \u2014 and turns that conversation into a structured, colour-coded written report in under two minutes. The report is verified against existing care records, flags medication concerns, and highlights the most urgent actions so the incoming nurse can get to work straight away."),
      ...spacer(1),
      h(2, "The Six Agents"),
      body("The system uses six specialised processes, called agents, that each handle one part of the job. They work together in sequence, like a relay race:"),
      ...spacer(1),
      twoColTable([
        ["IntakeAgent",       "Listens to the spoken handover and converts it into text."],
        ["UpdateAgent",       "Reads the text and pulls out the relevant clinical details: medications, vitals, observations."],
        ["CoordinatorAgent",  "Manages the overall process, decides priorities, and scores risk levels."],
        ["VerificationAgent", "Checks the extracted details against the existing care record to catch inconsistencies."],
        ["ProtocolAgent",     "Applies clinical protocols \u2014 for example, fall-risk checklists or medication interaction rules."],
        ["DraftGenerator",    "Writes the final plain-English report, colour-coded by urgency, ready for the incoming shift."],
      ]),
      ...spacer(1),
      body("At the moment, each agent relies on Microsoft Azure services. The goal of this document is to show how each agent can be powered by free, open source tools instead."),
      new Paragraph({ children: [new PageBreak()] }),

      // ══════════════════════════════════════════════════════════════════════
      // SECTION 2 – WHY WE ARE REBUILDING ON OPEN SOURCE
      // ══════════════════════════════════════════════════════════════════════
      h(1, "2.  Why We Are Rebuilding the Demo on Open Source"),
      divider(),
      body("There are three straightforward reasons."),
      ...spacer(1),
      h(2, "Cost"),
      body("Every time someone runs the current demo, Azure charges for the speech transcription and for the AI model that writes the report. These costs are small per use but add up quickly during a period of intensive demonstration and testing \u2014 exactly the phase we are in now. An open source version running on our own hardware has zero marginal cost per run."),
      ...spacer(1),
      h(2, "Privacy and Trust"),
      body("Healthcare is one of the most privacy-sensitive industries in the world. In the current setup, audio of a nurse handover is sent to a Microsoft server for transcription, and text is sent to an Azure OpenAI server for report generation. Even in a demo context, this raises questions."),
      ...spacer(1),
      body("A system that runs entirely on our own hardware never sends patient data anywhere. That is a powerful selling point to NHS trusts, care home operators, and anyone making a procurement decision. \u201CYour data never leaves the building\u201D is a message that resonates immediately with clinical governance teams."),
      ...spacer(1),
      h(2, "Control and Stability"),
      body("Open source tools do not change their pricing, deprecate models unexpectedly, or go offline. We control the version. We control the behaviour. We can freeze the model so the output stays consistent across trials \u2014 something that is essential for clinical validation, as Dr Jagtap has pointed out."),
      new Paragraph({ children: [new PageBreak()] }),

      // ══════════════════════════════════════════════════════════════════════
      // SECTION 3 – SPEECH TO TEXT
      // ══════════════════════════════════════════════════════════════════════
      h(1, "3.  Speech to Text: Our Recommendation"),
      divider(),
      sectionLabel("Replacing Azure Speech Services"),
      ...spacer(1),
      body("The IntakeAgent currently relies on Azure Speech Services to transcribe what the nurse says. We need a free, open source alternative that can handle long recordings (a full handover can run to 45 minutes or more), tell apart different speakers, and work reliably across different accents \u2014 including nurses from South Asia, West Africa, Eastern Europe, and Ireland, all common in the UK healthcare workforce."),
      ...spacer(1),
      h(2, "Our Recommendation: WhisperX + Pyannote"),
      callout(
        "What to use",
        "WhisperX (built on OpenAI\u2019s Whisper model) combined with Pyannote speaker diarization. Both are free and open source. They run locally on any modern laptop or server. No internet connection required once installed."
      ),
      ...spacer(1),
      h(3, "What is Whisper?"),
      body("Whisper is an open source transcription model released by OpenAI in 2022. Unlike the OpenAI API, the model itself is free to download and run on your own computer. It was trained on 680,000 hours of audio from the internet, covering 99 languages and a wide variety of accents. It is widely regarded as the most capable open source transcription tool available."),
      ...spacer(1),
      h(3, "What is WhisperX?"),
      body("WhisperX is a community-built wrapper around Whisper that adds two important capabilities Whisper lacks on its own: it handles very long audio files by intelligently splitting them into chunks before transcription (removing the 30-minute cap), and it adds word-level timestamps that are needed for accurate speaker labelling."),
      ...spacer(1),
      h(3, "What is Pyannote?"),
      body("Pyannote is a separate open source tool that listens to an audio file and works out who is speaking at each moment. It does not transcribe \u2014 it simply labels: \u201CSpeaker A said this section, Speaker B said that section.\u201D When combined with WhisperX\u2019s transcription, you get a complete, speaker-labelled transcript: \u201CNurse (handover): Patient has been breathless since 2pm. Nurse (incoming): Any change in oxygen sats?\u201D"),
      ...spacer(1),
      h(3, "Accent Performance"),
      body("In independent testing, the WhisperX + Pyannote combination has been shown to outperform several paid commercial transcription services on accented speech, particularly for longer audio files. Pyannote 3.1, the current version, achieves a speaker error rate of between 11 and 19 per cent on standard benchmarks \u2014 meaning the vast majority of speaker labels are correct even in noisy, multi-speaker conditions."),
      ...spacer(1),
      body("That said, accent robustness must be tested with real recordings from our target workforce before we rely on it clinically. This is consistent with Dr Jagtap\u2019s recommendation and is addressed in Section 6."),
      ...spacer(1),
      h(3, "Why Not Other Options?"),
      twoColTable([
        ["Azure Speech Services",   "Costs money per minute. Data leaves the building."],
        ["Google Speech-to-Text",   "Also paid. Same privacy concern."],
        ["Wav2Vec2 (Meta)",         "Strong for short utterances; less reliable for long-form clinical audio."],
        ["AssemblyAI",              "Excellent accuracy but a paid cloud service."],
        ["Whisper (plain)",         "Cannot label speakers and struggles with audio over 30 minutes."],
        ["WhisperX + Pyannote",     "Free. Local. Long audio. Speaker labels. Accent-robust. Our recommendation."],
      ], [3000, 6360]),
      new Paragraph({ children: [new PageBreak()] }),

      // ══════════════════════════════════════════════════════════════════════
      // SECTION 4 – CLINICAL LANGUAGE UNDERSTANDING
      // ══════════════════════════════════════════════════════════════════════
      h(1, "4.  Clinical Language Understanding: Our Recommendation"),
      divider(),
      sectionLabel("Understanding that different words mean the same clinical thing"),
      ...spacer(1),
      body("One of the most important requirements Dr Jagtap raised is that the system must understand clinical language properly. A nurse might say \u201Cbreathless.\u201D Another might say \u201Cshort of breath.\u201D A third might use the medical term \u201Cdyspnoea.\u201D All three mean the same thing, and the system must recognise that \u2014 otherwise it might treat them as different observations or miss them entirely."),
      ...spacer(1),
      body("This challenge is known in the field as \u201Cclinical synonym recognition\u201D or \u201Cconcept normalisation.\u201D It is well-studied in healthcare AI, and there are good open source tools to address it."),
      ...spacer(1),
      h(2, "Our Recommendation: MedCAT"),
      callout(
        "What to use",
        "MedCAT (Medical Concept Annotation Toolkit), developed by King\u2019s College London and the CogStack team. It is free, open source, and has been validated across 17 million clinical records at three major London NHS hospitals."
      ),
      ...spacer(1),
      h(3, "What is MedCAT?"),
      body("MedCAT is a piece of software that reads clinical text and identifies medical concepts \u2014 regardless of how they are worded. It maps lay terms, clinical shorthand, and formal medical vocabulary to a single agreed definition. It does this by using SNOMED-CT, the international standard clinical vocabulary used by the NHS, which contains over 350,000 medical concepts and their synonyms."),
      ...spacer(1),
      body("In practice, this means that when a nurse says \u201Cthe patient has been a bit off their food,\u201D MedCAT can recognise this as reduced appetite (a defined clinical concept) and flag it appropriately \u2014 even though the nurse did not use a medical term."),
      ...spacer(1),
      h(3, "How It Works in CascadeAI"),
      body("Once WhisperX has produced a transcript, MedCAT reads the text before it is passed to the report-writing model. It identifies and tags the clinical concepts mentioned. This has two benefits:"),
      bullet("It allows the UpdateAgent to extract structured clinical data (medications, observations, symptoms) reliably, even from informal speech."),
      bullet("It allows the VerificationAgent to compare what was said in the handover against what is already in the care record, because both are now expressed in the same clinical language."),
      ...spacer(1),
      h(3, "A Note on Licensing"),
      body("MedCAT itself is free and open source. However, the pre-trained models that come with it \u2014 particularly those trained on SNOMED-CT data \u2014 require a free registration with the National Institutes of Health (NIH) in the United States. This is a straightforward one-time process and does not involve any cost. We would need to complete this registration before deployment."),
      ...spacer(1),
      h(3, "Alternative Approaches"),
      body("For teams that want to avoid the NIH registration, there is a lighter-weight approach: build a custom dictionary of synonyms specific to the care home and hospital context. This is less comprehensive than SNOMED-CT but can be built and maintained internally. For the demo, either approach is viable; for clinical deployment, MedCAT with SNOMED-CT is the stronger choice."),
      new Paragraph({ children: [new PageBreak()] }),

      // ══════════════════════════════════════════════════════════════════════
      // SECTION 5 – REPORT GENERATION
      // ══════════════════════════════════════════════════════════════════════
      h(1, "5.  Report Generation: Our Recommendation"),
      divider(),
      sectionLabel("Replacing Azure OpenAI (GPT) with a local language model"),
      ...spacer(1),
      body("The DraftGenerator currently sends structured clinical data to Azure OpenAI, which uses a version of GPT to write the final handover report. This is the most visible part of the system \u2014 the quality of the report is what clinical staff will judge first. We need a free, local alternative that can produce the same quality of plain-English clinical writing."),
      ...spacer(1),
      h(2, "Our Recommendation: Llama 3 via Ollama"),
      callout(
        "What to use",
        "Meta\u2019s Llama 3 (8 billion parameter version), run locally using Ollama. Free to download and use. Runs on a consumer-grade laptop with 8GB of memory once quantized. No internet connection needed during operation."
      ),
      ...spacer(1),
      h(3, "What is Llama 3?"),
      body("Llama 3 is an open source large language model released by Meta in 2024. It is the same class of technology as GPT \u2014 a system trained on vast amounts of text that can read a prompt and generate coherent, relevant written output. The 8-billion-parameter version is compact enough to run locally on most modern computers while still producing high-quality text."),
      ...spacer(1),
      body("In independent evaluations, Llama 3 at 70 billion parameters matches the performance of GPT-4 on many benchmarks. The smaller 8-billion-parameter version, which is what we would use for the demo, is somewhat less capable but still significantly better than earlier open source models. For the specific task of writing a structured 150-word clinical summary from structured input data, the 8B version performs very well."),
      ...spacer(1),
      h(3, "What is Ollama?"),
      body("Ollama is a free, open source tool that makes it very easy to download and run language models on a local computer. Instead of complex server configuration, you run one command (\u2018ollama run llama3\u2019) and the model is available instantly. It handles memory management, model loading, and the technical infrastructure automatically."),
      ...spacer(1),
      body("From a practical standpoint, this means anyone on the team can set up the demo environment in under 30 minutes with no specialist knowledge."),
      ...spacer(1),
      h(3, "Clinical Text Generation: What the Research Shows"),
      body("Several research groups have tested Llama 3 in clinical documentation contexts. Key findings:"),
      bullet("A study in radiation oncology fine-tuned Llama 3 locally to generate physician letters, reporting that the model produced outputs comparable to junior clinical writers after fine-tuning."),
      bullet("When tested on discharge summary generation, Llama 3 at 8B achieved the best BLEU and ROUGE scores among open source models in its class."),
      bullet("The model successfully removed personally identifying information from clinical text with a 98 per cent success rate in one German hospital study, indicating reliable handling of structured clinical content."),
      ...spacer(1),
      h(3, "The Hallucination Risk \u2014 and How We Address It"),
      body("Language models can sometimes generate plausible-sounding but incorrect information. In a clinical context, this is unacceptable. A report that invents a medication or misquotes a vital sign could cause harm."),
      ...spacer(1),
      body("The way we address this is through the pipeline structure itself. The DraftGenerator does not work from audio alone. By the time it writes the report, the data has already been structured by the UpdateAgent, verified against the care record by the VerificationAgent, and validated against protocols by the ProtocolAgent. The language model\u2019s job is to turn verified, structured data into readable prose \u2014 not to reason about clinical facts from scratch. This significantly reduces the scope for harmful errors."),
      ...spacer(1),
      body("Additionally, the output of the DraftGenerator should always be reviewed by the departing nurse before the incoming team receives it. The system generates a draft; a human signs it off. This is analogous to how a doctor signs off a letter prepared by a medical secretary."),
      ...spacer(1),
      h(3, "Model Drift: Keeping Output Consistent Over Time"),
      body("Dr Jagtap raised the specific concern that after clinical trials, model output must remain consistent and not degrade. This is called \u201Cmodel drift\u201D and it is a genuine risk with cloud-hosted AI: the provider can update the model without notice, changing the output behaviour."),
      ...spacer(1),
      body("With a locally-hosted open source model, we control this completely. We download a specific version of Llama 3, lock it in place, and it will never change unless we deliberately update it. If we run the same input through the model a year from now, we will get the same output. This is essential for clinical validation \u2014 you cannot validate a system that is constantly changing underneath you."),
      new Paragraph({ children: [new PageBreak()] }),

      // ══════════════════════════════════════════════════════════════════════
      // SECTION 6 – THE 6-AGENT PIPELINE
      // ══════════════════════════════════════════════════════════════════════
      h(1, "6.  How the Open Source Tools Fit the Six-Agent Pipeline"),
      divider(),
      body("This section maps each of the six agents to its new open source equivalent, explaining what changes and what stays the same."),
      ...spacer(1),
      body("The table below gives a summary. Detailed descriptions follow."),
      ...spacer(1),

      // Agent summary table header
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2400, 2880, 2880, 1200],
        rows: [new TableRow({
          tableHeader: true,
          children: [
            new TableCell({
              borders: allBorders(NAVY),
              width: { size: 2400, type: WidthType.DXA },
              shading: { fill: NAVY, type: ShadingType.CLEAR },
              margins: { top: 100, bottom: 100, left: 160, right: 160 },
              children: [new Paragraph({ children: [new TextRun({ text: "Agent", bold: true, size: 21, color: WHITE, font: "Arial" })] })],
            }),
            new TableCell({
              borders: allBorders(NAVY),
              width: { size: 2880, type: WidthType.DXA },
              shading: { fill: NAVY, type: ShadingType.CLEAR },
              margins: { top: 100, bottom: 100, left: 160, right: 160 },
              children: [new Paragraph({ children: [new TextRun({ text: "Currently Uses", bold: true, size: 21, color: WHITE, font: "Arial" })] })],
            }),
            new TableCell({
              borders: allBorders(NAVY),
              width: { size: 2880, type: WidthType.DXA },
              shading: { fill: NAVY, type: ShadingType.CLEAR },
              margins: { top: 100, bottom: 100, left: 160, right: 160 },
              children: [new Paragraph({ children: [new TextRun({ text: "Open Source Replacement", bold: true, size: 21, color: WHITE, font: "Arial" })] })],
            }),
            new TableCell({
              borders: allBorders(NAVY),
              width: { size: 1200, type: WidthType.DXA },
              shading: { fill: NAVY, type: ShadingType.CLEAR },
              margins: { top: 100, bottom: 100, left: 120, right: 120 },
              children: [new Paragraph({ children: [new TextRun({ text: "Cost", bold: true, size: 21, color: WHITE, font: "Arial" })] })],
            }),
          ]
        })]
      }),

      agentBox("IntakeAgent",       "Azure Speech Services",      "WhisperX + Pyannote",       "Free"),
      agentBox("UpdateAgent",       "Azure OpenAI (GPT-4)",        "MedCAT + Llama 3",           "Free"),
      agentBox("CoordinatorAgent",  "Azure OpenAI (GPT-4)",        "Llama 3 (local)",            "Free"),
      agentBox("VerificationAgent", "Azure OpenAI + PostgreSQL",   "MedCAT + PostgreSQL",        "Free"),
      agentBox("ProtocolAgent",     "Azure OpenAI (GPT-4)",        "Llama 3 + rule library",     "Free"),
      agentBox("DraftGenerator",    "Azure OpenAI (GPT-4)",        "Llama 3 (local, locked)",    "Free"),

      ...spacer(1),
      h(2, "Agent-by-Agent Walkthrough"),
      h(3, "IntakeAgent \u2014 Listens and Transcribes"),
      body("This agent receives the audio recording and produces a written transcript. The Azure replacement is WhisperX, which performs the transcription, combined with Pyannote, which labels each section with the speaker who said it."),
      ...spacer(1),
      body("The output is the same as before: a text transcript of the handover, now also annotated with speaker turns (e.g., \u201CNurse A:\u201D, \u201CNurse B:\u201D). This is passed directly to the UpdateAgent."),
      ...spacer(1),
      h(3, "UpdateAgent \u2014 Extracts Clinical Details"),
      body("This agent reads the transcript and pulls out structured clinical information: which medications were mentioned, what vital signs were recorded, what symptoms were described. MedCAT does the heavy lifting here, recognising clinical concepts regardless of how they were expressed."),
      ...spacer(1),
      body("Where the current system uses GPT to make sense of the language, MedCAT uses the established SNOMED-CT clinical vocabulary \u2014 more reliable, more transparent, and better suited to this specific task."),
      ...spacer(1),
      h(3, "CoordinatorAgent \u2014 Manages the Process"),
      body("This agent oversees the other agents, decides the order of operations, and assigns a risk score to the handover based on what was said. In the open source version, Llama 3 takes over this role, reading the structured output from the UpdateAgent and deciding what is critical, what is routine, and what needs flagging."),
      ...spacer(1),
      h(3, "VerificationAgent \u2014 Checks Against the Care Record"),
      body("This agent compares what was said in the handover against the resident\u2019s existing care record in the database. If the nurse says the patient takes Warfarin but the record shows a different medication, this agent flags the discrepancy."),
      ...spacer(1),
      body("In the open source version, MedCAT ensures that the language in the transcript and the language in the care record are compared in the same clinical vocabulary \u2014 so \u201Cblood thinners\u201D in the transcript correctly matches \u201CWarfarin\u201D in the record. The database itself (PostgreSQL) is already free and stays unchanged."),
      ...spacer(1),
      h(3, "ProtocolAgent \u2014 Applies Clinical Rules"),
      body("This agent checks the structured handover data against a set of clinical protocols \u2014 for example, fall-risk assessment, pressure ulcer prevention, or medication interaction rules. In the open source version, Llama 3 applies these protocols, guided by a library of rules we maintain ourselves. This library does not change unless we update it deliberately, which is important for validation."),
      ...spacer(1),
      h(3, "DraftGenerator \u2014 Writes the Final Report"),
      body("This agent receives verified, structured, protocol-checked data and produces the readable handover report. Llama 3 performs this role in the open source version."),
      ...spacer(1),
      body("It is important to understand that by this point in the pipeline, the language model is not reasoning from scratch. It is converting a structured data record \u2014 essentially a list of verified facts \u2014 into natural English prose. This is a much simpler and safer task than asking a language model to interpret raw clinical audio, and it is well within the capability of the 8-billion-parameter version of Llama 3."),
      new Paragraph({ children: [new PageBreak()] }),

      // ══════════════════════════════════════════════════════════════════════
      // SECTION 7 – DR JAGTAP'S CLINICAL REQUIREMENTS
      // ══════════════════════════════════════════════════════════════════════
      h(1, "7.  Addressing Dr Jagtap\u2019s Clinical Requirements"),
      divider(),
      body("Dr Ameya Jagtap (MRCP) has raised seven specific clinical requirements that must be addressed before the product goes to market. This section addresses each one directly and explains how the open source rebuild either meets or creates a path to meeting it."),
      ...spacer(1),

      h(2, "7.1  Validation is Non-Negotiable"),
      callout("Dr Jagtap\u2019s concern", "There must be test cases, trial cases, and user stories before the system is used in a clinical setting."),
      ...spacer(1),
      body("We fully agree. The open source rebuild makes validation easier, not harder, for two reasons."),
      ...spacer(1),
      body("First, because the model is locked locally, we can run the same test case through the system a hundred times and expect the same answer every time. This is essential for building a test suite. With a cloud-hosted model that updates without notice, this is impossible."),
      ...spacer(1),
      body("Second, because the system is free to run, we can generate as many test cases as we need without budget constraints. We can simulate hundreds of handover scenarios, covering edge cases like complex medication lists, multiple patients, ambiguous clinical language, and unusual accents."),
      ...spacer(1),
      body("Recommended next step: define a set of 50 standard handover scenarios with known correct outputs. Run these through both the current Azure system and the open source rebuild. Document where they agree and where they differ. This becomes the validation baseline."),
      ...spacer(1),

      h(2, "7.2  Plain English Output Only"),
      callout("Dr Jagtap\u2019s concern", "No compression, no clinical shorthand the nurse wouldn\u2019t use. The report must read like something a nurse would write."),
      ...spacer(1),
      body("This is primarily a prompt design challenge rather than a technology choice. The instruction given to the language model \u2014 the \u201Cprompt\u201D \u2014 tells it how to write. We will write a prompt that explicitly instructs Llama 3: \u201CWrite this report in plain English. Do not use abbreviations. Do not use medical jargon. Write as if explaining to a colleague who is not medically trained.\u201D"),
      ...spacer(1),
      body("The advantage of a locally-hosted, version-locked model is that once we have a prompt that produces the right tone and style, it will continue to produce that tone and style indefinitely. The model will not be updated, so the output will not change."),
      ...spacer(1),
      body("Recommended next step: co-write the report prompt with a Clinical Nurse Manager (CNM) so that the language it produces feels natural to nurses rather than clinical or robotic."),
      ...spacer(1),

      h(2, "7.3  Accent Diversity"),
      callout("Dr Jagtap\u2019s concern", "The system must handle nurses from different backgrounds. It needs to be tested across accents."),
      ...spacer(1),
      body("WhisperX was trained on one of the most diverse audio datasets ever assembled: 680,000 hours of real-world speech from the internet, covering dozens of accents in English alone. Independent testing has shown it outperforms several paid services on accented English, particularly for longer recordings."),
      ...spacer(1),
      body("However, published benchmarks are not the same as testing with our specific user group. The UK nursing workforce includes large communities from the Philippines, Nigeria, India, Zimbabwe, and Eastern Europe. Each accent group has different phonetic patterns. We need to test with recordings from real nurses or close analogues before we can claim reliable performance."),
      ...spacer(1),
      body("Recommended next step: recruit five to ten test participants representing different accent backgrounds and run sample handovers through the system. Compare the transcripts against a human-written ground truth. Measure word error rate. Any accent group that performs poorly should be fine-tuned specifically."),
      ...spacer(1),

      h(2, "7.4  Clinical Language Understanding"),
      callout("Dr Jagtap\u2019s concern", "The system must understand that different words can mean the same clinical thing."),
      ...spacer(1),
      body("This is exactly what MedCAT addresses. The SNOMED-CT vocabulary used by MedCAT contains over 350,000 medical concepts, each with multiple synonyms, lay terms, and variant spellings. When a nurse says \u201Cchest pain,\u201D \u201Ccardiac discomfort,\u201D or \u201Ca tight feeling in the chest,\u201D MedCAT maps all three to the same clinical concept."),
      ...spacer(1),
      body("This is not a workaround \u2014 it is the internationally standardised approach to clinical language interoperability. The NHS uses SNOMED-CT as its primary clinical terminology system. By using MedCAT and SNOMED-CT in our pipeline, we are aligning with the same standard that NHS trusts already use."),
      ...spacer(1),

      h(2, "7.5  Model Drift"),
      callout("Dr Jagtap\u2019s concern", "Output must stay consistent after trials and not degrade over time."),
      ...spacer(1),
      body("With a locally-hosted, version-locked model, drift is entirely within our control. We choose when to update the model. If we do not update it, it will produce identical output for identical input indefinitely."),
      ...spacer(1),
      body("The recommended practice is to \u201Cfreeze\u201D the model version at the point where we begin formal clinical trials. Any future version updates are treated as a new system version that requires re-validation before deployment. This is consistent with standard medical device software practice and is exactly the kind of governance structure that regulatory bodies expect."),
      ...spacer(1),

      h(2, "7.6  Sit with a Clinical Nurse Manager"),
      callout("Dr Jagtap\u2019s concern", "We must understand real nurse needs before assuming anything."),
      ...spacer(1),
      body("This is a human process, not a technical one, and it is the most important item on this list."),
      ...spacer(1),
      body("Every assumption in this document \u2014 about what nurses say, how they say it, what they need in a report, and what format works best for an incoming shift \u2014 must be validated by sitting with actual nurses and observing real handovers. The technology is the easy part. Understanding the workflow is the hard part."),
      ...spacer(1),
      body("Recommended next step: arrange a half-day observation session at a partner care home or hospital ward. Attend a real shift handover. Record what the nurses say (with consent), what information gets communicated, what gets forgotten, and what format the receiving nurse actually finds useful. Use this to refine the DraftGenerator prompt and the report layout."),
      ...spacer(1),

      h(2, "7.7  Market Definition"),
      callout("Dr Jagtap\u2019s concern", "We must decide whether we are targeting hospitals, care homes, or residential settings before going to market."),
      ...spacer(1),
      body("This is a strategic decision for the founding team rather than a technical one, but the technology choices described in this document are relevant to it."),
      ...spacer(1),
      twoColTable([
        ["Hospital (NHS)",           "Highest data governance requirements. Needs IG Toolkit compliance, DCB0129 clinical safety certification, and likely CQC or MHRA involvement. Procurement cycles are 12-24 months. Integration with existing EPR systems (e.g. EMIS, SystemOne) is expected."],
        ["Care Home (private)",      "Faster procurement decisions. Less regulated but growing compliance requirements. Care home operators are under pressure to reduce staff time on documentation. Strong commercial fit for the current product."],
        ["Residential / supported",  "Highly variable. Smaller teams, less complex handovers, but often less technical infrastructure. Could be a good early market if the product is kept simple."],
      ]),
      ...spacer(1),
      body("The open source architecture described in this document is compatible with all three markets. The local deployment model (no data leaving the premises) is a particular advantage in NHS procurement conversations, where cloud data handling is a major concern."),
      new Paragraph({ children: [new PageBreak()] }),

      // ══════════════════════════════════════════════════════════════════════
      // SECTION 8 – WHAT THE REBUILT DEMO LOOKS LIKE IN PRACTICE
      // ══════════════════════════════════════════════════════════════════════
      h(1, "8.  What the Rebuilt Demo Looks Like in Practice"),
      divider(),
      body("It is worth being concrete about what we are proposing, so the team has a clear picture of what the open source demo actually involves."),
      ...spacer(1),
      h(2, "Hardware"),
      body("The demo can run on a standard laptop with 16GB of RAM. A MacBook Pro M2 or equivalent Windows machine is sufficient. For a more polished demo environment, a small dedicated server (a refurbished mini-PC costing around \u00A3300) could be set up to run the demo continuously in a care home or hospital setting without relying on a team member\u2019s laptop."),
      ...spacer(1),
      h(2, "Setup"),
      body("The full setup \u2014 downloading Ollama, pulling the Llama 3 model, installing WhisperX and Pyannote, and registering MedCAT \u2014 takes approximately two to four hours for someone with basic technical knowledge. Once set up, running the demo takes no ongoing maintenance."),
      ...spacer(1),
      h(2, "The Demo Flow"),
      bullet("A nurse speaks a handover into a microphone. The recording can be a real handover, a scripted test case, or a synthetic recording."),
      bullet("WhisperX transcribes the audio in real time or near-real time. For a 5-minute handover, transcription takes under 30 seconds on a modern laptop."),
      bullet("MedCAT processes the transcript, identifying clinical concepts and tagging them."),
      bullet("The CoordinatorAgent (Llama 3) prioritises the findings and assigns risk levels."),
      bullet("The VerificationAgent checks the output against a sample care record in the PostgreSQL database."),
      bullet("The ProtocolAgent checks for any protocol flags."),
      bullet("Llama 3 writes the final report. For a 5-minute handover, this takes under 10 seconds."),
      bullet("The report appears on screen: colour-coded, plain English, ready for the incoming nurse."),
      ...spacer(1),
      body("Total time from end of spoken handover to final report: under two minutes, consistent with the current product promise."),
      new Paragraph({ children: [new PageBreak()] }),

      // ══════════════════════════════════════════════════════════════════════
      // SECTION 9 – RECOMMENDED NEXT STEPS
      // ══════════════════════════════════════════════════════════════════════
      h(1, "9.  Recommended Next Steps"),
      divider(),
      body("The following actions are recommended in priority order. Steps 1 to 3 can be done immediately. Steps 4 to 6 require access to clinical partners."),
      ...spacer(1),
      twoColTable([
        ["1. Install and test WhisperX",      "Download WhisperX and Pyannote. Run them against three to five recorded nurse handovers (real or scripted). Assess transcript quality and speaker labelling."],
        ["2. Install and test Ollama + Llama 3", "Download Ollama and pull the Llama 3 8B model. Write an initial report-generation prompt. Run it against the transcripts from Step 1. Review the output for tone and accuracy."],
        ["3. Register for MedCAT",            "Complete the free NIH UMLS registration. Download the MedCAT SNOMED-CT model. Test it against a set of handover transcripts containing synonyms (breathless vs. dyspnoea, etc.)."],
        ["4. Sit with a CNM",                 "Arrange an observation session at a care home or ward. Map the real handover workflow. Refine the report prompt based on what nurses actually find useful."],
        ["5. Build the validation test set",  "Define 50 standard handover scenarios with known correct outputs. Run both the Azure system and the open source rebuild against them. Document differences."],
        ["6. Decide the target market",       "Review the hospital vs. care home vs. residential options and agree a primary market before the next demo round. This determines the compliance requirements and the sales approach."],
      ]),
      ...spacer(1),
      new Paragraph({ children: [new PageBreak()] }),

      // ══════════════════════════════════════════════════════════════════════
      // SECTION 10 – SUMMARY COMPARISON
      // ══════════════════════════════════════════════════════════════════════
      h(1, "10.  Summary Comparison"),
      divider(),
      body("The table below shows the current Azure stack alongside the recommended open source replacement for each component."),
      ...spacer(1),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2000, 2000, 3160, 1200, 1000],
        rows: [
          new TableRow({
            tableHeader: true,
            children: [
              new TableCell({ borders: allBorders(NAVY), width: { size: 2000, type: WidthType.DXA }, shading: { fill: NAVY, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: "Function", bold: true, size: 20, color: WHITE, font: "Arial" })] })] }),
              new TableCell({ borders: allBorders(NAVY), width: { size: 2000, type: WidthType.DXA }, shading: { fill: NAVY, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: "Current (Azure)", bold: true, size: 20, color: WHITE, font: "Arial" })] })] }),
              new TableCell({ borders: allBorders(NAVY), width: { size: 3160, type: WidthType.DXA }, shading: { fill: NAVY, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: "Open Source Replacement", bold: true, size: 20, color: WHITE, font: "Arial" })] })] }),
              new TableCell({ borders: allBorders(NAVY), width: { size: 1200, type: WidthType.DXA }, shading: { fill: NAVY, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Cost", bold: true, size: 20, color: WHITE, font: "Arial" })] })] }),
              new TableCell({ borders: allBorders(NAVY), width: { size: 1000, type: WidthType.DXA }, shading: { fill: NAVY, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: "Data stays local?", bold: true, size: 20, color: WHITE, font: "Arial" })] })] }),
            ]
          }),
          ...[
            ["Transcription",          "Azure Speech",       "WhisperX + Pyannote",         "Free",  "Yes"],
            ["Clinical NLP",           "Azure OpenAI (GPT)", "MedCAT + SNOMED-CT",           "Free",  "Yes"],
            ["Report generation",      "Azure OpenAI (GPT)", "Llama 3 via Ollama",           "Free",  "Yes"],
            ["Agent orchestration",    "Azure OpenAI (GPT)", "Llama 3 (local)",              "Free",  "Yes"],
            ["Care record database",   "Azure PostgreSQL",   "PostgreSQL (self-hosted)",     "Free",  "Yes"],
            ["Model version control",  "None (Azure manages)","Locked local version",        "Free",  "Yes"],
          ].map(([fn, cur, rep, cost, local], i) =>
            new TableRow({ children: [
              new TableCell({ borders: allBorders("BBCCDD"), width: { size: 2000, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHT : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: fn, size: 20, bold: true, color: DARK, font: "Arial" })] })] }),
              new TableCell({ borders: allBorders("BBCCDD"), width: { size: 2000, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHT : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: cur, size: 20, color: "BB4444", font: "Arial" })] })] }),
              new TableCell({ borders: allBorders("BBCCDD"), width: { size: 3160, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHT : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: rep, size: 20, bold: true, color: TEAL, font: "Arial" })] })] }),
              new TableCell({ borders: allBorders("BBCCDD"), width: { size: 1200, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHT : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: cost, size: 20, color: "227722", bold: true, font: "Arial" })] })] }),
              new TableCell({ borders: allBorders("BBCCDD"), width: { size: 1000, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHT : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, children: [new Paragraph({ children: [new TextRun({ text: local, size: 20, color: "227722", bold: true, font: "Arial" })] })] }),
            ]})
          )
        ]
      }),
      ...spacer(2),

      // ══════════════════════════════════════════════════════════════════════
      // APPENDIX – TOOL LINKS
      // ══════════════════════════════════════════════════════════════════════
      new Paragraph({ children: [new PageBreak()] }),
      h(1, "Appendix: Tool Links and Repository References"),
      divider(),
      body("Every tool recommended in this document is free and open source. The links below are the exact repositories to fork or download from. No account or subscription is required to access any of them (the MedCAT SNOMED-CT model requires a one-time free NIH registration, noted below)."),
      ...spacer(1),

      h(2, "Speech to Text"),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2400, 4560, 2400],
        rows: [
          new TableRow({ tableHeader: true, children: [
            new TableCell({ borders: allBorders(NAVY), width: { size: 2400, type: WidthType.DXA }, shading: { fill: NAVY, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: "Tool", bold: true, size: 20, color: WHITE, font: "Arial" })] })] }),
            new TableCell({ borders: allBorders(NAVY), width: { size: 4560, type: WidthType.DXA }, shading: { fill: NAVY, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: "Purpose", bold: true, size: 20, color: WHITE, font: "Arial" })] })] }),
            new TableCell({ borders: allBorders(NAVY), width: { size: 2400, type: WidthType.DXA }, shading: { fill: NAVY, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: "Repository", bold: true, size: 20, color: WHITE, font: "Arial" })] })] }),
          ]}),
          ...[
            ["WhisperX",          "Long-form transcription with word-level timestamps and chunking for audio up to 60+ minutes",   "github.com/m-bain/whisperX"],
            ["Pyannote Audio",     "Speaker diarization — identifies who is speaking at each moment in the transcript",             "github.com/pyannote/pyannote-audio"],
            ["OpenAI Whisper",     "The base transcription model that WhisperX is built on (included automatically)",               "github.com/openai/whisper"],
          ].map(([tool, purpose, repo], i) =>
            new TableRow({ children: [
              new TableCell({ borders: allBorders("BBCCDD"), width: { size: 2400, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHT : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: tool, bold: true, size: 20, color: DARK, font: "Arial" })] })] }),
              new TableCell({ borders: allBorders("BBCCDD"), width: { size: 4560, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHT : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: purpose, size: 20, color: BODY, font: "Arial" })] })] }),
              new TableCell({ borders: allBorders("BBCCDD"), width: { size: 2400, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHT : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, children: [new Paragraph({ children: [new ExternalHyperlink({ link: "https://" + repo, children: [new TextRun({ text: repo, size: 20, color: TEAL, underline: {}, font: "Arial" })] })] })] }),
            ]})
          )
        ]
      }),

      ...spacer(1),
      h(2, "Clinical Language Understanding"),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2400, 4560, 2400],
        rows: [
          new TableRow({ tableHeader: true, children: [
            new TableCell({ borders: allBorders(NAVY), width: { size: 2400, type: WidthType.DXA }, shading: { fill: NAVY, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: "Tool", bold: true, size: 20, color: WHITE, font: "Arial" })] })] }),
            new TableCell({ borders: allBorders(NAVY), width: { size: 4560, type: WidthType.DXA }, shading: { fill: NAVY, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: "Purpose", bold: true, size: 20, color: WHITE, font: "Arial" })] })] }),
            new TableCell({ borders: allBorders(NAVY), width: { size: 2400, type: WidthType.DXA }, shading: { fill: NAVY, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: "Repository", bold: true, size: 20, color: WHITE, font: "Arial" })] })] }),
          ]}),
          ...[
            ["MedCAT",           "Maps any clinical phrase to a SNOMED-CT concept — solves the synonym problem (breathless = dyspnoea = short of breath). Validated on 17M NHS records.",  "github.com/CogStack/MedCAT"],
            ["MedCATtrainer",    "Web interface for clinicians to review, correct, and improve MedCAT\u2019s concept recognition on your own data",                                        "github.com/CogStack/MedCATtrainer"],
            ["SNOMED-CT via NIH","The clinical vocabulary behind MedCAT. Free to access after one-time NIH registration at uts.nlm.nih.gov",                                               "uts.nlm.nih.gov (free registration)"],
          ].map(([tool, purpose, repo], i) =>
            new TableRow({ children: [
              new TableCell({ borders: allBorders("BBCCDD"), width: { size: 2400, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHT : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: tool, bold: true, size: 20, color: DARK, font: "Arial" })] })] }),
              new TableCell({ borders: allBorders("BBCCDD"), width: { size: 4560, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHT : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: purpose, size: 20, color: BODY, font: "Arial" })] })] }),
              new TableCell({ borders: allBorders("BBCCDD"), width: { size: 2400, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHT : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, children: [new Paragraph({ children: [new ExternalHyperlink({ link: "https://" + repo.split(" ")[0], children: [new TextRun({ text: repo, size: 20, color: TEAL, underline: {}, font: "Arial" })] })] })] }),
            ]})
          )
        ]
      }),

      ...spacer(1),
      h(2, "Open Source LLM for Report Generation"),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2400, 4560, 2400],
        rows: [
          new TableRow({ tableHeader: true, children: [
            new TableCell({ borders: allBorders(NAVY), width: { size: 2400, type: WidthType.DXA }, shading: { fill: NAVY, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: "Tool", bold: true, size: 20, color: WHITE, font: "Arial" })] })] }),
            new TableCell({ borders: allBorders(NAVY), width: { size: 4560, type: WidthType.DXA }, shading: { fill: NAVY, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: "Purpose", bold: true, size: 20, color: WHITE, font: "Arial" })] })] }),
            new TableCell({ borders: allBorders(NAVY), width: { size: 2400, type: WidthType.DXA }, shading: { fill: NAVY, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: "Repository / Download", bold: true, size: 20, color: WHITE, font: "Arial" })] })] }),
          ]}),
          ...[
            ["Llama 3 (Meta)",   "The language model that generates the final plain-English clinical report. The 8B version runs on any modern laptop. Free to use commercially.",               "huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct"],
            ["Ollama",           "The tool that makes Llama 3 easy to run locally \u2014 one command downloads and starts the model. No configuration needed.",                                 "github.com/ollama/ollama"],
            ["LM Studio",        "Optional: a free desktop app that lets you run and test Llama 3 with a visual interface. Useful for non-technical team members.",                            "lmstudio.ai (free download)"],
            ["llama.cpp",        "The underlying engine that makes Llama 3 run efficiently on a laptop CPU without a specialist graphics card.",                                               "github.com/ggerganov/llama.cpp"],
          ].map(([tool, purpose, repo], i) =>
            new TableRow({ children: [
              new TableCell({ borders: allBorders("BBCCDD"), width: { size: 2400, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHT : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: tool, bold: true, size: 20, color: DARK, font: "Arial" })] })] }),
              new TableCell({ borders: allBorders("BBCCDD"), width: { size: 4560, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHT : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: purpose, size: 20, color: BODY, font: "Arial" })] })] }),
              new TableCell({ borders: allBorders("BBCCDD"), width: { size: 2400, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHT : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, children: [new Paragraph({ children: [new ExternalHyperlink({ link: "https://" + repo.split(" ")[0], children: [new TextRun({ text: repo, size: 20, color: TEAL, underline: {}, font: "Arial" })] })] })] }),
            ]})
          )
        ]
      }),

      ...spacer(1),
      h(2, "Agent Orchestration"),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2400, 4560, 2400],
        rows: [
          new TableRow({ tableHeader: true, children: [
            new TableCell({ borders: allBorders(NAVY), width: { size: 2400, type: WidthType.DXA }, shading: { fill: NAVY, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: "Tool", bold: true, size: 20, color: WHITE, font: "Arial" })] })] }),
            new TableCell({ borders: allBorders(NAVY), width: { size: 4560, type: WidthType.DXA }, shading: { fill: NAVY, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: "Purpose", bold: true, size: 20, color: WHITE, font: "Arial" })] })] }),
            new TableCell({ borders: allBorders(NAVY), width: { size: 2400, type: WidthType.DXA }, shading: { fill: NAVY, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: "Repository", bold: true, size: 20, color: WHITE, font: "Arial" })] })] }),
          ]}),
          ...[
            ["RuFlo v3.5",       "The open source agent orchestration framework used to coordinate all six agents. Designed for Claude and multi-agent pipelines.",                           "github.com/ruvnet/ruflo"],
            ["PostgreSQL",       "The care-record database that stores resident data and powers the VerificationAgent. Already used in the current system \u2014 no change needed.",           "postgresql.org (free, open source)"],
          ].map(([tool, purpose, repo], i) =>
            new TableRow({ children: [
              new TableCell({ borders: allBorders("BBCCDD"), width: { size: 2400, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHT : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: tool, bold: true, size: 20, color: DARK, font: "Arial" })] })] }),
              new TableCell({ borders: allBorders("BBCCDD"), width: { size: 4560, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHT : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, children: [new Paragraph({ children: [new TextRun({ text: purpose, size: 20, color: BODY, font: "Arial" })] })] }),
              new TableCell({ borders: allBorders("BBCCDD"), width: { size: 2400, type: WidthType.DXA }, shading: { fill: i % 2 === 0 ? LIGHT : WHITE, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, children: [new Paragraph({ children: [new ExternalHyperlink({ link: "https://" + repo.split(" ")[0], children: [new TextRun({ text: repo, size: 20, color: TEAL, underline: {}, font: "Arial" })] })] })] }),
            ]})
          )
        ]
      }),

      ...spacer(2),

      // ══════════════════════════════════════════════════════════════════════
      // CLOSING NOTE
      // ══════════════════════════════════════════════════════════════════════
      divider(NAVY),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 160, after: 160 },
        children: [new TextRun({ text: "This document was prepared for internal use by the CascadeAI founding team.", size: 20, italic: true, color: "888888", font: "Arial" })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 160 },
        children: [new TextRun({ text: "April 2026  |  Not for distribution", size: 20, italic: true, color: "888888", font: "Arial" })]
      }),
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("CascadeAI_OpenSource_Rebuild_April2026.docx", buffer);
  console.log("Document written successfully.");
}).catch(err => {
  console.error("Error:", err);
  process.exit(1);
});
