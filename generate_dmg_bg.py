from PIL import Image, ImageDraw, ImageFont
import os

def create_background():
    # Create a 800x400 image (standard DMG size)
    # Color: Light Blue-ish background
    img = Image.new('RGB', (800, 400), color='#F0F5FF')
    draw = ImageDraw.Draw(img)
    
    # Draw an arrow pointing from App (left) to Applications (right)
    # App pos: ~200, 190
    # Apps pos: ~600, 185
    
    arrow_color = '#3B82F6' # Blue
    
    # Draw Arrow Line
    draw.line([(280, 240), (520, 240)], fill=arrow_color, width=5)
    
    # Draw Arrow Head
    draw.polygon([(520, 225), (520, 255), (550, 240)], fill=arrow_color)
    
    # Add Text
    try:
        # Try to use a system font
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
    except:
        font = None # Default font
        
    text = "Drag System Cleaner to Applications"
    
    # Calculate text position (centered horizontally)
    if font:
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        draw.text(((800 - w) / 2, 300), text, font=font, fill='#1E40AF')
    else:
        draw.text((300, 300), text, fill='#1E40AF')

    # Save
    if not os.path.exists("web"):
        os.makedirs("web")
    img.save("web/dmg_background.png")
    print("Background image created at web/dmg_background.png")

if __name__ == "__main__":
    create_background()
