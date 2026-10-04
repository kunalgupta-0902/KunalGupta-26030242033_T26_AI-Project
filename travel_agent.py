import pandas as pd
import numpy as np

# ============================================================
# CONFIGURATION
# ============================================================

INPUT_FILE = "T26_Travel_policy_compliance_assistant.xlsx"

DECISION_FILE = "150_Travel_Requests_Decisions.csv"
AUDIT_FILE = "30_Requests_Audit.csv"
VIOLATION_FILE = "Most_Common_Violations.csv"
RULE_SUMMARY_FILE = "Rule_Evaluation_Summary.csv"

# IMPORTANT:
# Metro-city classification is not explicitly provided as a
# separate field in the Travel Requests sheet.
#
# These are treated as metro cities for TP-04.
METRO_CITIES = {
    "Mumbai",
    "Delhi",
    "Bengaluru",
    "Chennai"
}


# ============================================================
# LOAD EXCEL
# ============================================================

requests_df = pd.read_excel(
    INPUT_FILE,
    sheet_name="Travel Requests"
)

rules_df = pd.read_excel(
    INPUT_FILE,
    sheet_name="Policy Rules"
)

print("=" * 70)
print("TRAVEL POLICY COMPLIANCE ASSISTANT")
print("=" * 70)

print(f"Travel Requests loaded : {len(requests_df)}")
print(f"Policy Rules loaded    : {len(rules_df)}")


# ============================================================
# CLEAN DATA
# ============================================================

requests_df["request_date"] = pd.to_datetime(
    requests_df["request_date"],
    errors="coerce"
)

requests_df["departure_date"] = pd.to_datetime(
    requests_df["departure_date"],
    errors="coerce"
)

requests_df["hotel_rate_per_night_inr"] = pd.to_numeric(
    requests_df["hotel_rate_per_night_inr"],
    errors="coerce"
)

requests_df["estimated_total_cost_inr"] = pd.to_numeric(
    requests_df["estimated_total_cost_inr"],
    errors="coerce"
)

requests_df["flight_duration_hours"] = pd.to_numeric(
    requests_df["flight_duration_hours"],
    errors="coerce"
)

# Text cleanup
for col in [
    "grade",
    "destination",
    "trip_type",
    "travel_mode",
    "purpose"
]:
    requests_df[col] = (
        requests_df[col]
        .fillna("")
        .astype(str)
        .str.strip()
    )


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def grade_number(grade):
    """
    Converts:
    M1 -> 1
    M2 -> 2
    ...
    M5 -> 5
    """
    try:
        return int(str(grade).upper().replace("M", "").strip())
    except:
        return None


def is_m1_to_m3(grade):
    g = grade_number(grade)
    return g is not None and 1 <= g <= 3


def is_m4_or_above(grade):
    g = grade_number(grade)
    return g is not None and g >= 4


def is_metro(destination):
    return destination.strip() in METRO_CITIES


def is_personal_extension(purpose):
    text = purpose.lower()

    keywords = [
        "personal",
        "personal day",
        "personal days",
        "family"
    ]

    return any(keyword in text for keyword in keywords)


# ============================================================
# RULE ENGINE
# ============================================================

