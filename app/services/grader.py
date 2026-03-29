def calculate_grade(battery_health, cycle_count, manual_checks, auto_checks):
    """
    Calculate QC grade for a MacBook.

    manual_checks: dict of {check_name: "pass"|"fail"|"skip"}
    auto_checks: dict of auto-diagnostic results from agent.py

    Grade ladder:
      CAP1 - Cosmetic A, all pass, battery 90%+, <200 cycles
      CAP  - Cosmetic A, all pass, battery 85%+
      CA+  - Cosmetic A, all pass, battery 80%+
      CA   - Cosmetic A, 1-2 minor warns
      CAB  - Cosmetic A, battery <80%
      SD   - Cosmetic B, all functional pass
      SD-  - Cosmetic B, 1-2 minor warns
      SDB  - Cosmetic B, battery <80%
      XF   - Functional fail (SMART, 4+ failures)
      XC   - Cosmetic fail (cracked screen, damaged body)
    """
    fail_reasons = []

    # -- Critical auto-check failures --
    smart_status = auto_checks.get("smart_status", "").lower()
    if smart_status and smart_status not in ("verified", "ok", "passed"):
        return "XF", "SMART Failure — Do Not Sell", ["SMART status: " + auto_checks.get("smart_status", "Unknown")]

    # -- Cosmetic grading --
    screen_cosmetic = manual_checks.get("screen_condition", "A").upper()
    body_cosmetic = manual_checks.get("body_condition", "A").upper()
    overall_cosmetic = manual_checks.get("overall_cosmetic_grade", "A").upper()

    if screen_cosmetic == "CRACKED":
        return "XC", "Cracked Screen — Cosmetic Fail", ["Screen is cracked"]
    if body_cosmetic == "DAMAGED":
        return "XC", "Damaged Body — Cosmetic Fail", ["Body is damaged"]

    # Determine cosmetic tier
    cosmetic_tier = "A"
    if "C" in (screen_cosmetic, body_cosmetic, overall_cosmetic):
        cosmetic_tier = "C"
    elif "B" in (screen_cosmetic, body_cosmetic, overall_cosmetic):
        cosmetic_tier = "B"

    # -- Count functional failures (non-cosmetic manual checks) --
    cosmetic_keys = {"screen_condition", "body_condition", "overall_cosmetic_grade"}
    functional_fails = 0
    for check_name, result in manual_checks.items():
        if check_name in cosmetic_keys:
            continue
        if result == "fail":
            functional_fails += 1
            fail_reasons.append(f"Manual check failed: {check_name}")

    if functional_fails >= 4:
        return "XF", "Multiple Functional Failures", fail_reasons

    # -- Battery evaluation --
    bat = battery_health if battery_health is not None else 100
    cycles = cycle_count if cycle_count is not None else 0
    low_battery = bat < 80

    if low_battery:
        fail_reasons.append(f"Battery health {bat}% (below 80%)")

    # -- Grade matrix --
    if cosmetic_tier == "A":
        if low_battery:
            grade, desc = "CAB", "Cosmetic A — Low Battery"
        elif functional_fails == 0:
            if bat >= 90 and cycles < 200:
                grade, desc = "CAP1", "Premium — Like New"
            elif bat >= 85:
                grade, desc = "CAP", "Cosmetic A — Excellent"
            elif bat >= 80:
                grade, desc = "CA+", "Cosmetic A — Very Good"
            else:
                grade, desc = "CA", "Cosmetic A — Good"
        else:
            grade, desc = "CA", "Cosmetic A — Minor Issues"
    elif cosmetic_tier == "B":
        if low_battery:
            grade, desc = "SDB", "Cosmetic B — Low Battery"
        elif functional_fails == 0:
            grade, desc = "SD", "Cosmetic B — Functional Pass"
        else:
            grade, desc = "SD-", "Cosmetic B — Minor Issues"
    else:
        # C cosmetic
        if low_battery:
            grade, desc = "SDB", "Cosmetic C — Low Battery"
        elif functional_fails == 0:
            grade, desc = "SD-", "Cosmetic C — Functional Pass"
        else:
            grade, desc = "XF", "Cosmetic C — Multiple Issues"
            if not fail_reasons:
                fail_reasons.append("Low cosmetic grade with functional issues")

    return grade, desc, fail_reasons
