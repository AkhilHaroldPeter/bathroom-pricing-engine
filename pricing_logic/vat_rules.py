
# Simplified French VAT assumptions (not tax advice):
# - Renovation in residential buildings often eligible for 10% VAT (mainland FR).
# - Some fixtures/sanitary goods can fall under 20% if supplied separately.
# We'll model per-task VAT conservatively.

def vat_for_task(task: str, context: dict | None = None) -> float:
    task = (task or "").lower()
    # default renovation VAT
    vat = 0.10
    if any(k in task for k in ["toilet", "vanity", "plumbing"]):
        # sanitary goods & plumbing commonly at standard rate in many cases
        vat = 0.20
    return vat
