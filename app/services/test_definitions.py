from app import db
from app.models.test_definition import TestDefinition

DEFAULTS = [
    # ── MacBook: Hardware ──
    ("Battery Health", "hardware", "macbook", 1, "System Settings > Battery. Pass if condition is Normal and health > 80%."),
    ("Display", "hardware", "macbook", 2, "Check for dead pixels, backlight bleed. Open solid color fullscreen images."),
    ("Keyboard", "hardware", "macbook", 3, "Test every key. Open TextEdit and type full keyboard layout."),
    ("Trackpad", "hardware", "macbook", 4, "Test click, force click, gestures (scroll, zoom, swipe)."),
    ("Speakers", "hardware", "macbook", 5, "Play audio. Check left and right channels, no distortion."),
    ("Microphone", "hardware", "macbook", 6, "Open Voice Memos, record and playback."),
    ("FaceTime Camera", "hardware", "macbook", 7, "Open FaceTime or Photo Booth. Check image quality."),
    # ── MacBook: Connectivity ──
    ("WiFi", "connectivity", "macbook", 8, "Connect to test network. Verify internet access."),
    ("Bluetooth", "connectivity", "macbook", 9, "Pair a test device (mouse or keyboard)."),
    ("USB-C Ports", "connectivity", "macbook", 10, "Test each port with a USB-C device or hub."),
    ("Thunderbolt", "connectivity", "macbook", 11, "Connect external display or Thunderbolt device."),
    ("MagSafe / Charging", "connectivity", "macbook", 12, "Plug in charger. Verify charging indicator."),
    # ── MacBook: Cosmetic ──
    ("Screen Condition", "cosmetic", "macbook", 13, "Inspect for scratches, cracks, coating wear."),
    ("Top Case", "cosmetic", "macbook", 14, "Check palm rest, keyboard area for dents or wear."),
    ("Bottom Case", "cosmetic", "macbook", 15, "Inspect for dents, scratches, missing screws."),
    ("Hinge", "cosmetic", "macbook", 16, "Open and close lid. Should be smooth, hold position."),

    # ── iPhone: Hardware ──
    ("Battery Health", "hardware", "iphone", 1, "Settings > Battery > Battery Health. Pass if > 80%."),
    ("Display", "hardware", "iphone", 2, "Check touch response, dead pixels. Test all screen areas."),
    ("Face ID / Touch ID", "hardware", "iphone", 3, "Enroll and test biometric unlock."),
    ("Speakers", "hardware", "iphone", 4, "Play audio. Test earpiece and bottom speaker."),
    ("Microphone", "hardware", "iphone", 5, "Record voice memo, play back."),
    ("Front Camera", "hardware", "iphone", 6, "Open Camera app, test front-facing camera and portrait mode."),
    ("Rear Camera", "hardware", "iphone", 7, "Test all rear lenses, zoom, flash."),
    # ── iPhone: Connectivity ──
    ("WiFi", "connectivity", "iphone", 8, "Connect to test network. Verify internet access."),
    ("Bluetooth", "connectivity", "iphone", 9, "Pair a test device (AirPods or speaker)."),
    ("Cellular", "connectivity", "iphone", 10, "Insert test SIM. Check signal and data."),
    ("Lightning / USB-C Port", "connectivity", "iphone", 11, "Test charging and data connection."),
    ("Wireless Charging", "connectivity", "iphone", 12, "Place on Qi charger. Verify charging indicator."),
    # ── iPhone: Cosmetic ──
    ("Screen Condition", "cosmetic", "iphone", 13, "Inspect for scratches, cracks."),
    ("Back Glass", "cosmetic", "iphone", 14, "Check for cracks, scratches, discoloration."),
    ("Frame Condition", "cosmetic", "iphone", 15, "Inspect edges for dents, chips."),
    ("Buttons", "cosmetic", "iphone", 16, "Test volume, power, mute switch. All should click."),

    # ── iPad: Hardware ──
    ("Battery Health", "hardware", "ipad", 1, "Check battery in Settings or coconutBattery. Pass if > 80%."),
    ("Display", "hardware", "ipad", 2, "Check touch response across full screen, dead pixels."),
    ("Face ID / Touch ID", "hardware", "ipad", 3, "Enroll and test biometric unlock."),
    ("Speakers", "hardware", "ipad", 4, "Play audio. Test all speaker grilles."),
    ("Microphone", "hardware", "ipad", 5, "Record voice memo, play back."),
    ("Front Camera", "hardware", "ipad", 6, "Test front camera in FaceTime or Camera app."),
    ("Rear Camera", "hardware", "ipad", 7, "Test rear camera, flash if present."),
    # ── iPad: Connectivity ──
    ("WiFi", "connectivity", "ipad", 8, "Connect to test network. Verify internet access."),
    ("Bluetooth", "connectivity", "ipad", 9, "Pair a test device."),
    ("Lightning / USB-C Port", "connectivity", "ipad", 10, "Test charging and data connection."),
    ("Apple Pencil", "connectivity", "ipad", 11, "Pair and test Apple Pencil if supported."),
    # ── iPad: Cosmetic ──
    ("Screen Condition", "cosmetic", "ipad", 12, "Inspect for scratches, cracks."),
    ("Back Panel", "cosmetic", "ipad", 13, "Check for dents, scratches."),
    ("Frame Condition", "cosmetic", "ipad", 14, "Inspect edges for dents, chips."),
    ("Buttons", "cosmetic", "ipad", 15, "Test volume, power buttons. All should click."),
]


def seed_defaults():
    existing = {
        (t.test_name, t.device_type)
        for t in TestDefinition.query.all()
    }
    for name, category, device_type, order, instructions in DEFAULTS:
        if (name, device_type) not in existing:
            db.session.add(TestDefinition(
                test_name=name,
                test_category=category,
                device_type=device_type,
                display_order=order,
                instructions=instructions,
            ))
    db.session.commit()
