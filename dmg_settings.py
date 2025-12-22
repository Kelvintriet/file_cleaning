import os.path

# Basics
filename = "SystemCleaner.dmg"
volume_name = "System Cleaner"
format = "UDBZ"
size = None
files = [ "dist/SystemCleaner.app" ]
symlinks = { "Applications": "/Applications" }
badge_icon = "dist/SystemCleaner.app/Contents/Resources/icon-windowed.icns"

# View
icon_locations = {
    "SystemCleaner.app": (140, 120),
    "Applications": (500, 120)
}
window_rect = ((100, 100), (640, 280))
background = "builtin-arrow"
default_view = "icon-view"
text_size = 14
icon_size = 128
