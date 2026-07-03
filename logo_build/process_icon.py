from PIL import Image
from rembg import remove
import io
import base64

# Load image
img_path = '/Users/aryansubhash/.gemini/antigravity/brain/23116d17-c1eb-4eca-a179-e3719b7ea66e/cascade_logo_refined_1772914940752.png'
base_img = Image.open(img_path)

# Crop the top part to isolate the icon and remove text (y=0 to 700 usually covers it)
# We can find the exact bounding box later, but a generous crop works.
width, height = base_img.size
cropped = base_img.crop((0, 0, width, height - 280))

# Remove background
transparent = remove(cropped)

# Get bounding box of non-transparent part
bbox = transparent.getbbox()
if bbox:
    icon_final = transparent.crop(bbox)
else:
    icon_final = transparent

# Save high-res icon PNG
icon_final.save('cascade-logo-icon.png')

# Save resized versions using high-quality Lanczos resampling
icon_final.resize((512, 512), Image.Resampling.LANCZOS).save('cascade-logo-icon-512.png')
icon_final.resize((32, 32), Image.Resampling.LANCZOS).save('cascade-logo-favicon-32.png')

# Create Base64 for embedding in SVGs
buffered = io.BytesIO()
icon_final.save(buffered, format="PNG")
img_str = base64.b64encode(buffered.getvalue()).decode()

# --- ICON SVG ---
# We create a simple SVG wrapping the exact image
icon_width, icon_height = icon_final.size
icon_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {width}" width="{width}" height="{width}">
    <image href="data:image/png;base64,{img_str}" x="{(width-icon_width)/2}" y="{(width-icon_height)/2}" width="{icon_width}" height="{icon_height}"/>
</svg>"""
with open('cascade-logo-icon.svg', 'w') as f:
    f.write(icon_svg)

# --- FULL LOGO SVG ---
# Combine image + exact typography requested
full_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" width="1024" height="1024">
    <style>
        .logo-text {{ font-family: 'Inter', 'Poppins', sans-serif; font-weight: 600; font-size: 110px; fill: #3D4F2F; }}
        .tagline {{ font-family: 'Inter', 'Poppins', sans-serif; font-weight: 500; font-size: 28px; fill: #5A6D4B; letter-spacing: 4px; }}
    </style>
    <image href="data:image/png;base64,{img_str}" x="{(1024-icon_width)/2}" y="120" width="{icon_width}" height="{icon_height}"/>
    
    <!-- Text Elements -->
    <text x="512" y="{min(120 + icon_height + 120, 800)}" text-anchor="middle" class="logo-text">CascadeAI</text>
    <text x="512" y="{min(120 + icon_height + 120, 800) + 60}" text-anchor="middle" class="tagline">INTELLIGENT HEALTHCARE ASSISTANT</text>
</svg>
"""
with open('cascade-logo-full.svg', 'w') as f:
    f.write(full_svg)

print("Icons processed and SVGs generated.")
