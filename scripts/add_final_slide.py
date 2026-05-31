"""Add 'Honest Take' slide before the 'Get Started' slide."""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from pptx import Presentation
from pptx.util import Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

PPTX_PATH = r'C:\Users\528875\Distill_Token_Optimization.pptx'
prs = Presentation(PPTX_PATH)
print(f"Loaded: {len(prs.slides)} slides")


def make_textbox(slide, left, top, width, height, text, sz, bold, color, align="l"):
    box = slide.shapes.add_textbox(Emu(left), Emu(top), Emu(width), Emu(height))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    al = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER}
    p.alignment = al.get(align, PP_ALIGN.LEFT)
    run = p.add_run()
    run.text = text
    run.font.size = Emu(sz * 12700)
    run.font.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)
    run.font.name = "Segoe UI"
    return box


def make_card(slide, left, top, width, height, fill):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Emu(left), Emu(top), Emu(width), Emu(height))
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor.from_string(fill)
    shape.line.fill.background()
    shape.adjustments[0] = 0.04
    return shape


def make_icon_rect(slide, left, top, size, fill, label):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Emu(left), Emu(top), Emu(size), Emu(size))
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor.from_string(fill)
    shape.line.fill.background()
    shape.adjustments[0] = 0.15
    tf = shape.text_frame
    tf.word_wrap = False
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = label
    run.font.size = Emu(18 * 12700)
    run.font.bold = True
    run.font.color.rgb = RGBColor.from_string("FFFFFF")
    run.font.name = "Segoe UI"
    return shape


# --- Create slide ---

blank_layout = None
for layout in prs.slide_layouts:
    if layout.name == "Blank":
        blank_layout = layout
        break
if not blank_layout:
    blank_layout = prs.slide_layouts[6]

slide = prs.slides.add_slide(blank_layout)

# Background
slide.background.fill.solid()
slide.background.fill.fore_color.rgb = RGBColor(0x0F, 0x17, 0x2A)

# Top accent bar
bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Emu(12192000), Emu(54864))
bar.fill.solid()
bar.fill.fore_color.rgb = RGBColor.from_string("00D4AA")
bar.line.fill.background()

# Title
make_textbox(slide, 731520, 365760, 10728960, 640080,
             "Our Recommendation", 36, True, "FFFFFF")

make_textbox(slide, 731520, 960120, 10728960, 365760,
             "Where Distill delivers real value and where to set expectations.",
             16, False, "94A3B8")

# --- High Value column ---
make_textbox(slide, 731520, 1554480, 5303520, 365760,
             "High Value  -  Adopt Now", 22, True, "00D4AA")

high_items = [
    (".llmignore files",
     "Biggest win. Just stop sending junk to the LLM."),
    ("CI budget gate",
     "Prevents bloat from landing. Low effort to maintain."),
    ("One-time repo scans",
     "Know your token footprint. Data drives decisions."),
]

card_w = 5120640
card_h = 548640
card_x = 731520
gap = 137160
y = 1965960

for title, desc in high_items:
    make_card(slide, card_x, y, card_w, card_h, "16213E")
    make_icon_rect(slide, card_x + 137160, y + 131064, 285750, "00D4AA", "+")
    make_textbox(slide, card_x + 514350, y + 91440, card_w - 605790, 228600,
                 title, 16, True, "FFFFFF")
    make_textbox(slide, card_x + 514350, y + 320040, card_w - 605790, 228600,
                 desc, 13, False, "94A3B8")
    y += card_h + gap

# --- Set Expectations column ---
sec2_x = 6309360

make_textbox(slide, sec2_x, 1554480, 5303520, 365760,
             "Set Expectations", 22, True, "FFA500")

expect_items = [
    ("Savings are directional",
     "Real savings will be lower than upper-bound estimates."),
    ("Adapters need custom tooling",
     "Python wrappers help if you build LLM tools, not for daily coding."),
    ("Lead with quality, not cost",
     "Better LLM responses matter more than dollars saved."),
]

y = 1965960
for title, desc in expect_items:
    make_card(slide, sec2_x, y, card_w, card_h, "16213E")
    make_icon_rect(slide, sec2_x + 137160, y + 131064, 285750, "FFA500", "!")
    make_textbox(slide, sec2_x + 514350, y + 91440, card_w - 605790, 228600,
                 title, 16, True, "FFFFFF")
    make_textbox(slide, sec2_x + 514350, y + 320040, card_w - 605790, 228600,
                 desc, 13, False, "94A3B8")
    y += card_h + gap

# Bottom line
make_textbox(slide, 731520, 5943600, 10728960, 365760,
             "Position as hygiene and visibility tooling. The ignore files and CI gate are the lasting value.",
             14, False, "58A6FF")

# --- Move to position 7 (before "Get Started" which is currently last) ---
sldIdLst = prs.element.sldIdLst
sldIds = list(sldIdLst)
new_sldId = sldIds[-1]  # our new slide (appended at end)
last_original = sldIds[-2]  # "Get Started" slide
sldIdLst.remove(new_sldId)
# Insert before "Get Started"
last_original.addprevious(new_sldId)

# --- Verify ---
print("\nFinal order:")
for i, s in enumerate(prs.slides):
    txt = ""
    for sh in s.shapes:
        if sh.has_text_frame:
            for p in sh.text_frame.paragraphs:
                t = p.text.strip()
                if t and len(t) > 10:
                    txt = t[:60]
                    break
        if txt:
            break
    print(f"  Slide {i+1}: {txt}")

prs.save(PPTX_PATH)
print(f"\nSaved. {len(prs.slides)} slides.")
