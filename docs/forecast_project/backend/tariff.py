def calc_bill_jod(kwh: float) -> float:
    if kwh <= 0:
        return 0.0
    if kwh <= 85:
        return 1.75

    cost = 0.0
    rem = float(kwh)
    for cap, rate in [(300, 50), (300, 100), (float("inf"), 200)]:
        used = min(rem, cap)
        cost += used * rate
        rem -= used
        if rem <= 0:
            break

    return round(cost / 1000, 3)


def get_tier(kwh: float) -> str:
    if kwh <= 300:
        return "T1 (0-300)"
    if kwh <= 600:
        return "T2 (301-600)"
    return "T3 (>600)"
