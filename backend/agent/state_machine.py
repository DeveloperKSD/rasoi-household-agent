START = "START"
UNDERSTAND = "UNDERSTAND_HOUSEHOLD"
INVENTORY = "CHECK_INVENTORY"
SELECT_MEAL = "SELECT_MEAL"
MISSING = "CHECK_MISSING_INGREDIENTS"
BUDGET = "CHECK_BUDGET"
CREATE_ORDER = "CREATE_ORDER"
PAYMENT = "PAYMENT"
PAYMENT_PENDING = "PAYMENT_PENDING"
VERIFY_PAYMENT = "VERIFY_PAYMENT"
DELIVERY = "DELIVERY"
VERIFY_DELIVERY = "VERIFY_DELIVERY"
UPDATE_INVENTORY = "UPDATE_INVENTORY"
LEARN = "LEARN"
COMPLETE = "COMPLETE"

# states where Rasoi stops and a human must act
NEEDS_HUMAN = "NEEDS_HUMAN"
PAYMENT_FAILED = "PAYMENT_FAILED"
DELIVERY_FAILED = "DELIVERY_FAILED"
CONSTRAINT_CONFLICT = "CONSTRAINT_CONFLICT"
STALE_INVENTORY = "STALE_INVENTORY"
BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
UNRESOLVED = "UNRESOLVED"
CANCELLED = "CANCELLED"

HUMAN_STATES = {NEEDS_HUMAN, PAYMENT_FAILED, DELIVERY_FAILED, CONSTRAINT_CONFLICT,
                STALE_INVENTORY, BUDGET_EXCEEDED, UNRESOLVED}
STOP_STATES = HUMAN_STATES | {COMPLETE, CANCELLED}

PIPELINE = [
    {"id": "understand", "label": "Understand household", "states": [START, UNDERSTAND]},
    {"id": "inventory", "label": "Check pantry", "states": [INVENTORY, STALE_INVENTORY]},
    {"id": "meal", "label": "Select meal", "states": [SELECT_MEAL, CONSTRAINT_CONFLICT]},
    {"id": "shopping", "label": "Build shopping list", "states": [MISSING]},
    {"id": "budget", "label": "Check budget", "states": [BUDGET, BUDGET_EXCEEDED]},
    {"id": "payment", "label": "Payment", "states": [CREATE_ORDER, PAYMENT, PAYMENT_PENDING, VERIFY_PAYMENT, PAYMENT_FAILED, UNRESOLVED]},
    {"id": "delivery", "label": "Delivery", "states": [DELIVERY, VERIFY_DELIVERY, DELIVERY_FAILED]},
    {"id": "inventory_update", "label": "Update pantry", "states": [UPDATE_INVENTORY]},
    {"id": "learn", "label": "Learn", "states": [LEARN, COMPLETE]},
]


def step_index(state):
    for i, s in enumerate(PIPELINE):
        if state in s["states"]:
            return i
    return len(PIPELINE)