def evaluate_request(row):

    results = []

    grade = row["grade"]
    destination = row["destination"]
    trip_type = row["trip_type"]
    travel_mode = row["travel_mode"]
    purpose = row["purpose"]

    request_date = row["request_date"]
    departure_date = row["departure_date"]

    flight_hours = row["flight_duration_hours"]
    hotel_rate = row["hotel_rate_per_night_inr"]
    total_cost = row["estimated_total_cost_inr"]


    # ========================================================
    # TP-01
    # AIR TRAVEL
    # ========================================================

    if travel_mode.startswith("Flight"):

        if "Economy" in travel_mode:
            flight_class = "Economy"
        elif "Business" in travel_mode:
            flight_class = "Business"
        else:
            flight_class = None

        if flight_class is None or pd.isna(flight_hours):

            results.append({
                "rule_id": "TP-01",
                "status": "NOT TESTABLE",
                "reason": "Flight class or flight duration unavailable."
            })

        elif flight_hours < 4:

            if flight_class == "Economy":

                results.append({
                    "rule_id": "TP-01",
                    "status": "COMPLIANT",
                    "reason": (
                        "Economy class used for flight under 4 hours."
                    )
                })

            else:

                results.append({
                    "rule_id": "TP-01",
                    "status": "VIOLATION",
                    "reason": (
                        f"Business class used for {flight_hours} hour flight. "
                        "Economy is required for flights under 4 hours."
                    )
                })

        else:

            if flight_class == "Economy":

                results.append({
                    "rule_id": "TP-01",
                    "status": "COMPLIANT",
                    "reason": "Economy class used."
                })

            elif flight_class == "Business" and is_m4_or_above(grade):

                results.append({
                    "rule_id": "TP-01",
                    "status": "COMPLIANT",
                    "reason": (
                        f"Grade {grade} is M4 or above and "
                        "business class is permitted for flights over 4 hours."
                    )
                })

            else:

                results.append({
                    "rule_id": "TP-01",
                    "status": "VIOLATION",
                    "reason": (
                        f"Grade {grade} is below M4 but business class "
                        "was used for a flight over 4 hours."
                    )
                })

    else:

        results.append({
            "rule_id": "TP-01",
            "status": "NOT APPLICABLE",
            "reason": "Not an air-travel request."
        })


    # ========================================================
    # TP-02
    # ADVANCE BOOKING
    # ========================================================

    if travel_mode.startswith("Flight"):

        if pd.isna(request_date) or pd.isna(departure_date):

            results.append({
                "rule_id": "TP-02",
                "status": "NOT TESTABLE",
                "reason": "Request/departure date unavailable."
            })

        else:

            advance_days = (
                departure_date - request_date
            ).days

            if advance_days >= 7:

                results.append({
                    "rule_id": "TP-02",
                    "status": "COMPLIANT",
                    "reason": (
                        f"Flight booked {advance_days} days before departure."
                    )
                })

            else:

                results.append({
                    "rule_id": "TP-02",
                    "status": "NEEDS APPROVAL",
                    "reason": (
                        f"Flight booked only {advance_days} days in advance. "
                        "Written department-head justification is required."
                    )
                })

    else:

        results.append({
            "rule_id": "TP-02",
            "status": "NOT APPLICABLE",
            "reason": "Not a flight booking."
        })


    # ========================================================
    # TP-03
    # TRAIN TRAVEL
    # ========================================================

    if travel_mode.startswith("Train"):

        if is_m1_to_m3(grade):

            if "AC 2 tier" in travel_mode:

                results.append({
                    "rule_id": "TP-03",
                    "status": "COMPLIANT",
                    "reason": (
                        f"Grade {grade} is using AC 2-tier as required."
                    )
                })

            else:

                results.append({
                    "rule_id": "TP-03",
                    "status": "VIOLATION",
                    "reason": (
                        f"Grade {grade} must use AC 2-tier."
                    )
                })

        elif is_m4_or_above(grade):

            if "AC 1st" in travel_mode:

                results.append({
                    "rule_id": "TP-03",
                    "status": "COMPLIANT",
                    "reason": (
                        f"Grade {grade} is using AC 1st class as required."
                    )
                })

            else:

                results.append({
                    "rule_id": "TP-03",
                    "status": "VIOLATION",
                    "reason": (
                        f"Grade {grade} must use AC 1st class."
                    )
                })

        else:

            results.append({
                "rule_id": "TP-03",
                "status": "NOT TESTABLE",
                "reason": "Employee grade could not be determined."
            })

    else:

        results.append({
            "rule_id": "TP-03",
            "status": "NOT APPLICABLE",
            "reason": "Not a train request."
        })


    # ========================================================
    # TP-04
    # HOTEL LIMIT - METRO
    # ========================================================

    if is_metro(destination):

        if pd.isna(hotel_rate):

            results.append({
                "rule_id": "TP-04",
                "status": "NOT TESTABLE",
                "reason": "Hotel rate unavailable."
            })

        else:

            g = grade_number(grade)

            if g in [1, 2]:
                limit = 7000
            elif g == 3:
                limit = 10000
            elif g >= 4:
                limit = 14000
            else:
                limit = None

            if limit is None:

                results.append({
                    "rule_id": "TP-04",
                    "status": "NOT TESTABLE",
                    "reason": "Grade could not be determined."
                })

            elif hotel_rate <= limit:

                results.append({
                    "rule_id": "TP-04",
                    "status": "COMPLIANT",
                    "reason": (
                        f"Hotel rate ₹{hotel_rate:,.0f} is within "
                        f"₹{limit:,.0f} metro limit."
                    )
                })

            else:

                results.append({
                    "rule_id": "TP-04",
                    "status": "VIOLATION",
                    "reason": (
                        f"Hotel rate ₹{hotel_rate:,.0f} exceeds "
                        f"₹{limit:,.0f} metro limit."
                    )
                })

    else:

        results.append({
            "rule_id": "TP-04",
            "status": "NOT APPLICABLE",
            "reason": "Destination classified as non-metro."
        })


    # ========================================================
    # TP-05
    # HOTEL LIMIT - NON-METRO
    # ========================================================

    if not is_metro(destination):

        if pd.isna(hotel_rate):

            results.append({
                "rule_id": "TP-05",
                "status": "NOT TESTABLE",
                "reason": "Hotel rate unavailable."
            })

        else:

            g = grade_number(grade)

            if g in [1, 2]:
                limit = 4500
            elif g == 3:
                limit = 6500
            elif g >= 4:
                limit = 9000
            else:
                limit = None

            if limit is None:

                results.append({
                    "rule_id": "TP-05",
                    "status": "NOT TESTABLE",
                    "reason": "Grade could not be determined."
                })

            elif hotel_rate <= limit:

                results.append({
                    "rule_id": "TP-05",
                    "status": "COMPLIANT",
                    "reason": (
                        f"Hotel rate ₹{hotel_rate:,.0f} is within "
                        f"₹{limit:,.0f} non-metro limit."
                    )
                })

            else:

                results.append({
                    "rule_id": "TP-05",
                    "status": "VIOLATION",
                    "reason": (
                        f"Hotel rate ₹{hotel_rate:,.0f} exceeds "
                        f"₹{limit:,.0f} non-metro limit."
                    )
                })

    else:

        results.append({
            "rule_id": "TP-05",
            "status": "NOT APPLICABLE",
            "reason": "Destination classified as metro."
        })


    # ========================================================
    # TP-06
    # DAILY ALLOWANCE
    # ========================================================

    results.append({
        "rule_id": "TP-06",
        "status": "NOT TESTABLE",
        "reason": (
            "The Travel Requests sheet has no daily allowance/meal/"
            "incidentals expense column."
        )
    })


    # ========================================================
    # TP-07
    # LOCAL CONVEYANCE
    # ========================================================

    results.append({
        "rule_id": "TP-07",
        "status": "NOT TESTABLE",
        "reason": (
            "The Travel Requests sheet has no local-conveyance "
            "mode/expense column."
        )
    })


    # ========================================================
    # TP-08
    # ALCOHOL
    # ========================================================

    results.append({
        "rule_id": "TP-08",
        "status": "NOT TESTABLE",
        "reason": (
            "The Travel Requests sheet contains no alcohol-expense "
            "information."
        )
    })


    # ========================================================
    # TP-09
    # RECEIPTS
    # ========================================================

    results.append({
        "rule_id": "TP-09",
        "status": "NOT TESTABLE",
        "reason": (
            "The Travel Requests sheet contains no receipt information."
        )
    })


    # ========================================================
    # TP-10
    # CLAIM DEADLINE
    # ========================================================

    results.append({
        "rule_id": "TP-10",
        "status": "NOT TESTABLE",
        "reason": (
            "The Travel Requests sheet contains no claim-submission "
            "date or return date."
        )
    })


    # ========================================================
    # TP-11
    # INTERNATIONAL TRAVEL
    # ========================================================

    if trip_type.lower() == "international":

        if pd.isna(request_date) or pd.isna(departure_date):

            results.append({
                "rule_id": "TP-11",
                "status": "NOT TESTABLE",
                "reason": "Travel dates unavailable."
            })

        else:

            advance_days = (
                departure_date - request_date
            ).days

            if advance_days >= 21:

                results.append({
                    "rule_id": "TP-11",
                    "status": "NEEDS APPROVAL",
                    "reason": (
                        f"International trip booked {advance_days} days "
                        "before departure. BU Head + CFO approval required."
                    )
                })

            else:

                results.append({
                    "rule_id": "TP-11",
                    "status": "VIOLATION",
                    "reason": (
                        f"International trip booked only {advance_days} "
                        "days before departure. Minimum is 21 days."
                    )
                })

    else:

        results.append({
            "rule_id": "TP-11",
            "status": "NOT APPLICABLE",
            "reason": "Not international travel."
        })


    # ========================================================
    # TP-12
    # PERSONAL EXTENSION
    # ========================================================

    if is_personal_extension(purpose):

        results.append({
            "rule_id": "TP-12",
            "status": "NOT TESTABLE",
            "reason": (
                "Personal extension detected, but the dataset does not "
                "contain business-only fare and actual ticket fare."
            )
        })

    else:

        results.append({
            "rule_id": "TP-12",
            "status": "NOT APPLICABLE",
            "reason": "No personal extension identified."
        })


    # ========================================================
    # TP-13
    # APPROVAL CHAIN
    # ========================================================

    if pd.isna(total_cost):

        results.append({
            "rule_id": "TP-13",
            "status": "NOT TESTABLE",
            "reason": "Estimated total cost unavailable."
        })

    elif trip_type.lower() == "domestic":

        if total_cost > 100000:

            results.append({
                "rule_id": "TP-13",
                "status": "NEEDS APPROVAL",
                "reason": (
                    f"Domestic trip costs ₹{total_cost:,.0f}. "
                    "Manager + department-head approval required."
                )
            })

        else:

            results.append({
                "rule_id": "TP-13",
                "status": "COMPLIANT",
                "reason": (
                    f"Domestic trip costs ₹{total_cost:,.0f}. "
                    "Manager approval is part of the normal approval chain."
                )
            })

    else:

        if total_cost > 100000:

            results.append({
                "rule_id": "TP-13",
                "status": "NEEDS APPROVAL",
                "reason": (
                    f"Trip costs ₹{total_cost:,.0f}; "
                    "additional department-head approval required."
                )
            })

        else:

            results.append({
                "rule_id": "TP-13",
                "status": "COMPLIANT",
                "reason": (
                    "No additional cost-based department-head approval triggered."
                )
            })


    # ========================================================
    # TP-14
    # CANCELLATION
    # ========================================================

    results.append({
        "rule_id": "TP-14",
        "status": "NOT TESTABLE",
        "reason": (
            "The Travel Requests sheet contains no cancellation status, "
            "reason or cancellation-charge information."
        )
    })


    # ========================================================
    # TP-15
    # SPOUSE / FAMILY TRAVEL
    # ========================================================

    results.append({
        "rule_id": "TP-15",
        "status": "NOT TESTABLE",
        "reason": (
            "The Travel Requests sheet contains no spouse/family "
            "traveller information."
        )
    })


    return results


