from PIL import Image, ImageDraw, ImageFont
import os
import sys
import shutil

def create_default_logo():
    # Create a 512x512 logo
    img = Image.new('RGBA', (512, 512), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw Circle Background (Blue Gradient-ish)
    draw.ellipse([(20, 20), (492, 492)], fill='#007AFF')
    
    # Draw Broom/Clean Icon (Simple representation)
    # Handle (White)
    draw.rectangle([(230, 100), (282, 300)], fill='white')
    # Bristles
    draw.pieslice([(156, 250), (356, 450)], 0, 180, fill='white')
    
    # Save as source png
    if not os.path.exists("web"):
        os.makedirs("web")
    img.save("web/logo.png")
    print("Default logo created at web/logo.png")
    return "web/logo.png"

def generate_icons(source_png):
    if not os.path.exists(source_png):
        print(f"Error: {source_png} not found.")
        return

    img = Image.open(source_png)
    
    # Generate .ico for Windows
    # Includes multiple sizes
    icon_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save("icon.ico", format='ICO', sizes=icon_sizes)
    print("Generated icon.ico")

    # Generate .icns for Mac
    # For CI/CD environments without mac-specific tools, we can try using a simple directory structure
    # or rely on an external tool. But PyInstaller on Mac often prefers .icns
    # Since we can't easily create .icns with just PIL, we will rely on 'iconutil' if on Mac, 
    # or just use the png if PyInstaller accepts it (it often warns but works), 
    # OR we can try to save as .icns if PIL supports it (depends on plugins).
    
    # Best bet for cross-platform generation without iconutil:
    # Just save the png as icon.icns (This is a hack, might not work).
    # Real solution: Create an iconset folder and run iconutil (macOS only).
    
    if sys.platform == 'darwin':
        try:
            iconset_path = "SystemCleaner.iconset"
            if os.path.exists(iconset_path):
                shutil.rmtree(iconset_path)
            os.makedirs(iconset_path)
            
            # Create required sizes
            sizes = [16, 32, 64, 128, 256, 512]
            for size in sizes:
                resized = img.resize((size, size), Image.Resampling.LANCZOS)
                resized.save(f"{iconset_path}/icon_{size}x{size}.png")
                resized = img.resize((size*2, size*2), Image.Resampling.LANCZOS)
                resized.save(f"{iconset_path}/icon_{size}x{size}@2x.png")
                
            os.system(f"iconutil -c icns {iconset_path} -o icon.icns")
            print("Generated icon.icns using iconutil")
            shutil.rmtree(iconset_path)
        except Exception as e:
            print(f"Failed to create .icns: {e}")
    else:
        # On Linux/Windows builders, we might not have iconutil.
        # But for the Mac build job, we are on 'macos-latest', so it has iconutil!
        print("Not on macOS, skipping .icns generation (will rely on CI to do it)")

if __name__ == "__main__":
    # If user provided a path arg, use it
    if len(sys.argv) > 1:
        source = sys.argv[1]
    else:
        source = "web/logo.png"
        if not os.path.exists(source):
            create_default_logo()
            
    generate_icons(source)