# ============================================================
# FINAL DECISION
# ============================================================

def get_final_decision(rule_results):

    # 1. Actual policy violation always wins
    violations = [
        r for r in rule_results
        if r["status"] == "VIOLATION"
    ]

    if violations:
        return "REJECTED"


    # 2. Explicit additional approval requirement
    approvals = [
        r for r in rule_results
        if r["status"] == "NEEDS APPROVAL"
    ]

    if approvals:
        return "NEEDS APPROVAL"


    # 3. If there are no violations or special approvals,
    # the request is compliant with the testable rules.
    #
    # NOT TESTABLE rules do NOT automatically make the request
    # NEEDS APPROVAL because the required fields simply don't
    # exist in the supplied dataset.
    return "APPROVED"


# ============================================================
# PROCESS ALL REQUESTS
# ============================================================

results = []
rule_audit = []

for _, row in requests_df.iterrows():

    rule_results = evaluate_request(row)

    final_decision = get_final_decision(rule_results)

    violations = [
        r for r in rule_results
        if r["status"] == "VIOLATION"
    ]

    approvals = [
        r for r in rule_results
        if r["status"] == "NEEDS APPROVAL"
    ]

    not_testable = [
        r for r in rule_results
        if r["status"] == "NOT TESTABLE"
    ]

    # --------------------------------------------------------
    # Rule IDs that affected the decision
    # --------------------------------------------------------

    decision_rules = []

    for r in violations:
        decision_rules.append(r["rule_id"])

    for r in approvals:
        decision_rules.append(r["rule_id"])

    # Remove duplicates while maintaining order
    decision_rules = list(dict.fromkeys(decision_rules))

    if decision_rules:
        rule_id_text = ", ".join(decision_rules)
    else:
        rule_id_text = "NONE"


    # --------------------------------------------------------
    # Reason
    # --------------------------------------------------------

    important_reasons = []

    for r in violations:
        important_reasons.append(
            f"{r['rule_id']}: {r['reason']}"
        )

    for r in approvals:
        important_reasons.append(
            f"{r['rule_id']}: {r['reason']}"
        )

    if not important_reasons:
        important_reasons.append(
            "No violation or additional approval requirement "
            "found in the testable policy rules."
        )

    reason_text = " | ".join(important_reasons)


    # --------------------------------------------------------
    # Add final decision
    # --------------------------------------------------------

    results.append({
        "Request_ID": row["request_id"],
        "Employee_Name": row["employee_name"],
        "Grade": row["grade"],
        "Destination": row["destination"],
        "Trip_Type": row["trip_type"],
        "Decision": final_decision,
        "Rule_ID": rule_id_text,
        "Reason": reason_text,
        "Not_Testable_Rules": ", ".join(
            r["rule_id"] for r in not_testable
        )
    })


    # --------------------------------------------------------
    # Save individual rule audit
    # --------------------------------------------------------

    for r in rule_results:

        rule_audit.append({
            "Request_ID": row["request_id"],
            "Employee_Name": row["employee_name"],
            "Rule_ID": r["rule_id"],
            "Status": r["status"],
            "Reason": r["reason"]
        })


# ============================================================
# CREATE DATAFRAMES
# ============================================================

results_df = pd.DataFrame(results)

rule_audit_df = pd.DataFrame(rule_audit)


# ============================================================
# SAVE 150 DECISIONS
# ============================================================

results_df.to_csv(
    DECISION_FILE,
    index=False
)

print(
    f"\n✓ Saved 150 decisions to: {DECISION_FILE}"
)


# ============================================================
# DECISION SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("FINAL DECISION SUMMARY")
print("=" * 70)

print(
    results_df["Decision"]
    .value_counts()
    .to_string()
)


# ============================================================
# SAVE RULE SUMMARY
# ============================================================

rule_summary = (
    rule_audit_df
    .groupby(["Rule_ID", "Status"])
    .size()
    .reset_index(name="Count")
)

rule_summary.to_csv(
    RULE_SUMMARY_FILE,
    index=False
)

print(
    f"\n✓ Saved rule summary to: {RULE_SUMMARY_FILE}"
)


# ============================================================
# MOST COMMON VIOLATIONS
# ============================================================

violations_df = rule_audit_df[
    rule_audit_df["Status"] == "VIOLATION"
]

violation_counts = (
    violations_df
    .groupby("Rule_ID")
    .size()
    .reset_index(name="Violation_Count")
    .sort_values(
        "Violation_Count",
        ascending=False
    )
)

violation_counts.to_csv(
    VIOLATION_FILE,
    index=False
)

print(
    f"✓ Saved violation report to: {VIOLATION_FILE}"
)

print("\nMOST COMMON POLICY VIOLATIONS")

if len(violation_counts) > 0:
    print(
        violation_counts.to_string(index=False)
    )
else:
    print("No violations found.")


# ============================================================
# 30-REQUEST MANUAL AUDIT SAMPLE
# ============================================================

audit_sample = results_df.sample(
    n=30,
    random_state=42
)

audit_sample.to_csv(
    AUDIT_FILE,
    index=False
)

print(
    f"\n✓ Saved 30-request audit to: {AUDIT_FILE}"
)


# ============================================================
# NOT TESTABLE RULES
# ============================================================

not_testable_summary = (
    rule_audit_df[
        rule_audit_df["Status"] == "NOT TESTABLE"
    ]
    .groupby("Rule_ID")
    .size()
    .reset_index(name="Count")
)

print("\nRULES WITH MISSING DATA")

print(
    not_testable_summary.to_string(index=False)
)


# ============================================================
# CHATBOT
# ============================================================

def chatbot_interface():

    print("\n" + "=" * 70)
    print("TRAVEL POLICY COMPLIANCE ASSISTANT")
    print("=" * 70)

    print(
        "\nEnter a Request ID, for example: TR0001"
    )

    print(
        "Type 'exit' to quit.\n"
    )

    while True:

        user_input = input("User: ").strip()

        if user_input.lower() in ["exit", "quit"]:

            print(
                "Assistant: Goodbye!"
            )

            break


        match = results_df[
            results_df["Request_ID"]
            .astype(str)
            .str.upper()
            == user_input.upper()
        ]


        if match.empty:

            print(
                "Assistant: Request ID not found."
            )

            continue


        result = match.iloc[0]

        print("\nAssistant")
        print("-" * 60)

        print(
            f"Request ID : {result['Request_ID']}"
        )

        print(
            f"Employee   : {result['Employee_Name']}"
        )

        print(
            f"Grade      : {result['Grade']}"
        )

        print(
            f"Destination: {result['Destination']}"
        )

        print(
            f"Decision   : {result['Decision']}"
        )

        print(
            f"Rule ID    : {result['Rule_ID']}"
        )

        print(
            f"Reason     : {result['Reason']}"
        )

        if result["Not_Testable_Rules"] != "":

            print(
                f"Not tested : {result['Not_Testable_Rules']}"
            )

        print("-" * 60)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    chatbot_interface()